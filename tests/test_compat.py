# SPDX-License-Identifier: Apache-2.0
"""What the stock blobs need from the tree on Android 17.

- tools/blob_fixups.py FIXUPS name files of the proprietary lists, and the
  libraries add_needed gives them exist: AOSP libraries or the shims of
  compat/ (Android.bp).
- The stock .rc files declare HIDL interfaces that exist only as
  prebuilts; Android.bp declares them (prebuilt_hidl_interfaces) for the
  host init verifier.
"""
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from blob_fixups import FIXUPS  # noqa: E402

MONDRIAN = next((p for p in (ROOT.parent / "android_device_xiaomi_mondrian", ROOT.parent / "mondrian",
                             ROOT / ".ci/android_device_xiaomi_mondrian") if p.is_dir()), None)
STOCK = next((p for p in (Path(os.environ.get("MONDRIAN_STOCK_FS", "/nonexistent")), Path("/home/user/fw/fs"))
              if (p / "vendor/etc/init").is_dir()), None)
# AOSP libraries the fixups add (built for the vendor by Android 17).
AOSP = {"android.hardware.security.rkp-V1-ndk.so"}


def listed(path):
    return {line.split("|")[0].split(";")[0].lstrip("-") for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")}


def blueprint_names(*trees):
    names = {}
    for tree in trees:
        text = (tree / "Android.bp").read_text()
        for kind, body in re.findall(r"(?m)^(\w+) \{(.*?)^\}", text, re.S):
            name = re.search(r'name: "([^"]+)"', body)
            if name:
                names[name[1]] = (kind, body)
    return names


class FixupsTest(unittest.TestCase):
    def test_every_fixup_names_a_listed_file(self):
        files = listed(ROOT / "proprietary-files.txt")
        if MONDRIAN:
            files |= listed(MONDRIAN / "proprietary-files.txt")
        for entry in FIXUPS:
            if MONDRIAN or entry in files:  # without mondrian, its entries cannot be checked
                self.assertIn(entry, files)

    def test_added_libraries_exist(self):
        modules = blueprint_names(ROOT)
        for entry, fixups in FIXUPS.items():
            for name, *args in fixups:
                if name != "add_needed":
                    continue
                for lib in args[0]:
                    module = lib.removesuffix(".so")
                    with self.subTest(entry=entry, lib=lib):
                        if lib in AOSP:
                            continue
                        kind, body = modules[module]
                        self.assertEqual(kind, "cc_library_shared")
                        self.assertIn("vendor: true", body)
                        for src in re.findall(r'"(compat/[^"]+)"', body):
                            self.assertTrue((ROOT / src).is_file(), src)

    @unittest.skipUnless(MONDRIAN, "needs the mondrian tree")
    def test_mondrian_vendor_namespace_sees_the_shims(self):
        self.assertIn("'device/xiaomi/sm8450-common',", (MONDRIAN / "extract-files.py").read_text())


@unittest.skipUnless(STOCK and MONDRIAN, "needs the stock vendor (MONDRIAN_STOCK_FS) and the mondrian tree")
class PrebuiltHidlInterfacesTest(unittest.TestCase):
    def test_vendor_interfaces_of_the_stock_rc_files_are_declared(self):
        declared = set()
        for _name, (kind, body) in blueprint_names(ROOT, MONDRIAN).items():
            if kind == "prebuilt_hidl_interfaces":
                declared |= set(re.findall(r'"([\w.]+@\d+\.\d+::\w+)"', body))
        files = listed(ROOT / "proprietary-files.txt") | listed(MONDRIAN / "proprietary-files.txt")
        for path in sorted(f for f in files if f.endswith(".rc")):
            for line in (STOCK / path).read_text(errors="ignore").splitlines():
                m = re.match(r"\s*interface\s+([\w.]+@\d+\.\d+::\w+)", line)
                if m and m[1].startswith("vendor."):
                    self.assertIn(m[1], declared, path)


if __name__ == "__main__":
    unittest.main()
