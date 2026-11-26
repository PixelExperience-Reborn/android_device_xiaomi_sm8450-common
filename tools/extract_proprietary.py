#!/usr/bin/env python3
"""Reproduce the mondrian proprietary files from the official Xiaomi OTA.

The lists (`proprietary-files.txt` of sm8450-common and mondrian) name each
closed file with the SHA-256 it has in the OTA pinned by
proprietary/ota-source.json. This tool copies exactly those files into the
vendor repositories and refuses any file whose hash differs.

Entries start with the partition they come from (vendor/ or odm/). Sources,
in order of preference, per partition:
  --vendor-dir DIR / --odm-dir DIR       an already extracted partition
  --vendor-image IMG / --odm-image IMG   the partition image (EROFS; needs fsck.erofs)
  --ota ZIP|URL                          the official OTA itself (default: the pinned URLs)

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blob_fixups import rename_ndk_platform  # noqa: E402
LINE = re.compile(r"^((?:vendor|odm)/[A-Za-z0-9_@+.,/-]+)\|([0-9a-f]{64})$")
PARTITIONS = ("vendor", "odm")


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
            raise ListError(f"{path}:{number}: expected '<vendor|odm>/<path>|<sha256>': {raw!r}")
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


def tree_from_image(image: Path, work: Path, name: str) -> Path:
    if shutil.which("fsck.erofs") is None:
        raise SystemExit("fsck.erofs (erofs-utils) is required to read the EROFS partition image")
    out = work / name
    out.mkdir(parents=True)
    subprocess.run(["fsck.erofs", f"--extract={out}", str(image)], check=True,
                   stdout=subprocess.DEVNULL)
    return out


def trees_from_ota(location: str | None, source: dict, work: Path, jobs: int,
                   names: list[str]) -> dict[str, Path]:
    sys.path.insert(0, str(ROOT / "tools"))
    from ota_payload import Ota, OtaError, rank_urls  # noqa: E402

    errors = []
    for url in ([location] if location else rank_urls(source["ota"]["urls"])):
        try:
            ota = Ota(url, source)
            trees = {}
            for name in names:
                image = work / f"{name}.img"
                ota.extract(name, image, jobs,
                            lambda done, total, n=name: print(f"\r  {n}: {done}/{total}", end="", flush=True))
                print()
                trees[name] = tree_from_image(image, work, name)
            return trees
        except (OtaError, OSError) as error:
            errors.append(f"{url}: {error}")
    raise SystemExit("cannot obtain the pinned partitions:\n  " + "\n  ".join(errors))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in PARTITIONS:
        p.add_argument(f"--{name}-dir", type=Path)
        p.add_argument(f"--{name}-image", type=Path)
    p.add_argument("--ota", help="official OTA zip path or https URL")
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
        needed = sorted({e.path.split("/", 1)[0] for _, _, entries in lists for e in entries})
        trees, from_ota = {}, []
        for name in needed:
            if getattr(args, f"{name}_dir"):
                trees[name] = getattr(args, f"{name}_dir")
            elif getattr(args, f"{name}_image"):
                trees[name] = tree_from_image(getattr(args, f"{name}_image"), work, name)
            else:
                from_ota.append(name)
        if from_ota:
            trees.update(trees_from_ota(args.ota, source, work, args.jobs, from_ota))

        problems = []
        fixups = {str(lst.name): {} for lst, _, _ in lists}
        for lst, out, entries in lists:
            for entry in entries:
                partition, rel = entry.path.split("/", 1)
                src_file = trees[partition] / rel
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
                    renamed = rename_ndk_platform(target)
                    if renamed:
                        fixups[str(lst.name)][entry.path] = {"needed_renamed": renamed,
                                                            "sha256": sha256(target)}
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
                    "partition_sha256": {n: source["partitions"][n]["sha256"] for n in needed},
                    "fixups": fixups[str(lst.name)],
                }, indent=2) + "\n")
        print("[PASS] every listed file matches the official OTA"
              + (" (verify only)" if args.verify_only else ""))
        return 0


if __name__ == "__main__":
    sys.exit(main())
