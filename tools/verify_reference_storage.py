#!/usr/bin/env python3
"""Read-only verification of pinned historical fstab conflict.

Do not use this as evidence of a bootable AOSP17 recovery.
"""
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from compare_fstab_pair import parse_fstab, compare

ROOT = Path(__file__).resolve().parents[1]


def blob_sha(data):
    header = b"blob " + str(len(data)).encode("ascii") + bytes([0])
    return hashlib.sha1(header + data).hexdigest()


def download_pinned(repo, commit, path):
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    req = Request(url, headers={"User-Agent": "PE-Reborn-Mondrian-fstab-audit"})
    with urlopen(req, timeout=30) as response:
        return response.read()


def verify():
    d = json.loads((ROOT / "storage-fstab-qualification.json").read_text(encoding="utf-8"))
    sha = d["reference_source_commit_sha"]
    sources = d["reference_sources"]
    files = {}
    for kind in ("main_fstab", "recovery_fstab"):
        source = sources[kind]
        data = download_pinned(source["repository"], sha, source["path"])
        actual = blob_sha(data)
        if actual != source["git_blob_sha"]:
            raise ValueError(f"{kind}: Git blob identity changed: {actual}")
        files[kind] = parse_fstab(data.decode("utf-8"))
        print(f"[PASS] pinned historical {kind} Git blob: {actual}")
    errors = compare(files["main_fstab"], files["recovery_fstab"])
    required = ("/system: filesystem mismatch", "/data: fileencryption policy mismatch")
    for expected in required:
        if not any(expected in error for error in errors):
            raise ValueError(f"Historical risk no longer matches evidence: {expected}")
    for e in errors:
        print(f"[EXPECTED BLOCKER] {e}")
    print("[PASS] validated historical EROFS/ext4 and FBE mismatch")
    print("[NOTE] This is only historical evidence. No active fstab or ROM image was selected.")


if __name__ == "__main__":
    try:
        verify()
    except (ValueError, OSError, UnicodeError, KeyError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
