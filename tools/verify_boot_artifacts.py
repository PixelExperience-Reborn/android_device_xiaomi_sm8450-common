#!/usr/bin/env python3
"""Validate final mondrian AOSP17 flashable image set, never a bare Image.

Use on a *completed* device build output, not a standalone kernel output.
Checks Android boot/vendor_boot/DTBO/AVB signatures and partition size
bounds. This is a preliminary format check, NOT cryptographic AVB
verification, bootloader compatibility, firmware provenance, or boot test.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

REQUIRED = ("boot.img", "dtbo.img", "vendor_boot.img",
            "recovery.img", "vendor_dlkm.img", "vbmeta.img", "vbmeta_system.img")
MAX_SIZE = {
    "boot.img": 0x0C000000,
    "dtbo.img": 0x01800000,
    "vendor_boot.img": 0x06000000,
    "recovery.img": 0x06400000,
}
DTBO_MAGIC = 0xD7B7AB1E


def require(ok, message):
    if not ok:
        raise ValueError(message)


def u32_le(data, offset):
    require(len(data) >= offset + 4, f"short image header at offset {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def verify_android_boot(header, name):
    require(header[:8] == b"ANDROID!", f"{name}: not an Android boot image")
    kernel_bytes = u32_le(header, 8)
    header_size = u32_le(header, 20)
    version = u32_le(header, 40)
    require(version == 4, f"{name}: expected header v4, got {version}")
    require(header_size >= 44, f"{name}: invalid Android boot header size")
    if name == "boot.img":
        require(kernel_bytes > 0, "boot.img contains no kernel")
    # A separate recovery.img may be ramdisk-only for some layouts;
    # do not assume the kernel must be embedded in recovery.


def verify_vendor_boot(header):
    require(header[:8] == b"VNDRBOOT", "vendor_boot.img: invalid vendor_boot magic")
    require(u32_le(header, 8) == 4, "vendor_boot.img: expected header v4")
    page_size = u32_le(header, 12)
    require(page_size == 4096, f"vendor_boot.img: unexpected page size {page_size}")


def verify_dtbo(header, file_size):
    require(len(header) >= 32, "dtbo.img: truncated DT table header")
    magic, total, hsize, entry_size, count, offset, page_size, version = (
        struct.unpack_from(">8I", header, 0)
    )
    require(magic == DTBO_MAGIC, "dtbo.img: not an Android DTBO table")
    require(hsize >= 32 and total <= file_size and total >= hsize,
            "dtbo.img: invalid size/offset header")
    require(1 <= count <= 1024, "dtbo.img: no DTBO entries or unreasonable entry count")
    require(entry_size >= 32 and offset >= hsize and
            offset + entry_size * count <= total,
            "dtbo.img: inconsistent entry offsets")
    require(page_size == 4096, "dtbo.img: unsupported DTBO page size")
    require(version in (0, 1), f"dtbo.img: unknown table format version {version}")


def validate(directory):
    require(directory.is_dir(), f"missing build output directory: {directory}")
    report = {"device": "mondrian", "boot_header_version": 4,
              "format_checked_not_boot_verified": True, "images": {}}
    for name in REQUIRED:
        path = directory / name
        require(path.is_file(), f"missing {name}: Image alone is NOT a bootable output")
        size = path.stat().st_size
        require(size > 0, f"{name}: empty image")
        if name in MAX_SIZE:
            require(size <= MAX_SIZE[name],
                    f"{name}: {size} bytes exceeds partition limit {MAX_SIZE[name]}")
        with path.open("rb") as f:
            head = f.read(4096)
        if name in ("boot.img", "recovery.img"):
            verify_android_boot(head, name)
        elif name == "vendor_boot.img":
            verify_vendor_boot(head)
        elif name == "dtbo.img":
            verify_dtbo(head, size)
        elif name in ("vbmeta.img", "vbmeta_system.img"):
            require(head[:4] == b"AVB0", f"{name}: missing AVB vbmeta header")
        report["images"][name] = {"bytes": size, "present": True, "format_ok": True}
    print("[PASS] boot.img + dtbo.img + vendor_boot.img + recovery.img + vendor_dlkm.img + AVB images")
    print("[NOTE] no signature verification or physical boot is implied")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_directory", type=Path,
                        help="e.g. out/target/product/mondrian; not the kernel output directory")
    parser.add_argument("--json", type=Path, help="optional output report")
    args = parser.parse_args()
    report = validate(args.image_directory)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
