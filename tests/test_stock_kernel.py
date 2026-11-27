# SPDX-License-Identifier: Apache-2.0
"""tools/stock_kernel.py: the stock kernel layout from the OTA images.

The LZ4 legacy decoder and the cpio reader are checked against the lz4 tool
and synthetic archives; with the stock images (MONDRIAN_STOCK_IMAGES) the
whole layout is checked against what the stock vendor_boot holds.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import stock_kernel  # noqa: E402

IMAGES = next((p for p in (Path(os.environ.get("MONDRIAN_STOCK_IMAGES", "/nonexistent")), Path("/home/user/fw/images"))
               if (p / "vendor_boot.img").is_file()), None)


def cpio(entries):
    out = bytearray()
    for name, body, mode in entries + [("TRAILER!!!", b"", 0)]:
        name_bytes = name.encode() + b"\0"
        fields = [0, mode, 0, 0, 1, 0, len(body), 0, 0, 0, 0, len(name_bytes), 0]
        out += b"070701" + b"".join(b"%08X" % f for f in fields) + name_bytes
        out += b"\0" * (-len(out) % 4) + body
        out += b"\0" * (-len(out) % 4)
    return bytes(out)


class StockKernelTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lz4"), "needs the lz4 tool")
    def test_lz4_legacy_matches_the_lz4_tool(self):
        payload = (b"lib/modules/foo.ko\0" * 5000) + os.urandom(70000) + bytes(300000) + b"tail" * 999
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.write_bytes(payload)
            for level in ("-1", "-9"):
                packed = subprocess.run(["lz4", "-l", level, "-c", str(raw)], check=True,
                                        capture_output=True).stdout
                self.assertEqual(stock_kernel.lz4_legacy(packed), payload, level)

    def test_cpio_keeps_regular_files_only(self):
        archive = cpio([("lib", b"", 0o040755), ("lib/modules/a.ko", b"A" * 5, 0o100644),
                        ("lib/modules/modules.load", b"a.ko\n", 0o100644), ("init", b"x", 0o120777)])
        files = stock_kernel.cpio_files(archive + bytes(8) + cpio([("first_stage.prop", b"p", 0o100644)]))
        self.assertEqual(files, {"lib/modules/a.ko": b"A" * 5, "lib/modules/modules.load": b"a.ko\n",
                                 "first_stage.prop": b"p"})

    def test_dtbo_table_drops_the_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            dtbo = Path(tmp) / "dtbo.img"
            table = struct.pack(">II", 0xD7B7AB1E, 64) + bytes(56)
            dtbo.write_bytes(table + bytes(4096) + b"AVBf")
            self.assertEqual(stock_kernel.dtbo_table(dtbo), table)

    @unittest.skipUnless(IMAGES and shutil.which("fsck.erofs"), "needs the stock images and fsck.erofs")
    def test_layout_from_the_stock_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = stock_kernel.extract(IMAGES, Path(tmp) / "kernel")
            out = Path(tmp) / "kernel"
            self.assertRegex(info["kernel_release"], r"^5\.10\.236-android12-9-")
            self.assertEqual(info["vendor_ramdisk_modules"], 354)
            self.assertEqual(info["vendor_dlkm_modules"], 309)
            self.assertEqual((out / "Image").read_bytes()[56:60], b"ARM\x64")
            self.assertEqual((out / "dtbs/stock.dtb").read_bytes()[:4], bytes.fromhex("d00dfeed"))
            for module in ("q6_pdr_dlkm.ko", "adsp_loader_dlkm.ko"):
                self.assertTrue((out / "vendor_dlkm" / module).is_file())


if __name__ == "__main__":
    unittest.main()
