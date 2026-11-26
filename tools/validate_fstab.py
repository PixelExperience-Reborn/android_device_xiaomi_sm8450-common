#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check rootdir/etc/fstab.qcom against the stock OS3.0.8.0 fstab and our kernel.

The fstab is derived from vendor/etc/fstab.qcom of the official OTA
OS3.0.8.0.VMNCNXM (also the first_stage_ramdisk fstab of its vendor_boot).
This tool checks that:
  - the entries are exactly the stock entries we keep (MIUI mi_ext/overlay
    mounts and the absent SD card slot are dropped);
  - every /data F2FS option is one our 5.10.81 kernel parses (an unknown
    option makes the mount fail);
  - verified boot, first-stage mounting and file-based encryption follow stock;
  - the fstab is installed to vendor/etc, the vendor ramdisk first stage and
    used by recovery.
With --stock PATH it also compares the file with the stock fstab line by line,
allowing only the documented differences.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FSTAB = ROOT / "rootdir/etc/fstab.qcom"
STOCK_SHA256 = "c19019a181e72c4f773d5f3db29df03a2a153c85f15ac2487e97b76c02ace372"

DYNAMIC = ("system", "system_ext", "product", "vendor", "vendor_dlkm", "odm")
VBMETA_SYSTEM = {"system", "system_ext", "product"}
GSI_KEYS = "/avb/q-gsi.avbpubkey:/avb/r-gsi.avbpubkey:/avb/s-gsi.avbpubkey"

# (device, mount point, filesystem) kept from stock, in stock order.
EXPECTED = [(p, "/" + p, fs) for p in DYNAMIC for fs in ("ext4", "erofs")] + [
    ("/dev/block/by-name/metadata", "/metadata", "ext4"),
    ("/dev/block/bootdevice/by-name/persist", "/mnt/vendor/persist", "ext4"),
    ("/dev/block/bootdevice/by-name/userdata", "/data", "f2fs"),
    ("/dev/block/bootdevice/by-name/misc", "/misc", "emmc"),
    ("/devices/platform/soc/*.ssusb/*.dwc3/xhci-hcd.*.auto*", "/storage/usbotg", "vfat"),
    ("/dev/block/bootdevice/by-name/modem", "/vendor/firmware_mnt", "vfat"),
    ("/dev/block/bootdevice/by-name/dsp", "/vendor/dsp", "ext4"),
    ("/dev/block/bootdevice/by-name/bluetooth", "/vendor/bt_firmware", "vfat"),
    ("/dev/block/bootdevice/by-name/qmcs", "/mnt/vendor/qmcs", "vfat"),
]

# Stock lines that are intentionally not carried over.
DROPPED_MOUNTS = {"/mnt/vendor/mi_ext", "/mi_ext", "/storage/sdcard1"}
DROPPED_DEVICES = {"mi_ext", "overlay"}

# /data mount options: VFS options plus the F2FS options of our kernel
# (fs/f2fs/super.c of android_kernel_xiaomi_sm8450 2efda4c).
VFS_OPTIONS = {"noatime", "nosuid", "nodev"}
KERNEL_F2FS_OPTIONS = {
    "discard", "reserve_root", "resgid", "fsync_mode", "inlinecrypt", "gc_merge",
    "compress_mode", "compress_cache", "atgc", "checkpoint_merge",
}
NOT_IN_OUR_KERNEL = {"age_extent_cache"}  # Linux 6.2

FBE = "aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0"
MDE = "aes-256-xts:wrappedkey_v0"
KEY_DIR = "/metadata/vold/metadata_encryption"


def parse_fstab(text):
    """Rows as dicts; a mount point may appear once per filesystem."""
    rows, seen = [], set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        cols = line.split()
        if len(cols) != 5:
            raise ValueError(f"line {number}: expected 5 fields, got {len(cols)}")
        device, mount, fs, options, mgr = cols
        if (mount, fs) in seen:
            raise ValueError(f"line {number}: duplicate entry {mount} {fs}")
        seen.add((mount, fs))
        flags = {}
        for item in mgr.split(","):
            key, sep, value = item.partition("=")
            if key in flags:
                raise ValueError(f"line {number}: duplicate fs_mgr flag {key}")
            flags[key] = value if sep else None
        rows.append({"device": device, "mount": mount, "fs": fs,
                     "options": options.split(","), "flags": flags, "line": line})
    return rows


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_rows(rows):
    require([(r["device"], r["mount"], r["fs"]) for r in rows] == EXPECTED,
            "entries differ from the stock entries we keep: "
            f"{sorted(set((r['device'], r['mount'], r['fs']) for r in rows) ^ set(EXPECTED))}")
    by = {(r["mount"], r["fs"]): r for r in rows}
    for part in DYNAMIC:
        for fs in ("ext4", "erofs"):
            row = by[("/" + part, fs)]
            flags = row["flags"]
            for flag in ("wait", "slotselect", "logical", "first_stage_mount"):
                require(flag in flags, f"/{part} {fs}: missing {flag}")
            chain = "vbmeta_system" if part in VBMETA_SYSTEM else None
            require("avb" in flags and flags["avb"] == chain, f"/{part} {fs}: wrong AVB chain")
            require(flags.get("avb_keys") == (GSI_KEYS if part == "system" else None),
                    f"/{part} {fs}: avb_keys differ from stock")
        require(by[("/" + part, "erofs")]["options"] == ["ro"], f"/{part}: EROFS must be mounted ro")

    metadata = by[("/metadata", "ext4")]["flags"]
    for flag in ("wait", "check", "formattable", "first_stage_mount"):
        require(flag in metadata, f"/metadata: missing {flag}")

    data = by[("/data", "f2fs")]
    for option in data["options"]:
        name = option.split("=", 1)[0]
        require(name not in NOT_IN_OUR_KERNEL, f"/data: {name} is not supported by our 5.10.81 kernel")
        require(name in VFS_OPTIONS | KERNEL_F2FS_OPTIONS, f"/data: unknown mount option {name}")
    flags = data["flags"]
    require(flags.get("fileencryption") == FBE, "/data: file-based encryption differs from stock")
    require(flags.get("metadata_encryption") == MDE, "/data: metadata encryption differs from stock")
    require(flags.get("keydirectory") == KEY_DIR, "/data: key directory differs from stock")
    for flag in ("latemount", "wait", "check", "formattable", "quota"):
        require(flag in flags, f"/data: missing {flag}")
    require(flags.get("checkpoint") == "fs", "/data: checkpoint=fs missing")

    for mount in ("/vendor/firmware_mnt", "/vendor/dsp", "/vendor/bt_firmware"):
        row = next(r for r in rows if r["mount"] == mount)
        require("slotselect" in row["flags"] and "ro" in row["options"],
                f"{mount}: firmware partitions are A/B and read-only")


def validate_installed():
    common = (ROOT / "common.mk").read_text(encoding="utf-8")
    board = (ROOT / "BoardConfigCommon.mk").read_text(encoding="utf-8")
    for dest in ("$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qcom",
                 "$(TARGET_COPY_OUT_VENDOR_RAMDISK)/first_stage_ramdisk/fstab.qcom"):
        require(f"device/xiaomi/sm8450-common/rootdir/etc/fstab.qcom:{dest}" in common,
                f"fstab.qcom is not installed to {dest}")
    require("TARGET_RECOVERY_FSTAB := $(COMMON_PATH)/rootdir/etc/fstab.qcom" in board,
            "recovery must use the same fstab.qcom")
    require(not (ROOT / "rootdir/etc/recovery.fstab").exists(),
            "a separate recovery.fstab would drift from fstab.qcom")


def compare_with_stock(rows, stock_text):
    """Every kept line must equal stock, except the documented /data option."""
    stock = {}
    for row in parse_fstab(stock_text):
        if row["mount"] in DROPPED_MOUNTS or row["device"] in DROPPED_DEVICES:
            continue
        if row["mount"].startswith("/storage/sdcard"):
            continue
        stock[(row["mount"], row["fs"])] = row
    ours = {(r["mount"], r["fs"]): r for r in rows}
    require(set(stock) == set(ours), f"kept entries differ from stock: {sorted(set(stock) ^ set(ours))}")
    for key, row in ours.items():
        theirs = stock[key]
        options = theirs["options"]
        if key == ("/data", "f2fs"):
            options = [o for o in options if o.split("=", 1)[0] not in NOT_IN_OUR_KERNEL]
        require(row["device"] == theirs["device"] and row["options"] == options
                and row["flags"] == theirs["flags"], f"{key}: differs from stock")


def validate(stock_path=None):
    rows = parse_fstab(FSTAB.read_text(encoding="utf-8"))
    validate_rows(rows)
    validate_installed()
    if stock_path:
        import hashlib
        data = Path(stock_path).read_bytes()
        require(hashlib.sha256(data).hexdigest() == STOCK_SHA256,
                "the given stock fstab is not the OS3.0.8.0.VMNCNXM file")
        compare_with_stock(rows, data.decode("utf-8"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stock", help="stock vendor/etc/fstab.qcom of OS3.0.8.0.VMNCNXM")
    args = parser.parse_args()
    try:
        rows = validate(args.stock)
    except (OSError, ValueError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(f"[PASS] fstab.qcom: {len(rows)} stock-derived entries, installed for first stage, "
          "vendor and recovery" + (", identical to stock except documented differences" if args.stock else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
