"""Native AOSP17 mondrian EROFS + virtual A/B product integration tests.

Assert real active product and board properties, not documentation-only
metadata. Do not imply source compilation, mount/FBE success or boot.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTITIONS = ("SYSTEM", "SYSTEM_EXT", "PRODUCT", "VENDOR", "ODM", "VENDOR_DLKM")
MOUNTS = {"/system", "/system_ext", "/product", "/vendor", "/odm", "/vendor_dlkm"}


def active_text(filename):
    return "\n".join(
        line.split("#", 1)[0].rstrip() for line in
        (ROOT / filename).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def board_assignments(source):
    assignments = {}
    for line in active_text(source).splitlines():
        found = re.match(r"^([A-Z][A-Z0-9_]*)\s*:?=\s*(.+)$", line)
        if found:
            key, value = found.groups()
            if key in assignments:
                raise AssertionError(f"duplicate board assignment: {key} in {source}")
            assignments[key] = value.strip()
    return assignments


class MondrianNativeErofsIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = board_assignments("BoardConfigCommon.mk")
        cls.boot = board_assignments("BoardConfigBootImages.mk")
        cls.product = active_text("common.mk")

    def test_all_six_logical_images_are_actively_erofs(self):
        b = self.board
        self.assertEqual(b.get("TARGET_USERIMAGES_USE_EROFS"), "true")
        self.assertEqual(b.get("BOARD_EROFS_COMPRESSOR"), "lz4hc,9")
        self.assertEqual(b.get("BOARD_EROFS_PCLUSTER_SIZE"), "65536")
        for partition in PARTITIONS:
            key = f"BOARD_{partition}IMAGE_FILE_SYSTEM_TYPE"
            self.assertEqual(b.get(key), "erofs", f"{key} not active")
            self.assertNotIn(key, self.boot, f"two conflicting owners for {key}")

    def test_userdata_is_f2fs_and_metadata_ext4(self):
        self.assertEqual(self.board.get("TARGET_USERIMAGES_USE_F2FS"), "true")
        self.assertEqual(self.board.get("TARGET_USERIMAGES_USE_EXT4"), "true")
        first = (ROOT / "rootdir/etc/fstab.qcom").read_text()
        recovery = (ROOT / "rootdir/etc/recovery.fstab").read_text()
        for name, text in (("main", first), ("recovery", recovery)):
            rows = {}
            for line in text.splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    cols = line.split()
                    if len(cols) != 5 or not cols[1].startswith("/"):
                        continue
                    rows[cols[1]] = cols[2]
            self.assertEqual({k for k, v in rows.items() if v == "erofs"}, MOUNTS,
                             f"{name}: wrong dynamic filesystem")
            self.assertEqual(rows.get("/data"), "f2fs")
            self.assertEqual(rows.get("/metadata"), "ext4")

    def test_aosp_virtual_ab_and_dynamic_partition_product_is_active(self):
        p = self.product
        for source in (
            "product/emulated_storage.mk",
            "product/generic_ramdisk.mk",
            "product/virtual_ab_ota/launch_with_vendor_ramdisk.mk",
        ):
            self.assertIn(f"$(SRC_TARGET_DIR)/{source}", p)
        self.assertIn("PRODUCT_USE_DYNAMIC_PARTITIONS := true", p)
        for name in ("fastbootd", "update_engine", "update_engine_sideload",
                     "update_verifier", "otapreopt_script"):
            self.assertRegex(p, rf"(?m)^\s+{name}(?:\s|$|\\)")
        self.assertIn("FILESYSTEM_TYPE_system=erofs", p)
        self.assertNotIn("FILESYSTEM_TYPE_system=ext4", p)

    def test_no_historic_rom_or_fm_radio_dependency(self):
        for source in ("BoardConfigCommon.mk", "BoardConfigBootImages.mk", "common.mk"):
            text = active_text(source)
            for token in ("vendor/lineage", "vendor.lineage.", "fm-commonsys",
                          "FMRadio", "radio-i2c-rtc6226-qca.ko", "bt_fm_slim.ko",
                          "--flags 3", "testkey"):
                self.assertNotIn(token, text)

    def test_erofs_is_active_independent_of_unverified_boot_image_gate(self):
        board = (ROOT / "BoardConfigCommon.mk").read_text()
        self.assertIn("BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := erofs", board)
        self.assertIn("ifeq ($(PE_MONDRIAN_BOOT_STAGE),qualified)", board)
        self.assertIn("include $(COMMON_DEVICE_PATH)/BoardConfigBootImages.mk", board)
        self.assertNotIn("BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE", self.boot)
        self.assertNotIn("BOARD_AVB_ENABLE", self.board)
        self.assertNotIn("BOARD_BOOT_HEADER_VERSION", self.board)


if __name__ == "__main__":
    unittest.main()
