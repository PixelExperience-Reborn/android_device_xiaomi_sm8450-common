#!/usr/bin/env python3
"""Source-only, fail-closed snapshot audit for mondrian boot partition data.

--online revalidates immutable public reference files and reports differences.
This cannot determine actual GPT sizes, vendor_boot layout or boot compatibility.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "boot-partition-qualification.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
FIELD_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*:?=\s*(.*?)\s*$")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def parse_assignments(source):
    result = {}
    for line in source.splitlines():
        cleaned = line.split("#", 1)[0].rstrip()
        match = FIELD_RE.match(cleaned)
        if match:
            key, val = match.groups()
            require(key not in result, "duplicate Make assignment: " + key)
            result[key] = val
    return result


def parse_ab_partitions(source):
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^AB_OTA_PARTITIONS\s*\+=\s*", line):
            block = []
            current = line.split("+=", 1)[1]
            pos = i
            while True:
                payload = current.split("#", 1)[0].strip()
                cont = payload.endswith("\\")
                if cont:
                    payload = payload[:-1].strip()
                if payload:
                    block.extend(payload.split())
                if not cont:
                    return block
                pos += 1
                require(pos < len(lines), "unterminated AB_OTA_PARTITIONS")
                current = lines[pos]
    raise ValueError("missing AB_OTA_PARTITIONS")


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data).hexdigest()


def load():
    d = json.loads(PROFILE.read_text(encoding="utf-8"))
    require(d["schema_version"] == 1, "wrong profile schema")
    require(d["device"] == "mondrian" and d["soc"] == "SM8475", "wrong target")
    require(d["qualification"] == "reference_only_unselected", "source promoted without build")
    require(len(d["references"]) == 2, "reference count changed")
    for r in d["references"]:
        for key in ("commit", "root_tree", "blob"):
            require(SHA.fullmatch(r[key]) is not None, f"bad SHA: {r['repo']} {key}")
    fields = d["matching_reference_fields"]
    require(fields["BOARD_BOOT_HEADER_VERSION"] == 4, "invalid boot header")
    require(fields["BOARD_KERNEL_PAGESIZE"] == 4096, "invalid kernel page size reference")
    require(fields["BOARD_SUPER_PARTITION_SIZE"] - fields["BOARD_QTI_DYNAMIC_PARTITIONS_SIZE"] ==
            d["super_metadata_reserve_bytes"] == 4 * 1024 * 1024,
            "dynamic super metadata reserve mismatch")
    require(len(d["dynamic_partition_names"]) == len(set(d["dynamic_partition_names"])),
            "duplicate dynamic partitions")
    require(not any(d["release_gates"].values()), "release status promoted without verification")
    require(not d["filesystem_decision"]["selected_for_production"],
            "filesystem selected without validated images")
    active = parse_assignments((ROOT / "BoardConfigCommon.mk").read_text(encoding="utf-8"))
    disallowed = set(fields) | {"BOARD_AVB_ENABLE",
                               "BOARD_RECOVERY_FSTAB",
                               "TARGET_RECOVERY_FSTAB", "BOARD_SUPER_PARTITION_GROUPS"}
    require(active.get("TARGET_USERIMAGES_USE_EROFS") == "true",
            "own mondrian EROFS policy not active")
    for partition in ("ODM", "PRODUCT", "SYSTEM", "SYSTEM_EXT", "VENDOR", "VENDOR_DLKM"):
        require(active.get(f"BOARD_{partition}IMAGE_FILE_SYSTEM_TYPE") == "erofs",
                f"own mondrian {partition} output is not EROFS")
    require(not (set(active) & disallowed),
            "unverified boot/partition setting enabled: " + str(sorted(set(active) & disallowed)))
    return d


def verify_source(text, r, d):
    data = parse_assignments(text)
    for key, size in d["matching_reference_fields"].items():
        require(key in data, f"{r['repo']}: {key} is absent")
        raw = data[key].split()[0]
        try:
            actual = int(raw, 0)
        except ValueError as e:
            raise ValueError(f"unparseable {key}: {raw}") from e
        require(actual == size, f"{r['repo']}: {key} changed: {actual} != {size}")
    dyn = data.get("BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST", "").split()
    require(dyn == d["dynamic_partition_names"], f"{r['repo']}: dynamic partition list drift")
    ota = parse_ab_partitions(text)
    require(ota == d["reference_ab_ota_partitions"], f"{r['repo']}: AB_OTA_PARTITIONS drift")
    for key in ("ODM", "PRODUCT", "SYSTEM", "SYSTEM_EXT", "VENDOR", "VENDOR_DLKM"):
        actual = data.get(f"BOARD_{key}IMAGE_FILE_SYSTEM_TYPE")
        require(actual == r["logical_fs"], f"{r['repo']}: {key} fs changed: {actual}")


def online(d):
    for r in d["references"]:
        url = f"https://raw.githubusercontent.com/{r['repo']}/{r['commit']}/{r['path']}"
        req = Request(url, headers={"User-Agent": "PE-Reborn-mondrian-boot-source-audit"})
        with urlopen(req, timeout=30) as response:
            raw = response.read()
        require(git_blob_sha(raw) == r["blob"], f"{r['repo']}: source file Git blob mismatch")
        verify_source(raw.decode("utf-8"), r, d)
        print(f"[PASS] read-only partition source: {r['repo']} @{r['commit'][:12]} ({r['logical_fs']})")
    print("[PASS] public boot partition references agree on sizes/OTA, but disagree on logical FS")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--online", action="store_true")
        args = parser.parse_args()
        d = load()
        print("[PASS] pinned mondrian boot/partition candidate schema; no unsafe board enablement")
        if args.online:
            online(d)
        else:
            print("[INFO] offline only: run --online to verify published source content")
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        sys.exit(1)
