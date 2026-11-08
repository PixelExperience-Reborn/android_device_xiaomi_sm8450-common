# SM8475 / taro common hardware contract for PE-Reborn Android 17

Target device: **mondrian only** (POCO F5 Pro / Redmi K60). The directory
name `sm8450-common` follows the established Qualcomm BSP path convention;
it is **not** a claim that the physical SoC is SM8450.

This common configuration is authored for an **independent AOSP 17 / PE-Reborn
product**. It does not include another ROM product makefile or service stack.

## Inputs to qualify before enabling builds

| Area | Gate |
| --- | --- |
| Kernel | OEM Xiaomi SM8475 kernel source, Qualcomm downstream revisions and security provenance, configuration and compiler |
| External modules | Same kernel/KMI, kernel symbols, first-stage and vendor_dlkm load order |
| Device trees | Matching DT/DTBO source, panel/touch variant and bootloader compatibility |
| Partitions | Exact boot/recovery/vendor_boot/DTBO, dynamic super, A/B OTA and fstab based on grounded partition evidence |
| Security | AVB keys and rollback strategy, KeyMint/FBE, VINTF/FCM, neverallow and verified SELinux |
| Display | DSI DRM, HWC, allocator and display-service ABI, panel ID and refresh-rate/brightness behavior |
| Touch | Identify actual IC, input events, firmware and interrupt failures; compare controller driver with OEM source |
| UDFPS | Vendor fingerprint HAL ABI, secure path, coordinates, SurfaceFlinger/HWC illumination and lockscreen |
| Radio | Modem firmware/vendor ABI, radio interfaces, emergency calls, IMS registration and carrier behavior |
| Other hardware | Camera/media, Wi-Fi/Bluetooth/GNSS/NFC, sensors, haptics, charging and thermal |

## Source strategy

1. Official AOSP 17 and PE-Reborn framework/product layer are the ROM base.
2. Xiaomi kernel publication and Qualcomm hardware implementations are
   **candidates for independent adaptation**, not ready-made Android 17 builds.
3. Original PixelExperience trees provide architectural examples, not the
   driver versions or build settings for mondrian.
4. LineageOS device trees may be **read-only** compatibility references;
   no product, overlays, packages, or Lineage-specific HAL APIs are inherited.
5. Proprietary blobs require verifiable OEM provenance, checksum and
   permission to redistribute. The two vendor repositories are not substitutes
   for a source/ABI audit.
6. Keep FM radio outside the product; defer optional ROM features until boot.

## Important release blockers

No vendor blobs, boot image layout, dtbo, kernel config, SELinux policy,
partition sizes, VINTF matrix or production keys are supplied by this stub.
Do **not** treat passing host source checks as Soong/CTS/VTS or device proof.


## 2026-11-08 — independent common platform implementation

`BoardConfigCommon.mk` now declares the device's confirmed `taro`
bootloader ownership (`TARGET_BOOTLOADER_BOARD_NAME`, no bootloader
build), standard Android output partition roots for
`odm/product/system_ext/vendor/vendor_dlkm`, and presence of a
separate metadata partition. These are early board properties, **not**
proof of boot image, OTA, super layout, FBE or AVB compatibility.

Storage/recovery source audit exposed a concrete risk: the inspected
main fstab mounts logical partitions as EROFS, but the reference
recovery fstab still declares ext4 and uses different /data encryption
flags. `tools/compare_fstab_pair.py` and
`tests/test_storage_contract.py` now block incompatible candidate
fstab pairs; **no fstab has been enabled in this new tree**.

The reviewed Qualcomm init reference has core QRTR/peripheral
manager/audio/sensors services, and old networking/debug helpers.
`docs/INIT_SERVICE_OWNERSHIP.md` prevents treating those services as
unnecessary background processes without vendor binary, VINTF and
SELinux evidence. No old init service is imported or modified.

The old module list contains FM-related drivers; they are explicitly
excluded from our initial product. No upstream LineageOS service,
old AVB test key, AOSP14-specific HAL, or unverified system property
is activated.
