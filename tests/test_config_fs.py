# SPDX-License-Identifier: Apache-2.0
"""config.fs: the vendor AIDs and file modes of the stock vendor.

The stock .rc files run services as vendor users and groups (vendor_qrtr,
vendor_qti_diag, ...); Android 17 checks them at build time (host init
verifier) against the passwd and group the build generates from config.fs.
The stock daemons need their file capabilities (pd-mapper, cnd, ...).
"""
import configparser
import os
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = next((p for p in (Path(os.environ.get("MONDRIAN_STOCK_FS", "/nonexistent")), Path("/home/user/fw/fs"))
              if (p / "vendor/etc/passwd").is_file()), None)
def config():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string((ROOT / "config.fs").read_text())
    return parser


class ConfigFsTest(unittest.TestCase):
    def test_is_the_fs_config_of_the_build(self):
        board = (ROOT / "BoardConfigCommon.mk").read_text()
        self.assertIn("TARGET_FS_CONFIG_GEN := $(COMMON_PATH)/config.fs", board)

    def test_vendor_aids_are_in_the_oem_range(self):
        aids = {s: int(c[s]["value"]) for s, c in ((s, config()) for s in config().sections()) if s.startswith("AID_")}
        self.assertTrue(aids)
        for name, value in aids.items():
            self.assertTrue(2900 <= value <= 2999 or 5000 <= value <= 5999, name)
        self.assertEqual(len(set(aids.values())), len(aids))

    def test_rc_users_and_groups_exist(self):
        users = {s[4:].lower() for s in config().sections() if s.startswith("AID_")}
        rcs = list((ROOT / "rootdir/etc").glob("*.rc"))
        if STOCK:
            rcs += [STOCK / p for p in self.shipped_rc_files()]
        for rc in rcs:
            for line in rc.read_text(errors="ignore").splitlines():
                m = re.match(r"\s*(user|group)\s+(.*)", line)
                if not m:
                    continue
                for name in m[2].split():
                    if name.startswith("vendor_"):
                        self.assertIn(name, users, f"{rc.name}: {line.strip()}")

    @staticmethod
    def shipped_rc_files():
        files = []
        for lst in (ROOT / "proprietary-files.txt", ROOT.parent / "android_device_xiaomi_mondrian/proprietary-files.txt"):
            if lst.is_file():
                for line in lst.read_text().splitlines():
                    path = line.split("|")[0].split(";")[0].lstrip("-")
                    if path.endswith(".rc") and (STOCK / path).is_file():
                        files.append(path)
        return files

    def test_file_entries_have_valid_fields(self):
        c = config()
        for section in c.sections():
            if section.startswith("AID_"):
                continue
            with self.subTest(path=section):
                self.assertTrue(section.startswith("vendor/"))
                self.assertRegex(c[section]["mode"], r"^0[0-7]{3}$")
                self.assertRegex(c[section]["user"], r"^AID_[A-Z_]+$")
                self.assertRegex(c[section]["group"], r"^AID_[A-Z_]+$")
                self.assertRegex(c[section]["caps"], r"^(0|[A-Z_]+( [A-Z_]+)*)$")

    @unittest.skipUnless(STOCK, "needs the stock OS3.0.8.0 vendor (MONDRIAN_STOCK_FS)")
    def test_same_as_the_stock_vendor(self):
        c = config()
        passwd = [f"{s[4:].lower()}::{c[s]['value']}:{c[s]['value']}::/:/bin/sh"
                  for s in c.sections() if s.startswith("AID_")]
        self.assertEqual(passwd, (STOCK / "vendor/etc/passwd").read_text().split())
        data = (STOCK / "vendor/etc/fs_config_files").read_bytes()
        stock, i = {}, 0
        while i < len(data):
            ln, mode, _uid, _gid, caps = struct.unpack_from("<HHHHQ", data, i)
            path = data[i + 16:i + ln].split(b"\0")[0].decode()
            if not path.startswith("system/vendor/"):
                stock[path] = (mode, caps)
            i += ln
        ours = {s: int(c[s]["mode"], 8) for s in c.sections() if not s.startswith("AID_")}
        self.assertEqual(set(ours), set(stock))
        for path, (mode, caps) in stock.items():
            self.assertEqual(ours[path], mode, path)
            self.assertEqual(c[path]["caps"] == "0", caps == 0, path)


if __name__ == "__main__":
    unittest.main()
