import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/verify_boot_artifacts.py"
spec = importlib.util.spec_from_file_location("verify_boot_artifacts", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def boot_header(kernel_size=1):
    data = bytearray(4096)
    data[:8] = b"ANDROID!"
    struct.pack_into("<I", data, 8, kernel_size)
    struct.pack_into("<I", data, 20, 1584)
    struct.pack_into("<I", data, 40, 4)
    return bytes(data)


def vendor_boot_header():
    data = bytearray(4096)
    data[:8] = b"VNDRBOOT"
    struct.pack_into("<I", data, 8, 4)
    struct.pack_into("<I", data, 12, 4096)
    return bytes(data)


def dtbo_table():
    return struct.pack(">8I", mod.DTBO_MAGIC, 64, 32, 32, 1, 32, 4096, 0) + bytes(32)


def fake_image_set(directory):
    # Synthetic header fixtures only. These are not bootable images and must
    # never be published, flashed, or confused with build artifacts.
    files = {
        "boot.img": boot_header(1),
        "recovery.img": boot_header(0),
        "vendor_boot.img": vendor_boot_header(),
        "dtbo.img": dtbo_table(),
        "vendor_dlkm.img": b"EROFS-TEST-FIXTURE-NOT-REAL",
        "vbmeta.img": b"AVB0-test-fixture",
        "vbmeta_system.img": b"AVB0-test-fixture",
    }
    for filename, data in files.items():
        (directory / filename).write_bytes(data)


class MondrianFinalArtifactTests(unittest.TestCase):
    def test_complete_named_image_set_passes_only_format_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fake_image_set(p)
            report = mod.validate(p)
            self.assertEqual(set(report["images"]), set(mod.REQUIRED))
            self.assertTrue(report["format_checked_not_boot_verified"])

    def test_lone_kernel_image_not_accepted_as_boot_img(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "Image").write_bytes(b"not an Android boot image")
            with self.assertRaisesRegex(ValueError, "missing boot.img"):
                mod.validate(p)

    def test_missing_dtbo_or_vendor_boot_image_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fake_image_set(p)
            (p / "dtbo.img").unlink()
            with self.assertRaisesRegex(ValueError, "dtbo.img"):
                mod.validate(p)
            fake_image_set(p)
            (p / "vendor_boot.img").unlink()
            with self.assertRaisesRegex(ValueError, "vendor_boot.img"):
                mod.validate(p)

    def test_wrong_header_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fake_image_set(p)
            bad = bytearray((p / "boot.img").read_bytes())
            struct.pack_into("<I", bad, 40, 3)
            (p / "boot.img").write_bytes(bad)
            with self.assertRaisesRegex(ValueError, "expected header v4"):
                mod.validate(p)

    def test_dtbo_must_have_nonempty_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fake_image_set(p)
            (p / "dtbo.img").write_bytes(b"Image" + bytes(40))
            with self.assertRaisesRegex(ValueError, "not an Android DTBO"):
                mod.validate(p)
            fake_image_set(p)
            broken = bytearray((p / "dtbo.img").read_bytes())
            struct.pack_into(">I", broken, 16, 0)
            (p / "dtbo.img").write_bytes(broken)
            with self.assertRaisesRegex(ValueError, "no DTBO entries"):
                mod.validate(p)

    def test_dtbo_partition_size_cannot_be_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fake_image_set(p)
            with (p / "dtbo.img").open("ab") as fd:
                fd.truncate(0x01800000 + 1)
            with self.assertRaisesRegex(ValueError, "exceeds partition limit"):
                mod.validate(p)

    def test_missing_avb_image_or_invalid_magic_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fake_image_set(p)
            (p / "vbmeta.img").write_bytes(b"BAD!" + bytes(100))
            with self.assertRaisesRegex(ValueError, "missing AVB vbmeta header"):
                mod.validate(p)
            fake_image_set(p)
            (p / "vbmeta_system.img").unlink()
            with self.assertRaisesRegex(ValueError, "missing vbmeta_system.img"):
                mod.validate(p)

    def test_guarded_aosp_packaging_contract_not_active_by_default(self):
        board = (ROOT / "BoardConfigCommon.mk").read_text(encoding="utf-8")
        images = (ROOT / "BoardConfigBootImages.mk").read_text(encoding="utf-8")
        self.assertIn("ifeq ($(PE_MONDRIAN_BOOT_STAGE),qualified)", board)
        self.assertIn("include $(COMMON_DEVICE_PATH)/BoardConfigBootImages.mk", board)
        for key in ("PE_MONDRIAN_KERNEL_BSP_VERIFIED",
                    "PE_MONDRIAN_VENDOR_FIRMWARE_VERIFIED",
                    "PE_MONDRIAN_FBE_AND_RECOVERY_VERIFIED",
                    "PE_MONDRIAN_AVB_SIGNING_VERIFIED"):
            self.assertIn(f"ifneq ($({key}),true)", images)
        self.assertIn("BOARD_BOOT_HEADER_VERSION := 4", images)
        self.assertIn("TARGET_USERIMAGES_USE_EROFS := true", board)
        for part in ("SYSTEM", "SYSTEM_EXT", "PRODUCT", "VENDOR", "ODM", "VENDOR_DLKM"):
            self.assertIn(f"BOARD_{part}IMAGE_FILE_SYSTEM_TYPE := erofs", board)
        self.assertNotIn("BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := erofs", images)
        self.assertIn("TARGET_NEEDS_DTBOIMAGE := true", images)
        self.assertIn("BOARD_KERNEL_IMAGE_NAME := Image", images)  # compiler input only
        self.assertIn("TARGET_KERNEL_EXT_MODULE_ROOT := kernel/xiaomi/sm8450-modules", images)
        self.assertIn("BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true", images)
        self.assertNotIn("BOARD_USES_QCOM_MERGE_DTBS_SCRIPT := true", images)
        self.assertIn("BOARD_DTBOIMG_PARTITION_SIZE := 0x01800000", images)
        self.assertIn("BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 0x06000000", images)
        for name in ("boot", "dtbo", "recovery", "vendor_boot", "vendor_dlkm"):
            self.assertIn(f"    {name}", images)
        self.assertNotIn("testkey", images)
        self.assertNotIn("--flags 3", images)


if __name__ == "__main__":
    unittest.main()
