# PE-Reborn AOSP 17 / mondrian — native storage and boot-chain implementation

**State: independent source implementation; NOT an installed fstab; no bootable
kernel, recovery, vendor partition or complete target ROM has been produced.**

Target is **POCO F5 Pro / Redmi K60 (mondrian, SM8475)**, with a shared
taro/SM8450-named BSP. This is not a claim that the physical SoC is SM8450.

## 1. Native source (already added)

- `rootdir/etc/fstab.qcom`: independently authored **normal-boot candidate**.
- `rootdir/etc/recovery.fstab`: independently authored **recovery candidate**,
  with the same logical filesystem and /data encryption contract.
- `tools/validate_native_fstab.py`: strict source-level comparison and AVB,
  mount-stage and encryption guards.
- `tools/compare_fstab_pair.py`: generic main/recovery consistency parser,
  now rejecting malformed/duplicate fields.
- `tests/test_native_fstab.py`: actual candidate regression and negative tests.

Neither fstab is referenced by active `PRODUCT_COPY_FILES` or
`TARGET_RECOVERY_FSTAB`. **Do not install** until verified product image
filesystem, bootloader layout and storage HAL/KeyMint are available.

| Mounts | Candidate format | Selection |
| --- | --- | --- |
| `/system`, `/system_ext`, `/product` | EROFS; A/B logical first stage; `vbmeta_system` | Not qualified for production |
| `/vendor`, `/odm`, `/vendor_dlkm` | EROFS; A/B logical first stage; primary AVB | Not qualified for production |
| `/metadata` | ext4; first-stage mount | Not qualified for production |
| `/data` | F2FS, v2 FBE + inlinecrypt + wrappedkey_v0; matching recovery flags | Not decrypted or boot tested |
| `/misc` | block device / emmc reference | Not bootloader validated |

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
python3 tools/validate_native_fstab.py
python3 tools/verify_reference_storage.py
python3 tools/verify_reference_boot_layout.py --online
```

The last two commands download the pinned **public** LF and LineageOS
reference sources to check their facts, not to import source or vendor
firmware into PE. Build image acceptance remains unproven even if every
host-source check passes.
