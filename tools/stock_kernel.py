#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Kernel of the stock OS3.0.8.0 firmware, taken from its pinned partition images.

The stock vendor and firmware run on the Google GKI kernel of the OTA
(5.10.236-android12-9) and on its vendor modules. From the images of the
official OTA (boot, vendor_boot, dtbo, vendor_dlkm, each pinned by SHA-256
in proprietary/ota-source.json) this writes the layout BoardConfig.mk reads
as KERNEL_PATH:

  Image                  kernel of boot (header v4)
  dtbs/stock.dtb         DTBs of vendor_boot (concatenated, as in the image)
  dtbo.img               DTBO table of dtbo (without the AVB footer)
  vendor_ramdisk/        modules and module lists of the vendor_boot ramdisk
  vendor_dlkm/           modules and module lists of vendor_dlkm (EROFS)
  kernel_release         kernel release of Image

Everything is read with the standard library: boot image headers, the LZ4
legacy frames of the ramdisk, cpio (newc); fsck.erofs reads vendor_dlkm.
"""
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

PAGE_HEADER_V4 = 4096
MODULE_FILES = re.compile(r"^(.+\.ko|modules\.(load|load\.recovery|blocklist|dep|alias|softdep))$")
LZ4_LEGACY = 0x184C2102


class KernelError(ValueError):
    pass


def _align(value, page):
    return (value + page - 1) // page * page


def boot_kernel(image):
    """Kernel of a boot image of header version 3 or 4 (page size 4096)."""
    data = Path(image).read_bytes()
    if data[:8] != b"ANDROID!":
        raise KernelError(f"{image}: not an Android boot image")
    kernel_size, = struct.unpack_from("<I", data, 8)
    version, = struct.unpack_from("<I", data, 40)
    if version not in (3, 4):
        raise KernelError(f"{image}: boot header version {version}, expected 3 or 4")
    kernel = data[PAGE_HEADER_V4:PAGE_HEADER_V4 + kernel_size]
    if kernel[:2] != b"MZ" and kernel[56:60] != b"ARM\x64":
        raise KernelError(f"{image}: the kernel is not an uncompressed arm64 Image")
    return kernel


def vendor_boot_parts(image):
    """(ramdisk bytes, dtb bytes) of a vendor_boot image of header version 4."""
    data = Path(image).read_bytes()
    if data[:8] != b"VNDRBOOT":
        raise KernelError(f"{image}: not a vendor_boot image")
    version, page = struct.unpack_from("<II", data, 8)
    if version != 4:
        raise KernelError(f"{image}: vendor_boot header version {version}, expected 4")
    ramdisk_size, = struct.unpack_from("<I", data, 24)
    offset = 28 + 2048 + 4 + 16  # cmdline, tags_addr, name
    header_size, dtb_size = struct.unpack_from("<II", data, offset)
    ramdisk_offset = _align(header_size, page)
    dtb_offset = ramdisk_offset + _align(ramdisk_size, page)
    return data[ramdisk_offset:ramdisk_offset + ramdisk_size], data[dtb_offset:dtb_offset + dtb_size]


def lz4_block(src):
    """Decompress one LZ4 block."""
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        token = src[i]
        i += 1
        length = token >> 4
        if length == 15:
            while True:
                byte = src[i]
                i += 1
                length += byte
                if byte != 255:
                    break
        out += src[i:i + length]
        i += length
        if i >= n:
            break  # the last sequence has literals only
        distance = src[i] | src[i + 1] << 8
        i += 2
        if distance == 0 or distance > len(out):
            raise KernelError("corrupt LZ4 block (match distance)")
        length = token & 15
        if length == 15:
            while True:
                byte = src[i]
                i += 1
                length += byte
                if byte != 255:
                    break
        length += 4
        start = len(out) - distance
        if distance >= length:
            out += out[start:start + length]
        else:  # overlapping match: the last `distance` bytes repeat
            pattern = bytes(out[start:])
            out += (pattern * (length // distance + 1))[:length]
    return bytes(out)


def lz4_legacy(data):
    """Decompress LZ4 legacy frames (lz4 -l, the format of Android ramdisks)."""
    out = bytearray()
    i = 0
    while i + 4 <= len(data):
        magic, = struct.unpack_from("<I", data, i)
        if magic != LZ4_LEGACY:
            if not out:
                raise KernelError(f"not LZ4 legacy data (magic {magic:#x})")
            break  # padding after the last frame
        i += 4
        while i + 4 <= len(data):
            size, = struct.unpack_from("<I", data, i)
            if size == LZ4_LEGACY:
                break  # next frame
            i += 4
            out += lz4_block(data[i:i + size])
            i += size
    return bytes(out)


def cpio_files(data):
    """{path: bytes} of the regular files of cpio newc archives (concatenated)."""
    files, i = {}, 0
    while i + 110 <= len(data):
        if data[i:i + 6] != b"070701":
            if data[i] == 0:  # padding between archives
                i += 1
                continue
            raise KernelError(f"bad cpio header at {i}")
        fields = [int(data[i + 6 + 8 * k:i + 14 + 8 * k], 16) for k in range(13)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        name = data[i + 110:i + 110 + name_size - 1].decode()
        i = _align(i + 110 + name_size, 4)
        if name == "TRAILER!!!":
            i += size
            continue
        if mode & 0o170000 == 0o100000:
            files[name.lstrip("./")] = data[i:i + size]
        i = _align(i + size, 4)
    return files


def dtbo_table(image):
    """The DTBO table of a dtbo image, without the padding and AVB footer."""
    data = Path(image).read_bytes()
    magic, total = struct.unpack_from(">II", data, 0)
    if magic != 0xD7B7AB1E:
        raise KernelError(f"{image}: not a DTBO image")
    return data[:total]


def kernel_release(kernel):
    m = re.search(rb"(\d+\.\d+\.\d+-[\w.-]+) SMP", kernel) or re.search(rb"Linux version (\S+)", kernel)
    if not m:
        raise KernelError("no kernel release in Image")
    return m[1].decode()


def write_modules(files, prefix, out):
    """Write the modules and module lists under prefix (e.g. lib/modules/)."""
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for path, body in files.items():
        if path.startswith(prefix) and "/" not in path[len(prefix):] and MODULE_FILES.match(path[len(prefix):]):
            (out / path[len(prefix):]).write_bytes(body)
            count += path.endswith(".ko")
    return count


def extract(images, out):
    """Write the kernel layout (see the module docstring) from <name>.img files."""
    images, out = Path(images), Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    kernel = boot_kernel(images / "boot.img")
    (out / "Image").write_bytes(kernel)
    release = kernel_release(kernel)
    (out / "kernel_release").write_text(release + "\n")

    ramdisk, dtb = vendor_boot_parts(images / "vendor_boot.img")
    (out / "dtbs").mkdir()
    (out / "dtbs/stock.dtb").write_bytes(dtb)
    ramdisk_modules = write_modules(cpio_files(lz4_legacy(ramdisk)), "lib/modules/", out / "vendor_ramdisk")

    (out / "dtbo.img").write_bytes(dtbo_table(images / "dtbo.img"))

    if shutil.which("fsck.erofs") is None:
        raise SystemExit("fsck.erofs (erofs-utils) is required to read vendor_dlkm")
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "vendor_dlkm"
        subprocess.run(["fsck.erofs", f"--extract={tree}", str(images / "vendor_dlkm.img")], check=True,
                       stdout=subprocess.DEVNULL)
        lib = tree / "lib/modules"
        dlkm = {f"lib/modules/{p.name}": p.read_bytes() for p in lib.iterdir() if p.is_file()}
    dlkm_modules = write_modules(dlkm, "lib/modules/", out / "vendor_dlkm")

    for listing in ("vendor_ramdisk/modules.load", "vendor_ramdisk/modules.load.recovery",
                    "vendor_dlkm/modules.load"):
        for module in (out / listing).read_text().split():
            if not (out / listing).parent.joinpath(module).is_file():
                raise KernelError(f"{listing} names {module}, which the image does not ship")
    return {"kernel_release": release, "vendor_ramdisk_modules": ramdisk_modules,
            "vendor_dlkm_modules": dlkm_modules}


if __name__ == "__main__":
    import argparse
    import json
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("images", type=Path, help="directory with boot.img, vendor_boot.img, dtbo.img, vendor_dlkm.img")
    p.add_argument("out", type=Path)
    args = p.parse_args()
    print(json.dumps(extract(args.images, args.out), indent=2))
