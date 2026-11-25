#!/usr/bin/env python3
"""Reproduce the mondrian proprietary files from the official Xiaomi OTA.

The lists (`proprietary-files.txt` of sm8450-common and mondrian) name each
closed file with the SHA-256 it has in the OTA pinned by
proprietary/ota-source.json. This tool copies exactly those files into the
vendor repositories and refuses any file whose hash differs.

Sources, in order of preference:
  --vendor-dir DIR     an already extracted vendor partition
  --vendor-image IMG   the vendor partition image (EROFS; needs fsck.erofs)
  --ota ZIP|URL        the official OTA itself (default: the pinned URLs)

Default layout inside an Android tree:
  device/xiaomi/sm8450-common/proprietary-files.txt -> vendor/xiaomi/sm8450-common/proprietary/
  device/xiaomi/mondrian/proprietary-files.txt      -> vendor/xiaomi/mondrian/proprietary/
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"^(vendor/[A-Za-z0-9_@+.,/-]+)\|([0-9a-f]{64})$")


@dataclass(frozen=True)
class Entry:
    path: str
    sha256: str
    section: str


class ListError(ValueError):
    pass


def read_list(path: Path) -> list[Entry]:
    """Parse a proprietary-files.txt; every entry must be inside a section."""
    entries, section, seen = [], None, set()
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# === ") and line.endswith(" ==="):
            section = line[6:-4]
            continue
        if line.startswith("#"):
            continue
        match = LINE.match(line)
        if not match:
            raise ListError(f"{path}:{number}: expected 'vendor/<path>|<sha256>': {raw!r}")
        if section is None:
            raise ListError(f"{path}:{number}: entry before the first section header")
        if match.group(1) in seen:
            raise ListError(f"{path}:{number}: duplicate entry {match.group(1)}")
        seen.add(match.group(1))
        entries.append(Entry(match.group(1), match.group(2), section))
    return entries


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_lists() -> list[tuple[Path, Path]]:
    android = ROOT.parents[2]
    pairs = [(ROOT / "proprietary-files.txt", android / "vendor/xiaomi/sm8450-common")]
    mondrian = ROOT.parent / "mondrian/proprietary-files.txt"
    if mondrian.exists():
        pairs.append((mondrian, android / "vendor/xiaomi/mondrian"))
    return pairs


def vendor_from_image(image: Path, work: Path) -> Path:
    if shutil.which("fsck.erofs") is None:
        raise SystemExit("fsck.erofs (erofs-utils) is required to read the EROFS vendor image")
    out = work / "vendor"
    out.mkdir(parents=True)
    subprocess.run(["fsck.erofs", f"--extract={out}", str(image)], check=True,
                   stdout=subprocess.DEVNULL)
    return out


def vendor_from_ota(location: str | None, source: dict, work: Path, jobs: int) -> Path:
    sys.path.insert(0, str(ROOT / "tools"))
    from ota_payload import Ota, OtaError  # noqa: E402

    image = work / "vendor.img"
    errors = []
    for url in ([location] if location else source["ota"]["urls"]):
        try:
            ota = Ota(url, source)
            ota.extract("vendor", image, jobs,
                        lambda done, total: print(f"\r  vendor: {done}/{total}", end="", flush=True))
            print()
            return vendor_from_image(image, work)
        except (OtaError, OSError) as error:
            errors.append(f"{url}: {error}")
    raise SystemExit("cannot obtain the pinned vendor partition:\n  " + "\n  ".join(errors))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--vendor-dir", type=Path)
    src.add_argument("--vendor-image", type=Path)
    src.add_argument("--ota", help="official OTA zip path or https URL")
    p.add_argument("--list", action="append", default=[], metavar="LIST=OUTDIR",
                   help="proprietary-files.txt and its vendor repository (default: Android tree layout)")
    p.add_argument("--verify-only", action="store_true", help="check every file, write nothing")
    p.add_argument("--work", type=Path, help="scratch directory for the OTA partition")
    p.add_argument("--jobs", type=int, default=6)
    args = p.parse_args()

    source = json.loads((ROOT / "proprietary/ota-source.json").read_text())
    pairs = [(Path(a.split("=", 1)[0]), Path(a.split("=", 1)[1])) for a in args.list] or default_lists()
    lists = [(lst, out, read_list(lst)) for lst, out in pairs]

    with tempfile.TemporaryDirectory(dir=args.work) as tmp:
        work = Path(tmp)
        if args.vendor_dir:
            vendor = args.vendor_dir
        elif args.vendor_image:
            vendor = vendor_from_image(args.vendor_image, work)
        else:
            vendor = vendor_from_ota(args.ota, source, work, args.jobs)

        problems = []
        for lst, out, entries in lists:
            for entry in entries:
                src_file = vendor / entry.path.removeprefix("vendor/")
                if not src_file.is_file():
                    problems.append(f"missing: {entry.path}")
                    continue
                actual = sha256(src_file)
                if actual != entry.sha256:
                    problems.append(f"hash mismatch: {entry.path} {actual} != {entry.sha256}")
                    continue
                if not args.verify_only:
                    target = out / "proprietary" / entry.path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src_file, target)
            print(f"{lst}: {len(entries)} files checked")
        if problems:
            print("[FAIL] proprietary files do not match the pinned OTA:")
            for line in problems:
                print("  " + line)
            return 1
        if not args.verify_only:
            for lst, out, entries in lists:
                (out / "proprietary/provenance.json").write_text(json.dumps({
                    "list": str(lst.name), "list_sha256": sha256(lst), "files": len(entries),
                    "ota": source["ota"]["file"], "ota_post_build": source["ota"]["post_build"],
                    "vendor_partition_sha256": source["partitions"]["vendor"]["sha256"],
                }, indent=2) + "\n")
        print("[PASS] every listed file matches the official OTA"
              + (" (verify only)" if args.verify_only else ""))
        return 0


if __name__ == "__main__":
    sys.exit(main())
