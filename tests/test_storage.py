# SPDX-License-Identifier: Apache-2.0
"""Internal storage and the update package stay compatible with stock HyperOS
and with recoveries built for it (official OrangeFox fox_16.0).

- /data is formatted by whoever wipes it: stock recovery, OrangeFox or ours.
  The ROM must expect the same f2fs features as all of them: casefolding and
  project quotas, without sdcardfs (stock vendor build.prop and OrangeFox's
  device-common.mk both inherit emulated_storage.mk). A ROM expecting other
  features cannot prepare /data/media: "internal storage unavailable".
- Android 17's casefolding remover (ro.casefolding.original_folder) moves
  folders between filesystems with different features; it is not used.
- A full OTA must keep REPLACE/REPLACE_XZ operations: REPLACE_ZSTD (Android
  17 update_engine, minor version 10) is unknown to the Android 16
  update_engine of OrangeFox, which would refuse to install the ROM.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The stock vendor build.prop of OS3.0.8.0.VMNCNXM sets exactly these.
STOCK_STORAGE = {
    "external_storage.projid.enabled": "1",
    "external_storage.casefold.enabled": "1",
    "external_storage.sdcardfs.enabled": "0",
}


def code(path):
    return "\n".join(line.split("#", 1)[0] for line in path.read_text().splitlines())


def sibling(*names):
    for base in (ROOT.parent, ROOT / ".ci"):
        for name in names:
            if (base / name).is_dir():
                return base / name
    return None


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.common = code(ROOT / "common.mk")

    def test_emulated_storage_like_stock(self):
        # emulated_storage.mk sets the three properties above in vendor.
        self.assertRegex(self.common, r"inherit-product, \$\(SRC_TARGET_DIR\)/product/emulated_storage\.mk\)")
        texts = [code(p) for p in ROOT.glob("*.mk")] + [code(p) for p in ROOT.glob("*.prop")]
        mondrian = sibling("mondrian", "android_device_xiaomi_mondrian")
        if mondrian:
            texts += [code(p) for p in mondrian.glob("*.mk")] + [code(p) for p in mondrian.glob("*.prop")]
        for text in texts:
            for prop, value in STOCK_STORAGE.items():
                for m in re.finditer(rf"{re.escape(prop)}=(\w+)", text):
                    self.assertEqual(m[1], value, prop)
            self.assertNotRegex(text, r"(?m)^\s*PRODUCT_(QUOTA_PROJID|FS_CASEFOLD)\s*:?=\s*(0|false)?\s*$")
            self.assertNotIn("ro.casefolding.original_folder", text)
            self.assertNotIn("sdcardfs.enabled=1", text)

    def test_full_ota_without_replace_zstd(self):
        for path in list(ROOT.glob("*.mk")) + list(ROOT.glob("tools/*")):
            if path.is_file():
                self.assertNotIn("enable_replace_zstd", path.read_text(errors="ignore"), str(path))


if __name__ == "__main__":
    unittest.main()
