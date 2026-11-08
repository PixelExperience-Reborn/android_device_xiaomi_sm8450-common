import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from compare_fstab_pair import parse_fstab, compare


def row(device, mount, fs_type, opts="ro", flags="wait,first_stage_mount"):
    return f"{device} {mount} {fs_type} {opts} {flags}"


def fixtures(system_fs="erofs", file_encryption="v2+wrappedkey_v0"):
    base = [
        row("system", "/system", system_fs, "ro", "wait,logical,first_stage_mount"),
        row("vendor", "/vendor", system_fs, "ro", "wait,logical,first_stage_mount"),
        row("/dev/block/by-name/metadata", "/metadata", "ext4", "rw", "wait,first_stage_mount"),
        row("/dev/block/by-name/userdata", "/data", "f2fs", "rw",
            f"wait,fileencryption={file_encryption},metadata_encryption=aes-256-xts"),
    ]
    return parse_fstab("\n".join(base) + "\n")


class StorageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((ROOT / "storage-fstab-qualification.json").read_text(encoding="utf-8"))

    def test_platform_scope_and_partition_roots(self):
        self.assertEqual(self.d["device_scope"], "mondrian")
        self.assertEqual(self.d["soc"], "SM8475")
        board = (ROOT / "BoardConfigCommon.mk").read_text(encoding="utf-8")
        self.assertIn("BOARD_USES_METADATA_PARTITION := true", board)
        self.assertIn("TARGET_BOOTLOADER_BOARD_NAME := taro", board)
        self.assertIn("TARGET_NO_BOOTLOADER := true", board)
        for name in ("ODM", "PRODUCT", "SYSTEM_EXT", "VENDOR", "VENDOR_DLKM"):
            self.assertIn(f"TARGET_COPY_OUT_{name} :=", board)

    def test_unselected_release_settings(self):
        p = self.d["production_selection"]
        for key in ("filesystem_type", "active_fstab_path",
                    "active_recovery_fstab_path", "encryption_policy",
                    "avb_keys", "rollback_index", "super_partition_size"):
            self.assertIsNone(p[key])
        for key in ("userdata_fstab_qualified", "recovery_mounts_qualified",
                    "module_load_order_qualified", "boot_build_proven"):
            self.assertFalse(p[key])
        self.assertFalse(self.d["safety"]["enable_fm_radio"])
        self.assertFalse(self.d["safety"]["allow_avb_disable_flags"])

    def test_reference_fstabs_not_treated_as_interchangeable(self):
        p = self.d["partition_mount_reference"]
        self.assertEqual(p["main_logical_filesystem"], "erofs")
        self.assertEqual(p["recovery_logical_filesystem"], "ext4")
        self.assertNotEqual(p["data"]["main_fbe"], p["data"]["recovery_fbe"])
        self.assertTrue(p["difference_requires_review"])
        for src in ("main_fstab", "recovery_fstab"):
            self.assertRegex(self.d["reference_sources"][src]["git_blob_sha"], r"^[0-9a-f]{40}$")

    def test_matching_fstabs_pass_static_gate(self):
        a, b = fixtures(), fixtures()
        self.assertEqual(compare(a, b), [])

    def test_disagreeing_erofs_and_ext4_fails(self):
        errors = compare(fixtures("erofs"), fixtures("ext4"))
        self.assertTrue(any("filesystem mismatch" in x for x in errors))

    def test_disagreeing_encryption_contract_fails(self):
        errors = compare(fixtures(file_encryption="v2+wrappedkey_v0"),
                         fixtures(file_encryption="ice"))
        self.assertTrue(any("fileencryption" in x for x in errors))

    def test_missing_metadata_and_duplicate_mounts_fail(self):
        a = fixtures()
        b = fixtures()
        del b["/metadata"]
        self.assertTrue(any("/metadata" in x for x in compare(a, b)))
        with self.assertRaises(ValueError):
            parse_fstab(
                row("system", "/system", "erofs") + "\n" +
                row("system_ext", "/system", "erofs") + "\n"
            )

    def test_old_fm_kernel_modules_are_not_active(self):
        self.assertEqual(set(self.d["module_reference_exclusions"]),
                         {"bt_fm_slim.ko", "radio-i2c-rtc6226-qca.ko"})
        for filename in ("BoardConfigCommon.mk", "common.mk"):
            statements = "\n".join(x for x in (ROOT / filename).read_text().splitlines()
                                   if x.strip() and not x.lstrip().startswith("#"))
            self.assertNotIn("radio-i2c-rtc6226-qca.ko", statements)
            self.assertNotIn("bt_fm_slim.ko", statements)


if __name__ == "__main__":
    unittest.main()
