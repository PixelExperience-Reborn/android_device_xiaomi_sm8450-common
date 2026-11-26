"""tools/blob_fixups.py renames only AOSP -ndk_platform DT_NEEDED entries."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from blob_fixups import needed, rename_ndk_platform  # noqa: E402


def elf64(names):
    """Minimal ELF64 LE with .dynstr, .dynamic (DT_NEEDED per name) and .shstrtab."""
    dynstr = b"\0" + b"".join(n.encode() + b"\0" for n in names)
    offsets, pos = [], 1
    for n in names:
        offsets.append(pos)
        pos += len(n.encode()) + 1
    dynamic = b"".join(struct.pack("<qQ", 1, o) for o in offsets) + struct.pack("<qQ", 0, 0)
    shstrtab = b"\0.dynstr\0.dynamic\0.shstrtab\0"
    dynstr_off = 64
    dynamic_off = (dynstr_off + len(dynstr) + 7) & ~7
    shstr_off = dynamic_off + len(dynamic)
    sh_off = (shstr_off + len(shstrtab) + 7) & ~7
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x28, sh_off)
    struct.pack_into("<HHH", header, 0x3A, 64, 4, 3)
    sh = b"\0" * 64
    sh += struct.pack("<IIQQQQIIQQ", 1, 3, 0, 0, dynstr_off, len(dynstr), 0, 0, 1, 0)
    sh += struct.pack("<IIQQQQIIQQ", 9, 6, 0, 0, dynamic_off, len(dynamic), 1, 0, 8, 16)
    sh += struct.pack("<IIQQQQIIQQ", 18, 3, 0, 0, shstr_off, len(shstrtab), 0, 0, 1, 0)
    data = bytearray(header) + dynstr
    data += b"\0" * (dynamic_off - len(data)) + dynamic + shstrtab
    data += b"\0" * (sh_off - len(data)) + sh
    return bytes(data)


class BlobFixupsTest(unittest.TestCase):
    def test_aosp_ndk_platform_names_become_ndk_and_vendor_names_stay(self):
        names = ["libc.so", "android.hardware.security.keymint-V1-ndk_platform.so",
                 "vendor.qti.hardware.radio.ims-V7-ndk_platform.so"]
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "libtest.so"
            blob.write_bytes(elf64(names))
            size = blob.stat().st_size
            changes = rename_ndk_platform(blob)
            self.assertEqual(changes, [("android.hardware.security.keymint-V1-ndk_platform.so",
                                        "android.hardware.security.keymint-V1-ndk.so")])
            self.assertEqual([n for _, n in needed(blob.read_bytes())],
                             ["libc.so", "android.hardware.security.keymint-V1-ndk.so",
                              "vendor.qti.hardware.radio.ims-V7-ndk_platform.so"])
            self.assertEqual(blob.stat().st_size, size)

    def test_non_elf_files_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "gps.conf"
            conf.write_text("android.hardware.gnss-V1-ndk_platform.so\n")
            self.assertEqual(rename_ndk_platform(conf), [])
            self.assertIn("ndk_platform", conf.read_text())


if __name__ == "__main__":
    unittest.main()
