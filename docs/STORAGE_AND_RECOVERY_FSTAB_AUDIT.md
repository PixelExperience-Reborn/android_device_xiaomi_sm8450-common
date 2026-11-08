# AOSP 17 / SM8475 mondrian — first-stage vs recovery storage preflight

**State:** reference-only comparison, no fstab installed in the PE-Reborn
product. `BoardConfigCommon.mk` now defines the physical logical
copy-out names (`odm`, `product`, `system_ext`, `vendor`,
`vendor_dlkm`) and presence of a dedicated metadata partition.
Actual filesystem, dynamic super sizing, boot, OTA and key-management
configuration remain **unselected**.

## Verified published device-tree discrepancy

The independently inspected working LF52406 common source has these
two **different reference configurations**:

| Mount | Main fstab.qcom | Recovery recovery.fstab |
| --- | --- | --- |
| /system, /system_ext, /product | `erofs` | `ext4` |
| /vendor, /odm | `erofs` | `ext4` |
| /vendor_dlkm | `erofs` | no corresponding recovery entry |
| /data | `f2fs` with v2 + inlinecrypt/wrappedkey values | `f2fs`, legacy `fileencryption=ice` |
| /metadata | `ext4` dedicated first-stage mount | `ext4` metadata with additional flags |

This is a **source mismatch**, not a claim that the currently installed
firmware has either exact layout. Mixing these exact two files in a
single EROFS release can cause recovery mounts to fail. Never install
a recovery fstab merely because it exists in a well-known ROM.

The actual production fstab must be authored from verified partition
metadata, be consistent with selected filesystem image output types,
and preserve Android17 `fs_mgr` and `vold` encryption requirements.
For recovery, match the same filesystem formats and avoid legacy
`fileencryption=ice` without proof of a compatible KeyMint/wrapped-key
chain. Validate /data decryption on a test device **without wiping**.

## Executable static gate

`tools/compare_fstab_pair.py` parses two ordinary fstab files
(`<device> <mount> <fstype> <mount_flags> <fs_mgr_flags>`). It reports
type disagreement for corresponding logical partitions, missing
recovery coverage for critical ones, and differing /data
`fileencryption=` or `metadata_encryption=` contracts.
Exit nonzero blocks a selected fstab pair from release approval.

```bash
python3 tools/compare_fstab_pair.py path/to/fstab.qcom path/to/recovery.fstab
```

This tool is a **preflight**, not proof of Android17 recovery
decryption, actual ext4/EROFS image compatibility, AVB, bootloader
metadata, UFS or OTA behaviour. Source tests cover known mismatches.

## Module and safety notes

The historical second-stage module list includes
`radio-i2c-rtc6226-qca.ko` and `bt_fm_slim.ko`. They are
legacy reference entries, **not selected** into this new PE device.
FM radio remains excluded. Qualcomm modules and any real
`modules.load` require a matched kernel `Module.symvers`, KMI,
vendor_boot/vendor_dlkm placement and actual runtime verification.

Do not bring forward `vendor/lineage` includes, public AVB test
keys, `--flags 3`, or unqualified QCOM SELinux/ROM-specific HALs.

Source references (read-only):
- https://github.com/LF52406/mondrian_android_device_xiaomi_sm8450-common/blob/lineage-24.0/rootdir/etc/fstab.qcom
- https://github.com/LF52406/mondrian_android_device_xiaomi_sm8450-common/blob/lineage-24.0/rootdir/etc/recovery.fstab
- https://github.com/LF52406/mondrian_android_device_xiaomi_sm8450-common/blob/lineage-24.0/modules.list.second_stage

## Pinned evidence verification

`tools/verify_reference_storage.py` downloads the two **historical
reference** fstabs from a single immutable LF52406 commit, validates
their original Git blob IDs and expects the EROFS versus ext4 and
`fileencryption` differences to be detected. The result is checked
by the source-only GitHub workflow
`.github/workflows/fstab-reference-check.yml`. A successful result
means the mismatch has been reproduced and **must still be fixed**
before enabling recovery, not that recovery is functional.
