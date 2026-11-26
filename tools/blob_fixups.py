#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fixups applied to the stock blobs after their OTA hash is checked.

The stock vendor was built for Android 12. Its AIDL clients link the NDK
backends under their Android 12 names, `<interface>-V<n>-ndk_platform.so`;
Android 17 builds the same libraries as `<interface>-V<n>-ndk.so`. The
DT_NEEDED entries are renamed in place in .dynstr (the new name is
shorter), so nothing else in the ELF moves. Only AOSP interfaces
(android.*) are renamed: the vendor's own interfaces (vendor.qti.*) ship
under their -ndk_platform names in the same proprietary lists.
"""
import re
import struct
from pathlib import Path

DT_NEEDED = 1
NDK_PLATFORM = re.compile(r"^(android\..+-V\d+)-ndk_platform\.so$")


class ElfError(ValueError):
    pass


def _layout(data):
    if data[:4] != b"\x7fELF":
        return None
    if data[5] != 1:
        raise ElfError("big-endian ELF")
    if data[4] == 2:
        return {"shoff": struct.unpack_from("<Q", data, 0x28)[0],
                "shentsize": struct.unpack_from("<H", data, 0x3A)[0],
                "shnum": struct.unpack_from("<H", data, 0x3C)[0],
                "shstrndx": struct.unpack_from("<H", data, 0x3E)[0],
                "sh": "<IIQQQQIIQQ", "dyn": "<qQ"}
    if data[4] == 1:
        return {"shoff": struct.unpack_from("<I", data, 0x20)[0],
                "shentsize": struct.unpack_from("<H", data, 0x2E)[0],
                "shnum": struct.unpack_from("<H", data, 0x30)[0],
                "shstrndx": struct.unpack_from("<H", data, 0x32)[0],
                "sh": "<IIIIIIIIII", "dyn": "<iI"}
    raise ElfError("unknown ELF class")


def _sections(data, layout):
    out = []
    for i in range(layout["shnum"]):
        name, typ, _flags, _addr, offset, size, link, _info, _align, entsize = struct.unpack_from(
            layout["sh"], data, layout["shoff"] + i * layout["shentsize"])
        out.append({"name": name, "type": typ, "offset": offset, "size": size, "link": link,
                    "entsize": entsize})
    return out


def needed(data):
    """[(offset in file, name)] of the DT_NEEDED strings of an ELF image."""
    layout = _layout(data)
    if layout is None:
        return []
    sections = _sections(data, layout)
    result = []
    for section in sections:
        if section["type"] != 6:  # SHT_DYNAMIC
            continue
        strtab = sections[section["link"]]
        size = struct.calcsize(layout["dyn"])
        for i in range(section["size"] // size):
            tag, value = struct.unpack_from(layout["dyn"], data, section["offset"] + i * size)
            if tag == 0:
                break
            if tag == DT_NEEDED:
                start = strtab["offset"] + value
                end = data.index(b"\0", start)
                result.append((start, data[start:end].decode()))
    return result


def rename_ndk_platform(path):
    """Rename the -ndk_platform DT_NEEDED entries of an ELF file in place.

    Returns the list of (old, new) names changed; non-ELF files are left alone.
    """
    path = Path(path)
    data = bytearray(path.read_bytes())
    changes = []
    for offset, name in needed(bytes(data)):
        match = NDK_PLATFORM.match(name)
        if not match:
            continue
        new = match.group(1) + "-ndk.so"
        old_len = len(name.encode())
        data[offset:offset + old_len] = new.encode() + b"\0" * (old_len - len(new.encode()))
        changes.append((name, new))
    if changes:
        path.write_bytes(bytes(data))
    return changes
