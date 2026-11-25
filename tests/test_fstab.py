# SPDX-License-Identifier: Apache-2.0
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate_fstab import FSTAB, compare_with_stock, parse_fstab, validate, validate_rows  # noqa: E402


def rows():
    return parse_fstab(FSTAB.read_text(encoding="utf-8"))


def find(table, mount, fs):
    return next(r for r in table if r["mount"] == mount and r["fs"] == fs)


class FstabTests(unittest.TestCase):
    def test_fstab_is_valid_and_installed(self):
        validate()

    def test_every_logical_partition_mounts_erofs_read_only(self):
        table = rows()
        for part in ("system", "system_ext", "product", "vendor", "vendor_dlkm", "odm"):
            row = find(table, "/" + part, "erofs")
            self.assertEqual(row["options"], ["ro"])
            self.assertIn("first_stage_mount", row["flags"])

    def test_firmware_and_persist_mounts_are_present(self):
        mounts = {r["mount"] for r in rows()}
        for mount in ("/vendor/firmware_mnt", "/vendor/dsp", "/vendor/bt_firmware",
                      "/mnt/vendor/persist", "/mnt/vendor/qmcs", "/storage/usbotg"):
            self.assertIn(mount, mounts)

    def test_option_unknown_to_our_kernel_is_rejected(self):
        table = rows()
        find(table, "/data", "f2fs")["options"].append("age_extent_cache")
        with self.assertRaisesRegex(ValueError, "not supported by our 5.10.81 kernel"):
            validate_rows(table)

    def test_missing_persist_is_rejected(self):
        table = [r for r in rows() if r["mount"] != "/mnt/vendor/persist"]
        with self.assertRaisesRegex(ValueError, "entries differ"):
            validate_rows(table)

    def test_weakened_encryption_is_rejected(self):
        table = rows()
        find(table, "/data", "f2fs")["flags"]["fileencryption"] = "ice"
        with self.assertRaisesRegex(ValueError, "file-based encryption"):
            validate_rows(table)

    def test_duplicate_entry_and_bad_line_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate entry"):
            parse_fstab("vendor /vendor erofs ro wait\nvendor /vendor erofs ro wait\n")
        with self.assertRaisesRegex(ValueError, "expected 5 fields"):
            parse_fstab("vendor /vendor erofs ro\n")

    def test_stock_comparison_accepts_only_documented_differences(self):
        table = rows()
        stock_lines = []
        for r in table:
            options = list(r["options"])
            if r["mount"] == "/data":
                options.append("age_extent_cache")
            flags = ",".join(k if v is None else f"{k}={v}" for k, v in r["flags"].items())
            stock_lines.append(f"{r['device']} {r['mount']} {r['fs']} {','.join(options)} {flags}")
        stock_lines.append("mi_ext /mnt/vendor/mi_ext erofs ro wait,slotselect,logical,nofail")
        stock_lines.append("overlay /product/app overlay ro,lowerdir=/x:/product/app check,nofail")
        stock_lines.append("/devices/platform/soc/8804000.sdhci/mmc_host* /storage/sdcard1 vfat "
                           "nosuid,nodev wait,voldmanaged=sdcard1:auto")
        compare_with_stock(table, "\n".join(stock_lines))
        changed = copy.deepcopy(table)
        find(changed, "/vendor/dsp", "ext4")["options"] = ["rw"]
        with self.assertRaisesRegex(ValueError, "differs from stock"):
            compare_with_stock(changed, "\n".join(stock_lines))


if __name__ == "__main__":
    unittest.main()
