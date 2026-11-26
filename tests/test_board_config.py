"""BoardConfigCommon.mk and common.mk against the stock OS3.0.8.0.VMNCNXM firmware.

Every boot, partition, super and AVB value is compared with the official
full OTA (payload manifest sha256 771becf9...): the image sizes and dynamic
partition group of its manifest, the header and bootconfig of its
vendor_boot, the empty-kernel recovery image and the descriptors of its
vbmeta and vbmeta_system.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Facts of the stock OTA (official full OTA OS3.0.8.0.VMNCNXM).
STOCK_IMAGE_SIZES = {
    "BOARD_BOOTIMAGE_PARTITION_SIZE": 201326592,
    "BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE": 100663296,
    "BOARD_RECOVERYIMAGE_PARTITION_SIZE": 104857600,
}
STOCK_DTBO_IMAGE = 24117248          # what stock pads dtbo.img to
DTBO_PARTITION = 25165824            # the 24 MiB partition other builds fill
STOCK_DYNAMIC = {"odm", "product", "system", "system_ext", "vendor", "vendor_dlkm", "mi_ext"}
STOCK_GROUP = "qti_dynamic_partitions"
STOCK_BOOTCONFIG = {"androidboot.hardware=qcom", "androidboot.memcg=1",
                    "androidboot.usbcontroller=a600000.dwc3"}
STOCK_OFFSETS = {"BOARD_KERNEL_BASE": 0, "BOARD_KERNEL_OFFSET": 0x8000,
                 "BOARD_RAMDISK_OFFSET": 0x01000000, "BOARD_KERNEL_TAGS_OFFSET": 0x100,
                 "BOARD_DTB_OFFSET": 0x01F00000}
STOCK_VBMETA_SYSTEM = {"product", "system", "system_ext"}
XIAOMI_ONLY = {"mi_ext"}
# ro.bionic.* and ro.vendor.build.security_patch of the stock vendor build.prop.
STOCK_BIONIC = {"TARGET_CPU_VARIANT_RUNTIME": "kryo300",
                "TARGET_2ND_CPU_VARIANT_RUNTIME": "cortex-a75"}
STOCK_VENDOR_SPL = "2026-02-01"
# Variants Soong of Android 17 accepts (build/soong/android/arch_list.go).
SOONG_ARM64_ARCH = {"armv8-a", "armv8-a-branchprot", "armv8-2a", "armv8-2a-dotprod",
                    "armv8-5a", "armv8-7a", "armv9-a", "armv9-2a", "armv9-3a", "armv9-4a"}
SOONG_ARM64_CPU = {"generic", "cortex-a53", "cortex-a55", "cortex-a72", "cortex-a73",
                   "cortex-a75", "cortex-a76", "kryo", "kryo385", "exynos-m1", "exynos-m2",
                   "oryon"}
LOGICAL = ("SYSTEM", "SYSTEM_EXT", "PRODUCT", "VENDOR", "ODM", "VENDOR_DLKM")


def assignments(name):
    """Make assignments of a file, continuation lines joined, comments removed."""
    text = (ROOT / name).read_text()
    text = re.sub(r"\\\n", " ", text)
    values = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        found = re.match(r"^([A-Z][A-Z0-9_.]*)\s*(\+?:?=)\s*(.*)$", line)
        if not found:
            continue
        key, op, value = found.groups()
        value = " ".join(value.split())
        values[key] = (values.get(key, "") + " " + value).strip() if op == "+=" else value
    return values


class BoardConfigAgainstStockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = assignments("BoardConfigCommon.mk")
        cls.product = (ROOT / "common.mk").read_text()

    def test_architecture_and_platform(self):
        b = self.board
        self.assertEqual(b["TARGET_ARCH"], "arm64")
        self.assertEqual(b["TARGET_CPU_ABI"], "arm64-v8a")
        self.assertEqual(b["TARGET_BOARD_PLATFORM"], "taro")
        self.assertIn(b["TARGET_ARCH_VARIANT"], SOONG_ARM64_ARCH)
        self.assertIn(b["TARGET_CPU_VARIANT"], SOONG_ARM64_CPU)
        # No SVE: Qualcomm does not enable it on SM8475.
        self.assertFalse(b["TARGET_ARCH_VARIANT"].startswith("armv9"))
        for key, value in STOCK_BIONIC.items():
            self.assertEqual(b[key], value, key)

    def test_vendor_security_patch_is_stock(self):
        self.assertEqual(self.board["VENDOR_SECURITY_PATCH"], STOCK_VENDOR_SPL)

    def test_boot_images_follow_stock_vendor_boot(self):
        b = self.board
        self.assertEqual(b["BOARD_BOOT_HEADER_VERSION"], "4")
        self.assertEqual(b["BOARD_KERNEL_PAGESIZE"], "4096")
        for key, value in STOCK_OFFSETS.items():
            self.assertEqual(int(b[key], 16), value, key)
        for key in ("BOARD_KERNEL_OFFSET", "BOARD_RAMDISK_OFFSET",
                    "BOARD_KERNEL_TAGS_OFFSET", "BOARD_DTB_OFFSET"):
            flag = "--" + key[len("BOARD_"):].lower().replace("kernel_tags", "tags")
            self.assertIn(f"{flag} $({key})", b["BOARD_MKBOOTIMG_ARGS"])
        self.assertEqual(set(b["BOARD_BOOTCONFIG"].split()), STOCK_BOOTCONFIG)
        self.assertEqual(b["BOARD_KERNEL_CMDLINE"].split(),
                         ["video=vfb:640x400,bpp=32,memsize=3072000", "disable_dma32=on"])
        self.assertEqual(b["BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE"], "true")
        self.assertEqual(b["BOARD_INCLUDE_DTB_IN_BOOTIMG"], "true")

    def test_raw_partitions_are_the_stock_sizes(self):
        for key, size in STOCK_IMAGE_SIZES.items():
            self.assertEqual(int(self.board[key], 0), size, key)
        dtbo = int(self.board["BOARD_DTBOIMG_PARTITION_SIZE"], 0)
        self.assertEqual(dtbo, DTBO_PARTITION)
        self.assertGreaterEqual(dtbo, STOCK_DTBO_IMAGE)

    def test_super_is_the_stock_group_without_xiaomi_partitions(self):
        b = self.board
        self.assertEqual(b["BOARD_SUPER_PARTITION_GROUPS"], STOCK_GROUP)
        listed = set(b["BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST"].split())
        self.assertEqual(listed, STOCK_DYNAMIC - XIAOMI_ONLY)
        self.assertEqual(int(b["BOARD_QTI_DYNAMIC_PARTITIONS_SIZE"]),
                         int(b["BOARD_SUPER_PARTITION_SIZE"]) - 4 * 1024 * 1024)
        ab = set(b["AB_OTA_PARTITIONS"].split())
        self.assertTrue(listed <= ab)
        self.assertTrue({"boot", "dtbo", "recovery", "vbmeta", "vbmeta_system", "vendor_boot"} <= ab)
        self.assertFalse(ab & XIAOMI_ONLY)

    def test_logical_partitions_are_erofs_as_the_fstab(self):
        b = self.board
        self.assertEqual(b["TARGET_USERIMAGES_USE_EROFS"], "true")
        for part in LOGICAL:
            self.assertEqual(b[f"BOARD_{part}IMAGE_FILE_SYSTEM_TYPE"], "erofs", part)
        sys.path.insert(0, str(ROOT / "tools"))
        from validate_fstab import FSTAB, parse_fstab
        rows = parse_fstab(FSTAB.read_text())
        erofs = {r["mount"] for r in rows if r["fs"] == "erofs"}
        self.assertEqual(erofs, {"/" + p.lower() for p in LOGICAL})
        self.assertEqual({r["fs"] for r in rows if r["mount"] == "/data"}, {"f2fs"})
        self.assertEqual({r["fs"] for r in rows if r["mount"] == "/metadata"}, {"ext4"})

    def test_avb_chain_is_the_stock_chain(self):
        b = self.board
        self.assertEqual(b["BOARD_AVB_ENABLE"], "true")
        self.assertEqual(set(b["BOARD_AVB_VBMETA_SYSTEM"].split()), STOCK_VBMETA_SYSTEM)
        self.assertEqual(b["BOARD_AVB_RECOVERY_ROLLBACK_INDEX_LOCATION"], "1")
        self.assertEqual(b["BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX_LOCATION"], "2")
        for key in ("BOARD_AVB_RECOVERY_ALGORITHM", "BOARD_AVB_VBMETA_SYSTEM_ALGORITHM"):
            self.assertEqual(b[key], "SHA256_RSA2048")
        self.assertNotIn("--flags", b.get("BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS", ""))

    def test_virtual_ab_product(self):
        p = self.product
        for source in ("product/emulated_storage.mk", "product/generic_ramdisk.mk",
                       "product/virtual_ab_ota/launch_with_vendor_ramdisk.mk"):
            self.assertIn(f"$(SRC_TARGET_DIR)/{source}", p)
        self.assertIn("PRODUCT_USE_DYNAMIC_PARTITIONS := true", p)
        self.assertIn("FILESYSTEM_TYPE_system=erofs", p)

    def test_no_other_rom_product_layer(self):
        for name in ("BoardConfigCommon.mk", "common.mk"):
            text = "\n".join(l.split("#", 1)[0] for l in (ROOT / name).read_text().splitlines()).lower()
            for token in ("vendor/lineage", "vendor.lineage", "org.lineageos"):
                self.assertNotIn(token, text, name)


if __name__ == "__main__":
    unittest.main()
