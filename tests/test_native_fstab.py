import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from compare_fstab_pair import compare, parse_fstab
from validate_native_fstab import NORMAL, RECOVERY, validate, validate_rows


class NativeMondrianFstabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal = parse_fstab(NORMAL.read_text(encoding="utf-8"))
        cls.recovery = parse_fstab(RECOVERY.read_text(encoding="utf-8"))

    def test_native_pair_is_syntactically_consistent_and_still_uninstalled(self):
        validate()
        self.assertEqual(compare(self.normal, self.recovery), [])

    def test_no_stale_ext4_recovery_paths(self):
        for mount in ("/system", "/system_ext", "/product", "/vendor", "/odm", "/vendor_dlkm"):
            self.assertEqual(self.normal[mount]["filesystem"], "erofs")
            self.assertEqual(self.recovery[mount]["filesystem"], "erofs")
            self.assertIn("avb", self.recovery[mount]["flags"])

    def test_downgraded_recovery_crypto_is_rejected(self):
        broken = copy.deepcopy(self.recovery)
        broken["/data"]["flags"]["fileencryption"] = "ice"
        with self.assertRaisesRegex(ValueError, "FBE v2"):
            validate_rows(broken, "recovery")
        self.assertTrue(any("fileencryption" in e for e in compare(self.normal, broken)))

    def test_missing_vendor_dlkm_is_rejected(self):
        broken = copy.deepcopy(self.recovery)
        del broken["/vendor_dlkm"]
        with self.assertRaisesRegex(ValueError, "unexpected/missing"):
            validate_rows(broken, "recovery")

    def test_modified_avb_chain_or_missing_first_stage_is_rejected(self):
        broken = copy.deepcopy(self.recovery)
        broken["/system"]["flags"]["avb"] = None
        with self.assertRaisesRegex(ValueError, "AVB chain"):
            validate_rows(broken, "recovery")
        broken = copy.deepcopy(self.normal)
        del broken["/vendor"]["flags"]["first_stage_mount"]
        with self.assertRaisesRegex(ValueError, "missing first_stage_mount"):
            validate_rows(broken, "normal")

    def test_unsafe_user_data_format_and_nobarrier_are_rejected(self):
        broken = copy.deepcopy(self.normal)
        broken["/data"]["flags"]["formattable"] = None
        with self.assertRaisesRegex(ValueError, "format user data"):
            validate_rows(broken, "normal")
        broken = copy.deepcopy(self.normal)
        broken["/data"]["options"] += ",fsync_mode=nobarrier"
        with self.assertRaisesRegex(ValueError, "nobarrier"):
            validate_rows(broken, "normal")

    def test_wrapped_key_and_metadata_keydirectory_are_fixed(self):
        for rows in (self.normal, self.recovery):
            flags = rows["/data"]["flags"]
            self.assertIn("v2+inlinecrypt_optimized+wrappedkey_v0", flags["fileencryption"])
            self.assertEqual(flags["metadata_encryption"], "aes-256-xts:wrappedkey_v0")
            self.assertEqual(flags["keydirectory"], "/metadata/vold/metadata_encryption")

    def test_invalid_or_duplicate_fstab_entry_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_fstab("vendor /vendor erofs ro\n")
        with self.assertRaisesRegex(ValueError, "expected exactly 5 fields"):
            parse_fstab("vendor /vendor erofs ro wait unexpected\n")
        with self.assertRaisesRegex(ValueError, "duplicate fs_mgr flag"):
            parse_fstab("vendor /vendor erofs ro wait,wait\n")
        with self.assertRaises(ValueError):
            parse_fstab("vendor /vendor erofs ro wait\nvendor /vendor erofs ro wait\n")


if __name__ == "__main__":
    unittest.main()
