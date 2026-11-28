# PE-Reborn AOSP 17 / mondrian — native storage and boot-chain implementation

**State: independent source implementation; NOT an installed fstab; no bootable
kernel, recovery, vendor partition or complete target ROM has been produced.**

Target is **POCO F5 Pro / Redmi K60 (mondrian, SM8475)**, with a shared
taro/SM8450-named BSP. This is not a claim that the physical SoC is SM8450.

## 1. fstab (stock-derived, installed)

`rootdir/etc/fstab.qcom` is derived entry by entry from the stock
`vendor/etc/fstab.qcom` of OS3.0.8.0.VMNCNXM (sha256 `c19019a1...ace372`),
which stock also uses as the `first_stage_ramdisk` fstab of `vendor_boot`.
`common.mk` installs it to both places and `TARGET_RECOVERY_FSTAB` uses it, so
first stage, Android and recovery share one file.

Deliberate differences from stock:

- `/data`: no `age_extent_cache` (Linux 6.2 F2FS option, rejected by our
  5.10.81 kernel). All other stock F2FS options are parsed by our kernel.
- no `mi_ext` partition and no MIUI overlay mounts on `/product` and `/system`.
- no SD card entry (mondrian has no slot).

Kept from stock: EROFS and ext4 entries for the six logical partitions (images
are EROFS), GSI `avb_keys` on `/system`, `/metadata` and `/data` with
`formattable`, FBE v2 + wrappedkey_v0 and metadata encryption, `persist`,
`modem` (`/vendor/firmware_mnt`), `dsp`, `bluetooth`, `qmcs` and USB OTG.

`tools/validate_fstab.py` checks the entries, AVB, encryption, kernel support of
every `/data` option and the installation; `--stock PATH` compares the file with
the stock fstab line by line (it matches except for the documented differences).
`tests/test_fstab.py` covers it, including negative cases.

The mount point directories `/vendor/firmware_mnt`, `/vendor/dsp` and
`/vendor/bt_firmware` are created in the vendor image by `rootdir/Android.mk`;
the verify stage of the build checks them in the built `vendor.img`. The
SELinux types of the `context=` options (`firmware_file`, `bt_firmware_file`,
`vendor_qmcs_file`) are declared by `tools/gen_bringup_sepolicy.py` since
28.11.2026; before that the kernel rejected the contexts (errno -22) and the
modem partition, with the ADSP, CDSP, modem, IPA and Wi-Fi firmware, was never
mounted.

The logical partitions are EROFS in the format of the stock images
(`feature_incompat` 0x1: LZ4 with 0padding, 4 KiB physical clusters, that is no
`BOARD_EROFS_PCLUSTER_SIZE`; `BOARD_EROFS_USE_LEGACY_COMPRESSION` would also drop
0padding and give 0x0, which the verify stage of build 0659 showed). The GKI 5.10 of the stock kernel mounts big pclusters only through a
backport it logs as "EXPERIMENTAL big pcluster feature in use"; the stock
images do not use them on this kernel, and neither do ours.


These choices are deliberate candidates based on the LF52406 mondrian
reference. **No automatic format action** is allowed in the candidate:
before enabling wipe/recovery options we must prove proper KeyMint, FBE
and safe data retention/upgrade behaviour.

AOSP requires dynamic logical fstab entries with `logical` and
`first_stage_mount`; `avb=...` identifies the chained vbmeta owner.
AOSP vendor boot guidance places first-stage fstab in the vendor-ramdisk,
**not in arbitrary generic-ramdisk/device-tree content**.

Sources:
- https://source.android.com/docs/core/ota/dynamic_partitions/implement
- https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions
- https://source.android.com/docs/security/features/encryption/metadata
- https://source.android.com/docs/security/features/encryption/file-based

## 2. Independent boot partition evidence

`boot-partition-qualification.json` pins Git commits **and file blobs**
for the official LineageOS24 and LF52406 board references. Both declare:

- `BOARD_BOOT_HEADER_VERSION=4`, kernel page size **4096 bytes**;
- boot partition **201,326,592 B** (192 MiB);
- DTBO partition **25,165,824 B** (24 MiB);
- recovery partition **104,857,600 B** (100 MiB);
- vendor_boot partition **100,663,296 B** (96 MiB);
- super partition **9,126,805,504 B**;
- dynamic group allowance **9,122,611,200 B**;
- super metadata/buffer difference **4,194,304 B (4 MiB)**;
- dynamic logical group members: odm/product/system/system_ext/vendor/vendor_dlkm;
- an A/B OTA list that includes boot, dtbo, recovery, vbmeta, vbmeta_system,
  vendor_boot and the logical partition images.

**Material discrepancy:** official LineageOS24 board uses **ext4** for
logical images, while the LF52406 modified tree uses **EROFS**.
Neither source proves the current physical GPT or establishes the
correct release image format on our new AOSP 17 build.

`tools/verify_reference_boot_layout.py --online` checks immutable
public Git file hashes, all common values, list membership, and confirms
the two distinct filesystem assumptions. CI reports this as source
evidence, not vendor_boot/AVB qualification. We have *not* activated
partition sizes, EROFS image generation, recovery or signing parameters
in `BoardConfigCommon.mk`.

## 3. Remaining first-boot blockers (must be solved together)

1. Select a reproducible **full kernel + external Qualcomm modules + DT/DTBO**
   bill of materials; reconcile Android17 QPR support and vendor KMI.
2. Identify actual device partitions from reliable on-device `by-name`
   links and boot/recovery/vendor_boot headers; validate DTBO board IDs and
   vendor-ramdisk fragment ordering, module load and fstab placement.
3. Match all logical image filesystem types to selected EROFS or ext4 policy.
   Actual vendor blobs, /persist, /vendor/firmware_mnt, DSP, Bluetooth,
   vm-bootsys and QMCS mount paths are **not implemented** in these minimal
   candidates; they require vendor ELF/partition/SELinux audits.
4. Validate AOSP17 KeyMint, wrapped-key compatibility and `dm-default-key`
   API/launch-level assumptions. Reusing `wrappedkey_v0` is a
   compatibility hypothesis with LF reference, **not** an invitation to
   upgrade keys or format encrypted user data.
5. Only after correctly signing AVB descriptors and rollback indexes
   should any image be flashed to a real mondrian. No public test AVB keys,
   `--flags 3`, SELinux permissive modes or unmanaged firmware are allowed.
6. Test normal/recovery mount, fastbootd, OTA A/B slot switching, FBE
   decryption and untouched userdata on a **test device**, then CTS/VTS
   as appropriate.

Do **not** import the historical LineageOS product, init service tree,
proprietary vendor binaries, old FM-radio modules or other device configs.

## 4. Host source-only verification

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_fstab.py
python3 tools/validate_fstab.py --stock <OS3 vendor>/etc/fstab.qcom
python3 tools/verify_reference_boot_layout.py --online
```

The last two commands download the pinned **public** LF and LineageOS
reference sources to check their facts, not to import source or vendor
firmware into PE. Build image acceptance remains unproven even if every
host-source check passes.
