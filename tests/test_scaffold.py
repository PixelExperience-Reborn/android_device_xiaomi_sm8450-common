from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IndependentCommonFoundationTest(unittest.TestCase):
    def test_confirmed_target_family_and_architecture(self):
        board = (ROOT / "BoardConfigCommon.mk").read_text()
        self.assertIn("TARGET_ARCH := arm64", board)
        self.assertIn("TARGET_BOARD_PLATFORM := taro", board)
        self.assertIn("TARGET_CPU_ABI := arm64-v8a", board)

    def test_no_unreviewed_rom_or_boot_settings(self):
        for path in ("BoardConfigCommon.mk", "common.mk"):
            with self.subTest(file=path):
                active = "\n".join(
                    line for line in (ROOT / path).read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ).lower()
                for forbidden in ("vendor/lineage", "org.lineageos", "vendor.lineage", "lineage_version"):
                    self.assertNotIn(forbidden, active)
                self.assertNotIn("testkey_rsa2048", active)
                self.assertNotIn("--flags 3", active)

    def test_do_not_claim_boot_readiness(self):
        note = (ROOT / "docs/HARDWARE_CONTRACT.md").read_text()
        self.assertIn("No vendor blobs, boot image layout", note)
        self.assertIn("UDFPS", note)
        self.assertIn("Touch", note)


if __name__ == "__main__":
    unittest.main()
