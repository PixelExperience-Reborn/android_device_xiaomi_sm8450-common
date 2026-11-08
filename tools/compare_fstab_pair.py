#!/usr/bin/env python3
"""Fail-closed source-level fstab pairing guard for mondrian.

Validates cross-file consistency, not mount success, decryption or AVB.
No partition is accessed and no device is modified.
"""
import argparse
import sys
from pathlib import Path

CRITICAL_MOUNTS = {"/system", "/system_ext", "/product", "/vendor", "/odm", "/data", "/metadata"}
LOGICAL_MOUNTS = {"/system", "/system_ext", "/product", "/vendor", "/odm", "/vendor_dlkm"}
ENCRYPTION_KEYS = ("fileencryption", "metadata_encryption", "keydirectory")


def parse_fstab(text):
    rows = {}
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        cols = line.split()
        if len(cols) != 5:
            raise ValueError(f"line {line_number}: expected exactly 5 fields, got {len(cols)}")
        device, mount, fs_type, mount_opts, mgr = cols
        if not mount.startswith("/"):
            raise ValueError(f"line {line_number}: invalid mount point {mount!r}")
        if mount in rows:
            raise ValueError(f"line {line_number}: duplicate mount point {mount!r}")
        flags = {}
        for value in mgr.split(","):
            if not value:
                continue
            key, sep, val = value.partition("=")
            if key in flags:
                raise ValueError(f"line {line_number}: duplicate fs_mgr flag {key!r}")
            flags[key] = val if sep else None
        rows[mount] = {"device": device, "filesystem": fs_type, "options": mount_opts, "flags": flags}
    return rows


def compare(main, recovery):
    errors = []
    for mount in sorted(CRITICAL_MOUNTS):
        if mount in main and mount not in recovery:
            errors.append(f"{mount}: required recovery mount absent")
    for mount in sorted(LOGICAL_MOUNTS):
        if mount not in main or mount not in recovery:
            continue
        a, b = main[mount], recovery[mount]
        if a["filesystem"] != b["filesystem"]:
            errors.append(f"{mount}: filesystem mismatch main={a['filesystem']} recovery={b['filesystem']}")
    if "/data" in main and "/data" in recovery:
        if main["/data"]["filesystem"] != recovery["/data"]["filesystem"]:
            errors.append("/data: filesystem mismatch")
        a, b = main["/data"]["flags"], recovery["/data"]["flags"]
        for key in ENCRYPTION_KEYS:
            va, vb = a.get(key), b.get(key)
            if va != vb:
                errors.append(f"/data: {key} policy mismatch main={va!r} recovery={vb!r}")
        if "fileencryption" not in a:
            errors.append("/data: no documented main fileencryption policy")
    if "/metadata" in main and "/metadata" in recovery:
        if main["/metadata"]["filesystem"] != recovery["/metadata"]["filesystem"]:
            errors.append("/metadata: filesystem mismatch")
    if not all(x in main for x in ("/data", "/metadata")):
        errors.append("main fstab missing /data or /metadata")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_fstab", type=Path)
    parser.add_argument("recovery_fstab", type=Path)
    args = parser.parse_args()
    main_rows = parse_fstab(args.main_fstab.read_text(encoding="utf-8"))
    recovery_rows = parse_fstab(args.recovery_fstab.read_text(encoding="utf-8"))
    errors = compare(main_rows, recovery_rows)
    if errors:
        for error in errors:
            print(f"[BLOCKED] {error}", file=sys.stderr)
        return 1
    print("[PASS] static fstab pairing: no selected filesystem/encryption mismatch detected")
    print("[NOTE] This does not validate actual KeyMint, FBE, fs_mgr, image format or recovery boot")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[BLOCKED] {exc}", file=sys.stderr)
        sys.exit(1)
