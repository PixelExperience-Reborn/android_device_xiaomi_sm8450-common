"""Contract for the SM8475 proprietary file list, its OTA provenance and the extraction tools."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "proprietary-files.txt"
SOURCE = json.loads((ROOT / "proprietary/ota-source.json").read_text())


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


extract = load("extract_proprietary")
payload = load("ota_payload")

# Services, engines and platform files that are deliberately not taken from the OTA.
FORBIDDEN = [
    r"libmialgoengine\.so$", r"/com\.xiaomi\.plugin\.", r"campostproc", r"/camera\.xiaomi\.so$",
    r"/bin/cnd$", r"perf-hal", r"libqti-perfd", r"/bin/[^/]*dpm", r"soter", r"mlipay", r"trustedui",
    r"tui_comm", r"wfd", r"vppservice|/libvpp|/rfsa/adsp/libVpp", r"dolby", r"/bin/hw/vendor\.xiaomi\.",
    r"vendor\.qti\.hardware\.factory", r"diag-router|diag_mdlog", r"ATFWD", r"qvr", r"sxr",
    r"^vendor/etc/vintf/", r"/init\.(qcom|target)\.rc$",
]
# Built from our source repositories; a prebuilt copy would conflict with them.
# Built from source and never taken from stock: the display composer core,
# the AudioReach PAL/AGM and IPACM. For the first stable build the display
# client libraries (gralloc, mapper, metadata, config), GNSS utilities and
# the WLAN/data/Bluetooth/FM/camera interface libraries come from stock,
# where they match the other blobs; moving them to source is a later step.
SOURCE_BUILT = {
    "libsdmcore.so", "libar-pal.so", "libagm.so", "libagmclient.so", "ipacm",
    # AOSP libraries Xiaomi copied into vendor; AOSP 17 builds their vendor variants.
    "libcodec2_vndk.so", "libcodec2_hidl@1.0.so", "libcodec2_hidl_plugin.so", "libstagefright_bufferpool@2.0.1.so",
    "libavservices_minijail.so", "android.system.net.netd@1.0.so", "android.system.net.netd@1.1.so",
    "libhidltransport.so",
}


class ProprietaryList(unittest.TestCase):
    entries = extract.read_list(LIST)

    def test_entries_are_sectioned_unique_and_sorted(self):
        self.assertGreater(len(self.entries), 300)
        sections = {}
        for entry in self.entries:
            sections.setdefault(entry.section, []).append(entry.path)
        for section, paths in sections.items():
            with self.subTest(section=section):
                self.assertEqual(paths, sorted(paths))
        text = LIST.read_text()
        for header in re.findall(r"^# === (.+) ===$", text, re.M):
            following = text.split(f"# === {header} ===", 1)[1].lstrip("\n").splitlines()[0]
            self.assertTrue(following.startswith("# "), f"section {header} lacks a reason line")

    def test_nothing_excluded_or_built_from_source_is_listed(self):
        for entry in self.entries:
            with self.subTest(path=entry.path):
                for pattern in FORBIDDEN:
                    self.assertIsNone(re.search(pattern, entry.path), pattern)
                self.assertNotIn(Path(entry.path).name, SOURCE_BUILT)
                self.assertNotRegex(Path(entry.path).name, r"^audio\.primary\.")

    def test_header_names_the_pinned_ota(self):
        head = LIST.read_text().split("# ===", 1)[0]
        fingerprint, _, version = SOURCE["ota"]["post_build"].split(":user")[0].rpartition("/")
        self.assertIn(fingerprint, head)
        self.assertIn(version, head)
        self.assertIn("not redistributed", head)

    def test_gpu_firmware_matches_kernel_requests(self):
        paths = {e.path for e in self.entries}
        for name in ("a730_sqe.fw", "gmu_gen70000.bin", "a730_zap.mdt", "vpu20_4v.mdt", "evass.mdt"):
            self.assertIn("vendor/firmware/" + name, paths)


class OtaSource(unittest.TestCase):
    def test_pinned_provenance(self):
        ota, vendor = SOURCE["ota"], SOURCE["partitions"]["vendor"]
        self.assertTrue(all(u.startswith("https://") and u.endswith(ota["file"]) for u in ota["urls"]))
        self.assertGreaterEqual(len(ota["urls"]), 2)
        self.assertRegex(ota["payload_metadata"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(vendor["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(vendor["board_api_level"], 31)
        for name, part in SOURCE["partitions"].items():
            self.assertRegex(part["sha256"], r"^[0-9a-f]{64}$", name)
            self.assertEqual(part["filesystem"], "erofs", name)
        self.assertIn("OS3.0.8.0.VMNCNXM", ota["post_build"])
        self.assertIn("mondrian", vendor["build_fingerprint"])


class Tools(unittest.TestCase):
    def test_read_list_rejects_malformed_and_duplicate_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "list.txt"
            for body in ("vendor/a|" + "0" * 64 + "\n",                           # before a section
                         "# === S ===\n# why\nvendor/a|xyz\n",                      # bad hash
                         "# === S ===\n# why\nvendor/a|" + "0" * 64 + "\nvendor/a|" + "1" * 64 + "\n"):
                bad.write_text(body)
                with self.assertRaises(extract.ListError):
                    extract.read_list(bad)

    def test_extract_copies_verified_files_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            vendor = tmp / "vendor"
            (vendor / "lib64").mkdir(parents=True)
            (vendor / "lib64/libx.so").write_bytes(b"x")
            (vendor / "etc").mkdir()
            (vendor / "etc/y.conf").write_bytes(b"y")
            digest = lambda b: hashlib.sha256(b).hexdigest()
            lst = tmp / "list.txt"
            odm = tmp / "odm"
            (odm / "lib64").mkdir(parents=True)
            (odm / "lib64/libz.so").write_bytes(b"z")
            lst.write_text(f"# === S ===\n# why\nodm/lib64/libz.so|{digest(b'z')}\n"
                           f"vendor/etc/y.conf|{digest(b'y')}\nvendor/lib64/libx.so|{digest(b'x')}\n")
            out = tmp / "out"
            cmd = [sys.executable, "-I", str(ROOT / "tools/extract_proprietary.py"),
                   "--vendor-dir", str(vendor), "--odm-dir", str(odm), "--list", f"{lst}={out}"]
            subprocess.run(cmd + ["--verify-only"], check=True, capture_output=True)
            self.assertFalse(out.exists())
            subprocess.run(cmd, check=True, capture_output=True)
            self.assertEqual((out / "proprietary/vendor/lib64/libx.so").read_bytes(), b"x")
            self.assertEqual((out / "proprietary/odm/lib64/libz.so").read_bytes(), b"z")
            self.assertEqual(json.loads((out / "proprietary/provenance.json").read_text())["files"], 3)
            (vendor / "lib64/libx.so").write_bytes(b"changed")
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("hash mismatch: vendor/lib64/libx.so", result.stdout)

    def test_manifest_parser(self):
        def varint(n):
            out = b""
            while True:
                byte, n = n & 0x7F, n >> 7
                out += bytes([byte | (0x80 if n else 0)])
                if not n:
                    return out

        def field(number, value):
            if isinstance(value, int):
                return varint(number << 3) + varint(value)
            return varint(number << 3 | 2) + varint(len(value)) + value

        extent = field(1, 5) + field(2, 2)
        op = field(1, payload.REPLACE_XZ) + field(2, 100) + field(3, 30) + field(6, extent) + field(8, b"\xab" * 32)
        info = field(1, 8192) + field(2, b"\xcd" * 32)
        part = field(1, b"vendor") + field(7, info) + field(8, op)
        block, parts = payload.parse_manifest(field(3, 4096) + field(13, part))
        self.assertEqual(block, 4096)
        vendor = parts["vendor"]
        self.assertEqual((vendor["size"], vendor["hash"]), (8192, "cd" * 32))
        self.assertEqual(vendor["ops"], [{"type": payload.REPLACE_XZ, "offset": 100, "length": 30,
                                          "dst": [(5, 2)], "sha256": "ab" * 32}])


if __name__ == "__main__":
    unittest.main()
