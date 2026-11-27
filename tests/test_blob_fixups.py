"""tools/blob_fixups.py: the -ndk_platform renames and the Android 17 fixups.

add_needed and unversion_imports rewrite ELF files; besides structural
checks (those bionic's ElfReader makes), they are tested on x86-64 files
built here and loaded by the host loader, which binds the added library
and the unversioned imports for real.
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
import blob_fixups  # noqa: E402
from blob_fixups import (FIXUPS, PT_DYNAMIC, PT_LOAD, SHT_DYNAMIC, _Elf, add_needed, apply,  # noqa: E402
                         needed, regex_replace, rename_ndk_platform, unversion_imports)

CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
STOCK = [Path(p) for p in (os.environ.get("MONDRIAN_STOCK_FS", ""), "/home/user/fw/fs") if p]
STOCK = next((p for p in STOCK if (p / "vendor/lib64/libqtikeymint.so").is_file()), None)


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



def check_like_bionic(test, path):
    """What bionic's ElfReader requires of the rewritten file."""
    data = path.read_bytes()
    elf = _Elf(bytearray(data))
    phdrs = elf.phdrs()
    loads = [p for p in phdrs if p["type"] == PT_LOAD]
    test.assertEqual(loads, sorted(loads, key=lambda p: p["vaddr"]), "PT_LOAD in address order")
    for a, b in zip(loads, loads[1:]):
        test.assertLessEqual(a["vaddr"] + a["memsz"], b["vaddr"], "segments overlap")
    for p in loads:
        test.assertEqual((p["vaddr"] - p["offset"]) % p["align"], 0, "offset and address congruent")
        test.assertLessEqual(p["offset"] + p["filesz"], len(data), "segment inside the file")
    dyn = next(p for p in phdrs if p["type"] == PT_DYNAMIC)
    section = next(s for s in elf.sections() if s["type"] == SHT_DYNAMIC)
    test.assertEqual((section["offset"], section["size"]), (dyn["offset"], dyn["filesz"]),
                     ".dynamic section matches PT_DYNAMIC")
    strtab = elf.sections()[section["link"]]
    names = [elf.cstring(strtab["offset"] + v) for t, v in elf.dynamic() if t == 1]
    test.assertEqual(names, [n for _, n in needed(data)], "DT_NEEDED names through .dynstr")
    return names


@unittest.skipUnless(CC and sys.platform.startswith("linux"), "needs a C compiler and the Linux loader")
class HostLoaderTest(unittest.TestCase):
    """The rewritten files are loaded by the host loader, which binds for real."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.env = dict(os.environ, LD_LIBRARY_PATH=str(self.tmp))

    def cc(self, out, source, *flags):
        src = self.tmp / (out + ".c")
        src.write_text(source)
        subprocess.run([CC, "-o", str(self.tmp / out), str(src), *flags], check=True, cwd=self.tmp)
        return self.tmp / out

    def test_add_needed_lets_a_library_and_an_executable_bind_the_new_library(self):
        self.cc("libdep.so", "int dep_value(void) { return 42; }\n", "-shared", "-fPIC")
        lib = self.cc("libuser.so", "int dep_value(void);\nint user_value(void) { return dep_value() + 1; }\n",
                      "-shared", "-fPIC")
        loader = self.cc("loader", """
#include <dlfcn.h>
#include <stdio.h>
int main(void) {
    void *h = dlopen("libuser.so", RTLD_NOW);
    if (!h) { printf("%s\\n", dlerror()); return 1; }
    int (*f)(void) = (int (*)(void))dlsym(h, "user_value");
    printf("%d\\n", f());
    return 0;
}
""", "-ldl")
        before = subprocess.run([str(loader)], capture_output=True, text=True, env=self.env)
        self.assertNotEqual(before.returncode, 0)
        self.assertIn("dep_value", before.stdout)
        self.assertEqual(add_needed(lib, ["libdep.so"]), ["libdep.so"])
        check_like_bionic(self, lib)
        after = subprocess.run([str(loader)], capture_output=True, text=True, env=self.env)
        self.assertEqual((after.returncode, after.stdout.strip()), (0, "43"), after.stdout)
        self.assertEqual(add_needed(lib, ["libdep.so"]), [], "already needed")

        # An executable importing dep_value whose DT_NEEDED names a library
        # without it (libdeq.so), as the stock blobs import symbols that the
        # Android 17 libraries they need no longer export.
        exe = self.cc("exe", "#include <stdio.h>\nint dep_value(void);\n"
                      "int main(void) { printf(\"%d\\n\", dep_value()); return 0; }\n",
                      "-pie", "-fPIE", "-L" + str(self.tmp), "-ldep")
        self.cc("libdeq.so", "int unrelated(void) { return 0; }\n", "-shared", "-fPIC")
        exe.write_bytes(exe.read_bytes().replace(b"libdep.so\0", b"libdeq.so\0"))
        before = subprocess.run([str(exe)], capture_output=True, text=True, env=self.env)
        self.assertNotEqual(before.returncode, 0)
        self.assertIn("dep_value", before.stderr)
        add_needed(exe, ["libdep.so"])
        check_like_bionic(self, exe)
        run = subprocess.run([str(exe)], capture_output=True, text=True, env=self.env)
        self.assertEqual((run.returncode, run.stdout.strip()), (0, "42"))

    def test_unversioned_imports_bind_to_the_default_version(self):
        (self.tmp / "ver.map").write_text("VER_1 { global: f; local: *; };\n")
        self.cc("libver.so", "int f(void) { return 7; }\n", "-shared", "-fPIC",
                "-Wl,--version-script=" + str(self.tmp / "ver.map"))
        lib = self.cc("libimp.so", "int f(void);\nint g(void) { return f(); }\n", "-shared", "-fPIC",
                      "-L" + str(self.tmp), "-lver")
        syms = subprocess.run(["readelf", "--dyn-syms", "-W", str(lib)], capture_output=True, text=True).stdout
        self.assertRegex(syms, r"UND f@VER_1")
        self.assertEqual(unversion_imports(lib, "VER_1"), ["f"])
        syms = subprocess.run(["readelf", "--dyn-syms", "-W", str(lib)], capture_output=True, text=True).stdout
        self.assertNotIn("f@VER_1", syms)
        with self.assertRaises(blob_fixups.FixupError):
            unversion_imports(lib, "VER_1")
        loader = self.cc("loader2", """
#include <dlfcn.h>
#include <stdio.h>
int main(void) {
    void *h = dlopen("libimp.so", RTLD_NOW);
    if (!h) { printf("%s\\n", dlerror()); return 1; }
    printf("%d\\n", ((int (*)(void))dlsym(h, "g"))());
    return 0;
}
""", "-ldl")
        run = subprocess.run([str(loader)], capture_output=True, text=True, env=self.env)
        self.assertEqual((run.returncode, run.stdout.strip()), (0, "7"), run.stdout)


class RegexReplaceTest(unittest.TestCase):
    def test_only_the_match_changes_and_crlf_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "t.xml"
            xml.write_bytes(b'<?xml=version="1.0"?>\r\n<a b=1>\r\n</a>\r\n')
            regex_replace(xml, r"^<\?xml=version=", "<?xml version=")
            regex_replace(xml, r'(<\w+ \w+)=([0-9]+)>', r'\1="\2">')
            self.assertEqual(xml.read_bytes(), b'<?xml version="1.0"?>\r\n<a b="1">\r\n</a>\r\n')
            with self.assertRaises(blob_fixups.FixupError):
                regex_replace(xml, "absent", "x")


@unittest.skipUnless(STOCK, "needs the stock OS3.0.8.0 vendor (MONDRIAN_STOCK_FS)")
class StockBlobsTest(unittest.TestCase):
    """Every FIXUPS entry applies to the stock file, and the ELF files stay valid."""

    def test_fixups_on_the_stock_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for entry, fixups in FIXUPS.items():
                with self.subTest(entry=entry):
                    copy = Path(tmp) / entry.replace("/", "_")
                    shutil.copyfile(STOCK / entry, copy)
                    rename_ndk_platform(copy)
                    done = apply(entry, copy)
                    self.assertEqual(len(done), len(fixups))
                    for item in done:
                        self.assertTrue(item["result"], item)
                    if copy.read_bytes()[:4] == b"\x7fELF":
                        names = check_like_bionic(self, copy)
                        for name, *args in fixups:
                            if name == "add_needed":
                                self.assertLessEqual(set(args[0]), set(names))
                    else:
                        xmllint = shutil.which("xmllint")
                        if xmllint:
                            subprocess.run([xmllint, "--noout", str(copy)], check=True)

    def test_keymint_finds_the_rkp_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            for entry in ("vendor/bin/hw/android.hardware.security.keymint-service-qti",
                          "vendor/lib64/libqtikeymint.so"):
                copy = Path(tmp) / Path(entry).name
                shutil.copyfile(STOCK / entry, copy)
                rename_ndk_platform(copy)
                apply(entry, copy)
                names = [n for _, n in needed(copy.read_bytes())]
                self.assertIn("android.hardware.security.keymint-V1-ndk.so", names)
                self.assertIn("android.hardware.security.rkp-V1-ndk.so", names)


if __name__ == "__main__":
    unittest.main()
