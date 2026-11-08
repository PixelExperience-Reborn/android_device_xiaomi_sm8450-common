#!/usr/bin/env python3
"""Check independently authored, non-installed mondrian AOSP17 fstab candidates.

This is source-level preflight, not an Android fs_mgr parser, encrypted userdata
mount, verified AVB, OTA or recovery boot test. No filesystem is modified.
"""
import sys
from pathlib import Path
from compare_fstab_pair import parse_fstab, compare

ROOT = Path(__file__).resolve().parents[1]
NORMAL = ROOT / "rootdir/etc/fstab.qcom"
RECOVERY = ROOT / "rootdir/etc/recovery.fstab"

DYNAMIC = {
    "/system": "system",
    "/system_ext": "system_ext",
    "/product": "product",
    "/vendor": "vendor",
    "/odm": "odm",
    "/vendor_dlkm": "vendor_dlkm",
}
CRYPTO_KEYS = ("fileencryption", "keydirectory", "metadata_encryption")
FBE = "aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0"
MDE = "aes-256-xts:wrappedkey_v0"
KEY_DIR = "/metadata/vold/metadata_encryption"


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def validate_rows(rows, role):
    # Only the nine essential core entries are under source qualification.
    # Independent modem/persist firmware and other mount points are pending.
    require(set(rows) == set(DYNAMIC) | {"/metadata", "/data", "/misc"},
            f"{role}: unexpected/missing mount points: {set(rows) ^ (set(DYNAMIC) | {'/metadata', '/data', '/misc'})}")
    for mount, dev in DYNAMIC.items():
        row = rows[mount]
        flags = row["flags"]
        require(row["device"] == dev, f"{role}: incorrect dynamic partition name {mount}")
        require(row["filesystem"] == "erofs", f"{role}: EROFS image type mismatch {mount}")
        require(row["options"] == "ro", f"{role}: read-only dynamic mount required {mount}")
        for k in ("logical", "first_stage_mount", "slotselect"):
            require(k in flags, f"{role}: {mount}: missing {k}")
        expected_avb = "vbmeta_system" if mount in ("/system", "/system_ext", "/product") else None
        require("avb" in flags and flags["avb"] == expected_avb,
                f"{role}: {mount}: unexpected AVB chain")
        require("avb_keys" not in flags, f"{role}: {mount}: unaudited GSI public AVB keys")

    metadata = rows["/metadata"]
    require(metadata["filesystem"] == "ext4", f"{role}: /metadata must be ext4")
    require(metadata["device"] == "/dev/block/by-name/metadata",
            f"{role}: /metadata device changed")
    require("first_stage_mount" in metadata["flags"],
            f"{role}: /metadata must mount in first stage")

    data = rows["/data"]
    require(data["device"] == "/dev/block/bootdevice/by-name/userdata",
            f"{role}: /data device changed")
    require(data["filesystem"] == "f2fs", f"{role}: /data must use F2FS")
    flags = data["flags"]
    require("latemount" in flags and "wait" in flags, f"{role}: /data mount phase")
    require(flags.get("fileencryption") == FBE, f"{role}: /data FBE v2 contract changed")
    require(flags.get("metadata_encryption") == MDE,
            f"{role}: /data metadata crypt contract changed")
    require(flags.get("keydirectory") == KEY_DIR,
            f"{role}: /data encryption key directory changed")
    require("inlinecrypt" in data["options"].split(","), f"{role}: /data inlinecrypt option absent")
    require("nobarrier" not in data["options"], f"{role}: unsafe nobarrier storage tuning")
    require("formattable" not in flags, f"{role}: candidate must never format user data")
    require("wrappedkey" not in flags and flags.get("fileencryption") != "ice",
            f"{role}: recovery may not downgrade FBE")

    misc = rows["/misc"]
    require(misc["device"] == "/dev/block/bootdevice/by-name/misc" and
            misc["filesystem"] == "emmc", f"{role}: /misc device/type changed")
    for mount, row in rows.items():
        require("formattable" not in row["flags"],
                f"{role}: unexpected format-on-error option at {mount}")


def validate_uninstalled():
    board = (ROOT / "BoardConfigCommon.mk").read_text(encoding="utf-8")
    device = (ROOT / "common.mk").read_text(encoding="utf-8")
    active = "\n".join(
        line.split("#", 1)[0].strip()
        for line in (board + "\n" + device).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    for token in ("TARGET_RECOVERY_FSTAB", "BOARD_RECOVERY_FSTAB", "fstab.qcom",
                  "rootdir/etc/recovery.fstab", "TARGET_COPY_OUT_VENDOR_RAMDISK",
                  "TARGET_USERIMAGES_USE_EROFS", "BOARD_AVB_ENABLE"):
        require(token not in active, f"fstab/boot choice active before vendor validation: {token}")


def validate():
    main = parse_fstab(NORMAL.read_text(encoding="utf-8"))
    recovery = parse_fstab(RECOVERY.read_text(encoding="utf-8"))
    validate_rows(main, "normal")
    validate_rows(recovery, "recovery")
    mismatches = compare(main, recovery)
    require(not mismatches, "fstab pair mismatch: " + "; ".join(mismatches))
    for mount in ("/data", "/metadata"):
        require(main[mount]["device"] == recovery[mount]["device"],
                f"{mount} device differs between normal and recovery")
    for field in CRYPTO_KEYS:
        require(main["/data"]["flags"].get(field) == recovery["/data"]["flags"].get(field),
                f"normal/recovery /data field mismatch: {field}")
    validate_uninstalled()
    print("[PASS] native mondrian EROFS + F2FS fstab candidates agree, FBE and AVB guards hold")
    print("[NOTE] NOT installed in an image; needs kernel, vendor KeyMint, AVB, recovery, OTA hardware checks")


if __name__ == "__main__":
    try:
        validate()
    except (ValueError, OSError) as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
