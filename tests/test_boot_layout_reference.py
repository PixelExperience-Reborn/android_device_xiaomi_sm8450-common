import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_reference_boot_layout import load, verify_source, git_blob_sha, parse_ab_partitions


def synthetic_board(profile, filesystem):
    fields = profile["matching_reference_fields"]
    assignments = [f"{k} := {hex(v) if k.endswith('_PARTITION_SIZE') and k != 'BOARD_QTI_DYNAMIC_PARTITIONS_SIZE' else v}" for k, v in fields.items()]
    assignments.append("BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST := " +
                       " ".join(profile["dynamic_partition_names"]))
    ab = profile["reference_ab_ota_partitions"]
    assignments += ["AB_OTA_PARTITIONS += " + chr(92)]
    assignments += [f"    {name} " + (chr(92) if i < len(ab) - 1 else "")
                    for i, name in enumerate(ab)]
    for part in ("ODM", "PRODUCT", "SYSTEM", "SYSTEM_EXT", "VENDOR", "VENDOR_DLKM"):
        assignments.append(f"BOARD_{part}IMAGE_FILE_SYSTEM_TYPE := {filesystem}")
    return "\n".join(assignments) + "\n"


class BootLayoutReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load()

    def test_real_source_baselines_are_pinned_and_distinct(self):
        d = self.profile
        self.assertEqual(d["device"], "mondrian")
        self.assertEqual(d["soc"], "SM8475")
        self.assertEqual(d["matching_reference_fields"]["BOARD_BOOT_HEADER_VERSION"], 4)
        self.assertEqual(d["super_metadata_reserve_bytes"], 4 * 1024 * 1024)
        self.assertEqual(set(r["logical_fs"] for r in d["references"]), {"erofs", "ext4"})
        self.assertFalse(any(d["release_gates"].values()))

    def test_independent_reference_variants_are_both_internally_consistent(self):
        for r in self.profile["references"]:
            with self.subTest(repo=r["repo"]):
                verify_source(synthetic_board(self.profile, r["logical_fs"]), r, self.profile)

    def test_changed_super_or_dynamic_size_is_blocked(self):
        r = self.profile["references"][0]
        raw = synthetic_board(self.profile, r["logical_fs"])
        raw = raw.replace("BOARD_SUPER_PARTITION_SIZE := 0x220000000",
                          "BOARD_SUPER_PARTITION_SIZE := 0x220000001")
        with self.assertRaisesRegex(ValueError, "BOARD_SUPER_PARTITION_SIZE changed"):
            verify_source(raw, r, self.profile)

    def test_different_filesystem_choice_is_not_interchangeable(self):
        official, own = self.profile["references"]
        with self.assertRaisesRegex(ValueError, "fs changed"):
            verify_source(synthetic_board(self.profile, own["logical_fs"]), official, self.profile)
        with self.assertRaisesRegex(ValueError, "fs changed"):
            verify_source(synthetic_board(self.profile, official["logical_fs"]), own, self.profile)

    def test_missing_ota_partition_is_rejected(self):
        r = self.profile["references"][0]
        raw = synthetic_board(self.profile, r["logical_fs"])
        raw = "\n".join(line for line in raw.splitlines() if line.strip() != "vendor_dlkm") + "\n"
        with self.assertRaises(ValueError):
            verify_source(raw, r, self.profile)

    def test_blob_hash_uses_real_git_object_framing(self):
        payload = b"mondrian\n"
        expected = hashlib.sha1(b"blob 9" + bytes([0]) + payload).hexdigest()
        self.assertEqual(git_blob_sha(payload), expected)

    def test_deferred_real_boot_and_recovery_gates(self):
        d = load()
        for key in ("on_device_partition_sizes_verified", "verified_boot_chain_configured",
                    "real_boot_tested", "recovery_ramdisk_boot_tested"):
            self.assertFalse(d["release_gates"][key])
        self.assertFalse(d["filesystem_decision"]["selected_for_production"])


if __name__ == "__main__":
    unittest.main()
