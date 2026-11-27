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
  device/xiaomi/mondrian/firmware-files.txt         -> vendor/xiaomi/mondrian/radio/
  device/xiaomi/mondrian/kernel-files.txt           -> vendor/xiaomi/mondrian/kernel/

Firmware lists name raw partition images of the OTA payload (<partition>|<sha256>,
also pinned in ota-source.json). They come from --images-dir (already extracted
images) or the OTA; with --verify-only the OTA payload manifest is checked
without downloading the images.

The kernel list (mondrian/kernel-files.txt) names the stock boot, vendor_boot,
dtbo and vendor_dlkm images the same way; tools/stock_kernel.py turns them into
the kernel layout of vendor/xiaomi/mondrian/kernel (KERNEL_PATH of BoardConfig).
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
from blob_fixups import apply as apply_fixups, rename_ndk_platform  # noqa: E402
# <file>[;<extract-utils argument>...]|<sha256>, e.g. ;SYMLINK=<link> or
# ;MODULE_SUFFIX=_vendor; the arguments shape the build rules only.
LINE = re.compile(r"^((?:vendor|odm)/[A-Za-z0-9_@+.,/-]+)(?:;[A-Z_]+(?:=[A-Za-z0-9_@+.,/-]+)?)*\|([0-9a-f]{64})$")
PARTITIONS = ("vendor", "odm")
FIRMWARE_LINE = re.compile(r"^([a-z0-9_-]+)\|([0-9a-f]{64})$")


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


def default_firmware() -> list[tuple[Path, Path]]:
    android = ROOT.parents[2]
    lst = ROOT.parent / "mondrian/firmware-files.txt"
    return [(lst, android / "vendor/xiaomi/mondrian/radio")] if lst.exists() else []


def default_kernel() -> list[tuple[Path, Path]]:
    android = ROOT.parents[2]
    lst = ROOT.parent / "mondrian/kernel-files.txt"
    return [(lst, android / "vendor/xiaomi/mondrian/kernel")] if lst.exists() else []


def read_firmware(path: Path, source: dict, kind: str = "firmware") -> list[tuple[str, str]]:
    """(partition, sha256) of a firmware or kernel list; each must be pinned in ota-source.json."""
    out, seen = [], set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = FIRMWARE_LINE.match(line)
        if not m or m[1] in seen:
            raise ListError(f"{path}:{number}: malformed or duplicate firmware line: {line}")
        pinned = source["partitions"].get(m[1])
        if not pinned or pinned.get("type") != kind or pinned["sha256"] != m[2]:
            raise ListError(f"{path}:{number}: {m[1]} is not the {kind} image pinned in ota-source.json")
        seen.add(m[1])
        out.append((m[1], m[2]))
    return out


def firmware(location: str | None, source: dict, lists, images: Path | None, verify_only: bool,
             jobs: int) -> list[str]:
    """Copy or extract each listed firmware image; return the problems."""
    problems, from_ota = [], []
    for lst, out, entries in lists:
        for name, digest in entries:
            local = images / f"{name}.img" if images else None
            done = out / f"{name}.img"
            if not verify_only and done.is_file() and sha256(done) == digest:
                continue  # already extracted and verified
            if local and local.is_file():
                if sha256(local) != digest:
                    problems.append(f"hash mismatch: {local}")
                elif not verify_only:
                    out.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(local, out / f"{name}.img")
            else:
                from_ota.append((out, name, digest))
        print(f"{lst}: {len(entries)} firmware images checked")
    if from_ota:
        sys.path.insert(0, str(ROOT / "tools"))
        from ota_payload import Ota, OtaError, rank_urls  # noqa: E402
        errors = []
        for url in ([location] if location else rank_urls(source["ota"]["urls"])):
            try:
                ota = Ota(url, source)
                for out, name, digest in from_ota:
                    part = ota.partitions.get(name)
                    if part is None or part["hash"] != digest:
                        problems.append(f"{name}: not the pinned image in the OTA payload")
                    elif not verify_only:
                        ota.extract(name, out / f"{name}.img", jobs)
                return problems
            except (OtaError, OSError) as error:
                errors.append(f"{url}: {error}")
        problems.append("cannot obtain the firmware: " + "; ".join(errors))
    return problems


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
    p.add_argument("--firmware", action="append", default=[], metavar="LIST=OUTDIR",
                   help="firmware-files.txt and its radio directory (default: Android tree layout)")
    p.add_argument("--kernel", action="append", default=[], metavar="LIST=OUTDIR",
                   help="kernel-files.txt and its kernel directory (default: Android tree layout)")
    p.add_argument("--images-dir", type=Path, help="already extracted OTA partition images (<name>.img)")
    p.add_argument("--verify-only", action="store_true", help="check every file, write nothing")
    p.add_argument("--work", type=Path, help="scratch directory for the OTA partition")
    p.add_argument("--jobs", type=int, default=6)
    args = p.parse_args()

    source = json.loads((ROOT / "proprietary/ota-source.json").read_text())
    pairs = [(Path(a.split("=", 1)[0]), Path(a.split("=", 1)[1])) for a in args.list] or default_lists()
    lists = [(lst, out, read_list(lst)) for lst, out in pairs]
    fw_pairs = [(Path(a.split("=", 1)[0]), Path(a.split("=", 1)[1])) for a in args.firmware] or default_firmware()
    fw_lists = [(lst, out, read_firmware(lst, source)) for lst, out in fw_pairs]
    k_pairs = [(Path(a.split("=", 1)[0]), Path(a.split("=", 1)[1])) for a in args.kernel] or default_kernel()
    # The pinned images go next to the kernel directory, which stock_kernel.py rewrites.
    k_lists = [(lst, out.parent / f"{out.name}-images", read_firmware(lst, source, "kernel"), out)
               for lst, out in k_pairs]

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
                    applied = apply_fixups(entry.path, target)
                    if renamed or applied:
                        record = {"sha256": sha256(target)}
                        if renamed:
                            record["needed_renamed"] = renamed
                        if applied:
                            record["fixups"] = applied
                        fixups[str(lst.name)][entry.path] = record
            print(f"{lst}: {len(entries)} files checked")
        problems += firmware(args.ota, source, fw_lists, args.images_dir, args.verify_only, args.jobs)
        problems += firmware(args.ota, source, [k[:3] for k in k_lists], args.images_dir, args.verify_only,
                             args.jobs)
        if not problems and not args.verify_only:
            from stock_kernel import extract as extract_kernel  # noqa: E402
            for lst, images, entries, out in k_lists:
                info = extract_kernel(images, out)
                info["images"] = {name: digest for name, digest in entries}
                (out / "provenance.json").write_text(json.dumps(info, indent=2) + "\n")
                print(f"{lst}: kernel {info['kernel_release']}, {info['vendor_ramdisk_modules']} vendor_boot "
                      f"and {info['vendor_dlkm_modules']} vendor_dlkm modules")
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
