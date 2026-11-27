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

FIXUPS lists what else single blobs need on Android 17 (add_needed,
unversion_imports, regex_replace); apply() runs them on a copied file.
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


# --- ELF rewriting -----------------------------------------------------------

PT_LOAD, PT_DYNAMIC, PT_NOTE = 1, 2, 4
PF_W, PF_R = 2, 4
SHT_STRTAB, SHT_DYNAMIC, SHT_DYNSYM = 3, 6, 11
SHT_GNU_VERNEED, SHT_GNU_VERSYM = 0x6FFFFFFE, 0x6FFFFFFF
DT_NULL, DT_STRTAB, DT_STRSZ = 0, 5, 10
SHN_UNDEF = 0
VER_NDX_GLOBAL = 1


class FixupError(ValueError):
    pass


def _align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


class _Elf:
    """Program headers, section headers and dynamic table of a little-endian ELF."""

    def __init__(self, data):
        if data[:4] != b"\x7fELF":
            raise ElfError("not an ELF file")
        if data[5] != 1:
            raise ElfError("big-endian ELF")
        self.data = data
        if data[4] == 2:
            self.phoff, self.shoff = struct.unpack_from("<QQ", data, 0x20)
            self.phentsize, self.phnum, self.shentsize, self.shnum = struct.unpack_from("<HHHH", data, 0x36)
            self.ph = ("<IIQQQQQQ", ("type", "flags", "offset", "vaddr", "paddr", "filesz", "memsz", "align"))
            self.sh_fmt, self.dyn_fmt = "<IIQQQQIIQQ", "<qQ"
            self.sym = ("<IBBHQQ", 0, 3)  # format, index of st_name, index of st_shndx
        elif data[4] == 1:
            self.phoff, self.shoff = struct.unpack_from("<II", data, 0x1C)
            self.phentsize, self.phnum, self.shentsize, self.shnum = struct.unpack_from("<HHHH", data, 0x2A)
            self.ph = ("<IIIIIIII", ("type", "offset", "vaddr", "paddr", "filesz", "memsz", "flags", "align"))
            self.sh_fmt, self.dyn_fmt = "<IIIIIIIIII", "<iI"
            self.sym = ("<IIIBBH", 0, 5)
        else:
            raise ElfError("unknown ELF class")

    def phdrs(self):
        fmt, names = self.ph
        return [dict(zip(names, struct.unpack_from(fmt, self.data, self.phoff + i * self.phentsize)))
                for i in range(self.phnum)]

    def write_phdrs(self, phdrs):
        fmt, names = self.ph
        for i, ph in enumerate(phdrs):
            struct.pack_into(fmt, self.data, self.phoff + i * self.phentsize, *(ph[n] for n in names))

    _SH = ("name", "type", "flags", "addr", "offset", "size", "link", "info", "addralign", "entsize")

    def sections(self):
        return [dict(zip(self._SH, struct.unpack_from(self.sh_fmt, self.data, self.shoff + i * self.shentsize)))
                for i in range(self.shnum)]

    def write_section(self, index, section):
        struct.pack_into(self.sh_fmt, self.data, self.shoff + index * self.shentsize,
                         *(section[n] for n in self._SH))

    def offset_of(self, vaddr):
        for ph in self.phdrs():
            if ph["type"] == PT_LOAD and ph["vaddr"] <= vaddr < ph["vaddr"] + ph["filesz"]:
                return ph["offset"] + vaddr - ph["vaddr"]
        raise ElfError(f"address {vaddr:#x} is not in a loaded segment")

    def dynamic(self):
        """[(tag, value)] of PT_DYNAMIC up to and including DT_NULL."""
        ph = next((p for p in self.phdrs() if p["type"] == PT_DYNAMIC), None)
        if ph is None:
            raise ElfError("no PT_DYNAMIC")
        size = struct.calcsize(self.dyn_fmt)
        entries = []
        for i in range(ph["filesz"] // size):
            tag, value = struct.unpack_from(self.dyn_fmt, self.data, ph["offset"] + i * size)
            entries.append((tag, value))
            if tag == DT_NULL:
                return entries
        raise ElfError("PT_DYNAMIC has no DT_NULL")

    def cstring(self, offset):
        return bytes(self.data[offset:self.data.index(b"\0", offset)]).decode()


def add_needed(path, libraries):
    """Add DT_NEEDED entries to an ELF file, after its own ones.

    The stock blobs have no spare dynamic entry, so, as patchelf does, the
    file gets a new read-write PT_LOAD segment at its end holding the
    string table (the old one plus the new names, so every old offset
    stays valid) and the dynamic table (the old one plus the new entries).
    PT_DYNAMIC, DT_STRTAB, DT_STRSZ and the .dynamic and .dynstr section
    headers point to them: bionic's ElfReader checks that .dynamic matches
    PT_DYNAMIC and reads the DT_NEEDED names through .dynstr. The program
    header of the segment replaces the last PT_NOTE (the notes stay in the
    file and in their section headers) and follows the other PT_LOAD
    entries, which the kernel and the linker expect in address order.
    Returns the names added.
    """
    path = Path(path)
    elf = _Elf(bytearray(path.read_bytes()))
    entries = elf.dynamic()
    values = dict(entries)
    old_strtab_vaddr, old_strsz = values[DT_STRTAB], values[DT_STRSZ]
    strtab_offset = elf.offset_of(old_strtab_vaddr)
    present = {elf.cstring(strtab_offset + v) for t, v in entries if t == DT_NEEDED}
    new = [lib for lib in libraries if lib not in present]
    if not new:
        return []

    strtab = bytearray(elf.data[strtab_offset:strtab_offset + old_strsz])
    added = []
    for lib in new:
        added.append((DT_NEEDED, len(strtab)))
        strtab += lib.encode() + b"\0"

    phdrs = elf.phdrs()
    loads = [p for p in phdrs if p["type"] == PT_LOAD]
    alignment = max([0x1000] + [p["align"] for p in loads])
    seg_vaddr = _align(max(p["vaddr"] + p["memsz"] for p in loads), alignment)
    seg_offset = _align(len(elf.data), alignment)
    dyn_rel = _align(len(strtab), 8)

    last_needed = max((i for i, (t, _) in enumerate(entries) if t == DT_NEEDED), default=-1)
    entries = entries[:last_needed + 1] + added + entries[last_needed + 1:]
    entries = [(t, seg_vaddr if t == DT_STRTAB else len(strtab) if t == DT_STRSZ else v) for t, v in entries]
    dynamic = b"".join(struct.pack(elf.dyn_fmt, t, v) for t, v in entries)
    segment = bytes(strtab) + b"\0" * (dyn_rel - len(strtab)) + dynamic

    notes = [i for i, p in enumerate(phdrs) if p["type"] == PT_NOTE]
    if not notes:
        raise FixupError(f"{path.name}: no PT_NOTE program header to reuse for the new segment")
    del phdrs[notes[-1]]
    last_load = max(i for i, p in enumerate(phdrs) if p["type"] == PT_LOAD)
    phdrs.insert(last_load + 1, {"type": PT_LOAD, "flags": PF_R | PF_W, "offset": seg_offset,
                                 "vaddr": seg_vaddr, "paddr": seg_vaddr, "filesz": len(segment),
                                 "memsz": len(segment), "align": alignment})
    for ph in phdrs:
        if ph["type"] == PT_DYNAMIC:
            ph.update(offset=seg_offset + dyn_rel, vaddr=seg_vaddr + dyn_rel, paddr=seg_vaddr + dyn_rel,
                      filesz=len(dynamic), memsz=len(dynamic))
    elf.write_phdrs(phdrs)

    moved = set()
    for index, section in enumerate(elf.sections()):
        if section["type"] == SHT_DYNAMIC:
            section.update(offset=seg_offset + dyn_rel, addr=seg_vaddr + dyn_rel, size=len(dynamic))
        elif section["type"] == SHT_STRTAB and section["addr"] == old_strtab_vaddr and old_strtab_vaddr:
            section.update(offset=seg_offset, addr=seg_vaddr, size=len(strtab))
        else:
            continue
        moved.add(section["type"])
        elf.write_section(index, section)
    if moved != {SHT_DYNAMIC, SHT_STRTAB}:
        raise FixupError(f"{path.name}: .dynamic or .dynstr section header not found")

    elf.data += b"\0" * (seg_offset - len(elf.data)) + segment
    path.write_bytes(bytes(elf.data))
    return new


def unversion_imports(path, version):
    """Make the imports bound to a symbol version unversioned (index global).

    For blobs linked against a library that Android 17 builds unversioned for
    the vendor (LLNDK `unversioned: true`, e.g. libnativewindow, version
    LIBNATIVEWINDOW): the build checks the imports against that unversioned
    stub, and at run time an unversioned import binds to the default
    version of the symbol in the real library. Returns the symbols changed.
    """
    path = Path(path)
    elf = _Elf(bytearray(path.read_bytes()))
    sections = elf.sections()
    dynsym = next(s for s in sections if s["type"] == SHT_DYNSYM)
    versym = next((s for s in sections if s["type"] == SHT_GNU_VERSYM), None)
    verneed = next((s for s in sections if s["type"] == SHT_GNU_VERNEED), None)
    if versym is None or verneed is None:
        raise FixupError(f"{path.name}: no symbol versions")
    strings = sections[verneed["link"]]["offset"]
    indexes, need = set(), verneed["offset"]
    for _ in range(verneed["info"]):  # sh_info: number of Verneed entries
        _ver, count, _file, aux, nxt = struct.unpack_from("<HHIII", elf.data, need)
        entry = need + aux
        for _ in range(count):
            _hash, _flags, other, name, aux_next = struct.unpack_from("<IHHII", elf.data, entry)
            if elf.cstring(strings + name) == version:
                indexes.add(other)
            entry += aux_next
        need += nxt
    names = sections[dynsym["link"]]["offset"]
    fmt, name_index, _ = elf.sym
    changed = []
    for i in range(dynsym["size"] // dynsym["entsize"]):
        offset = versym["offset"] + 2 * i
        if struct.unpack_from("<H", elf.data, offset)[0] & 0x7FFF in indexes:
            struct.pack_into("<H", elf.data, offset, VER_NDX_GLOBAL)
            fields = struct.unpack_from(fmt, elf.data, dynsym["offset"] + i * dynsym["entsize"])
            changed.append(elf.cstring(names + fields[name_index]))
    if not changed:
        raise FixupError(f"{path.name}: no import bound to {version}")
    path.write_bytes(bytes(elf.data))
    return changed


def regex_replace(path, pattern, replacement):
    """re.sub on a text file; the pattern must match, so a changed file is noticed.

    The file is read and written as bytes (latin-1), so line endings and
    everything the pattern does not match stay as they are.
    """
    path = Path(path)
    text, count = re.subn(pattern, replacement, path.read_bytes().decode("latin-1"), flags=re.M)
    if not count:
        raise FixupError(f"{path.name}: no match for {pattern!r}")
    path.write_bytes(text.encode("latin-1"))
    return count


# --- What the stock files need on Android 17 ---------------------------------

FIXUPS = {
    # KeyMint: Android 14 moved IRemotelyProvisionedComponent out of the
    # keymint AIDL library into android.hardware.security.rkp; keymint-V1
    # does not import it, so the stock service would not load without it.
    "vendor/bin/hw/android.hardware.security.keymint-service-qti": [
        ("add_needed", ["android.hardware.security.rkp-V1-ndk.so"])],
    "vendor/lib64/libqtikeymint.so": [("add_needed", ["android.hardware.security.rkp-V1-ndk.so"])],
    # Camera: SetTaskProfiles had C linkage before Android 14;
    # libprocessgroup_shim (compat/) exports it.
    "vendor/lib64/libcamxcommonutils.so": [("add_needed", ["libprocessgroup_shim.so"])],
    "vendor/lib64/hw/com.qti.chi.override.so": [("add_needed", ["libprocessgroup_shim.so"])],
    # Camera: libnativewindow is unversioned for the vendor on Android 17.
    **{f"vendor/lib64/{lib}": [("unversion_imports", "LIBNATIVEWINDOW")]
       for lib in ("libMiVideoFilter.so", "libTrueSight.so", "libalLDC.so", "libalhLDC.so")},
    # XML the build checks with xmllint: a broken declaration and unquoted
    # numeric attributes in the stock camera tuning files.
    **{f"vendor/etc/camera/{xml}": [("regex_replace", r"^<\?xml=version=", "<?xml version=")]
       for xml in ("mondrian_motiontuning.xml", "mondrian_enhance_motiontuning.xml")},
    "vendor/etc/camera/pureView_parameter.xml": [("regex_replace", r'(<\w+ \w+)=([0-9]+)>', r'\1="\2">')],
    # Codec list: AOSP declares its software codecs itself (media swcodec
    # APEX); these Xiaomi copies are not installed, and an Include of a
    # missing file fails the parse of the codec list.
    "vendor/etc/media_codecs_cape.xml": [
        ("regex_replace", r'^[ \t]*<Include href="media_codecs_google_(audio|c2|telephony)\.xml" ?/>\r?\n', "")],
}

_OPERATIONS = {"add_needed": add_needed, "unversion_imports": unversion_imports,
               "regex_replace": regex_replace}


def apply(entry, path):
    """Run the FIXUPS of a list entry (e.g. vendor/lib64/libfoo.so) on its copy."""
    done = []
    for name, *args in FIXUPS.get(entry, []):
        result = _OPERATIONS[name](path, *args)
        done.append({"fixup": name, "args": args, "result": result})
    return done
