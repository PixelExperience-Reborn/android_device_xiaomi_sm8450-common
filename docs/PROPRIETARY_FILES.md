# Proprietary files for PE-Reborn Android 17 on mondrian

Scope: **POCO F5 Pro / Redmi K60 (mondrian, SM8475)** only. This document
explains which closed vendor files the product needs, where they come from,
and how they are reproduced.

## Policy

* Only components **without source** are listed. Anything our source
  repositories build (display, audio PAL/AGM/HAL, IPACM, power, thermal HAL,
  vibrator, USB, health, NFC HAL, Wi-Fi HAL, lights, GNSS HAL wrapper) is
  never taken from the firmware; a test rejects such entries.
* Files come from **one** official Xiaomi OTA for mondrian (its `vendor` and
  `odm` partitions), never from another device, another ROM or a third-party
  blob repository.
* AOSP libraries that Xiaomi copied into its vendor partition (Codec2,
  bufferpool, minijail, netd HIDL, hidltransport) are built from the AOSP 17
  sources of our base instead; the stock copies are not used.
* The files are **not redistributed**. `HARDWARE_CONTRACT.md` requires
  permission to redistribute, which we do not have. The repositories hold the
  lists, the pinned source and the tools; `tools/extract_proprietary.py`
  reproduces the files from the official OTA and checks every SHA-256.
* VINTF manifests and platform init scripts are written in our device trees,
  not copied (see "Authored in the device trees").

## Source

`proprietary/ota-source.json` pins the official full OTA
`mondrian-ota_full-OS3.0.8.0.VMNCNXM-user-15.0-3fb07519a6.zip`
(Redmi/mondrian/mondrian:15/AQ3A.250226.002, security patch 2026-05-01):

* the payload metadata SHA-256 (identical on `bigota.d.miui.com` and the
  official Xiaomi Aliyun mirror);
* the `vendor` and `odm` partition sizes and SHA-256, checked against the
  signed payload manifest and per operation while extracting.

Its vendor partition is still the launch Android 12 vendor
(`ro.board.api_level=31`, VINTF `target-level="6"`,
`Redmi/mondrian/mondrian:12/SKQ1.230401.001`); Xiaomi updates only the
system side.

## How the lists were derived

1. Roots: the closed service binaries and dlopen'ed plugins of each
   subsystem (camera provider, CamX/CHI nodes and sensor modules, QCRIL,
   Codec2, sensor multi-HAL, KeyMint, ...).
2. The complete `DT_NEEDED` closure inside the vendor partition.
3. Minus every file produced by our source repositories (389 outputs of 24
   repositories) and by AOSP (`android.hardware.*`, `android.hidl.*`).
4. Plus the data each subsystem reads (firmware, configuration, calibration)
   and the per-service init scripts.

| List | Files | Size |
| --- | --- | --- |
| `sm8450-common/proprietary-files.txt` (Qualcomm SoC stack) | 361 | 113 MB |
| `mondrian/proprietary-files.txt` (device-specific, incl. one `odm` file) | 879 | 994 MB |

Deliberately excluded: the MIUI camera app engine (`libmialgoengine`,
`com.xiaomi.plugin.*`, `campostproc`, `camera.xiaomi.so`), CNE daemon, DPM,
WiFi Display, Perf/IOP, Soter, Mlipay, Trusted UI, Dolby, VPP, XR tracking,
diagnostics, factory tests and the `vendor.xiaomi.*` services. Client
libraries the radio stack links directly (for example `libcneapiclient`)
stay, because their users cannot load without them.

The camera is taken as the complete Xiaomi HAL: `com.qti.chiusecaseselector`
and `camera.qcom.so` reference 24 Xiaomi CHI nodes themselves, so removing
them could break pipeline creation. Pruning it further needs device tests.

## Compatibility evidence

**Kernel.** Every firmware file our drivers request exists in the OTA under
the requested name: KGSL `a730_sqe.fw`, `gmu_gen70000.bin`, `a730_zap`;
camera `CAMERA_ICP`; video `vpu20_4v`; EVA `evass`; touch
`goodix_*_m11a.bin` (names from our DT); amplifier `aw882xx_acf.bin`.

Comparing the OTA kernel modules with ours, built from the launch Xiaomi
release, by their source strings:

| Driver | Ours | OS3.0.8.0 |
| --- | --- | --- |
| Camera, EVA, MMRM, audio core, IPA | launch release | unchanged |
| KGSL | KERNEL.PLATFORM r1-07800 | at least r1-14900 |
| FastRPC | r1-07800 | at least r1-15100 |
| cnss2 | r1-07800 | at least r1-14400 |
| Video | VIDEO.LA.2.0 r1-03100 | at least r1-08200 |

If GPU, video, DSP or Wi-Fi misbehave on the device, these are the exact
Qualcomm CodeLinaro releases to update the drivers to.

**Consumer IR** needs no blob: our kernel builds Xiaomi's `ir-spi` driver
(`CONFIG_IR_SPI=m`, `/dev/ir_spi`, DT node `ir-spi` in `xiaomi-sm8475-common.dtsi`),
which is all the closed `consumerir.qcom.so` uses, and `android.hardware.ir@1.0`
no longer exists in AOSP 17. IR becomes an AIDL HAL in `hardware/xiaomi`.

**Android 17.** The AOSP 17 framework accepts vendor FCM level 7 and newer.
35 of the 40 standard HALs of this vendor satisfy level 7; the other five
come from source: `wifi.supplicant 1.4`, `wifi.hostapd 1.3` (AOSP
wpa_supplicant_8 AIDL), `health 2.1` (healthd-ext AIDL), `bluetooth.audio
2.0` (AIDL) and `dumpstate 1.1` (AIDL).

**Libraries the blobs expect from the platform** (checked against the exact
`android-17.0.0_r1` sources of our base):

* 59 of the 60 `android.hardware.*@x.y` HIDL libraries still exist in
  `hardware/interfaces` (only `ir@1.0` is gone, see above).
* Every former VNDK library they use (`libutils`, `libcutils`, `libbinder`,
  `libhidlbase`, `libion`, `libui`, ...) exists with a vendor variant. AOSP 17
  clears `BOARD_VNDK_VERSION`, so these vendor variants are what the blobs will
  load (`linkerconfig` searches `/vendor/lib64` before any VNDK APEX).
* Seven AIDL libraries are named `-ndk_platform` in the blobs and `-ndk` in
  AOSP 17 (KeyMint V1, SecureClock V1, SharedSecret V1, identity V3,
  keymaster V3, GNSS V1, `vendor.qti.hardware.display.config` V2); all those
  frozen versions exist, so a NEEDED rename at extraction time suffices.
* Symbol screening of 440 64-bit blobs against Google's VNDK snapshots v31
  (Android 12) and v34 (Android 14) found one removed import:
  `GraphicBufferSource::configure` used by the stock copy of
  `libcodec2_hidl@1.0`, which is now built from AOSP instead. The remaining
  Android 14 to 17 gap is checked on the first build.

## Source counterparts the blobs depend on

The lists assume these modules come from source. In the current PE AOSP 17
manifest none of these repositories is included, and in every one of them the
`seventeen` branch is identical to `fourteen` (Android 14 code); Android 17
work exists only in separate branches:

| Repository | Modules the listed blobs link | Android 17 branch |
| --- | --- | --- |
| `hardware_qcom-caf_sm8450_display` | `libgralloc.qti`, `libgrallocutils`, `libqdMetaData`, `libdisplayconfig.qti` | none |
| `vendor_qcom_opensource_display` | `libgralloc.qti`, `libqdMetaData`, `libdisplayconfig.qti` | `audit/a17-qcom-display-hwc3-aidl-20261107` |
| `vendor_qcom_opensource_interfaces` | `vendor.qti.hardware.display.{allocator,mapper,mapperextensions}`, `camera.{aon,postproc}`, `btconfigstore`, `fm` | `port/a17-mondrian-qcom-interfaces-aidl-20261107` |
| `hardware_qcom-caf_common` | `libqti_vndfwk_detect` | `integrate/a17-sm8450-qcom-common-20261105` |
| `hardware_qcom_gps` | `libgps.utils`, `libloc_core`, `liblocation_api` | `audit/a17-mondrian-gnss-aidl-20261105` |
| `hardware_qcom-caf_wlan` | `libcld80211` | `audit/a17-mondrian-wlan-ownership-20261105` |
| `vendor_qcom_opensource_dataservices` | `librmnetctl` | `audit/a17-qcom-dataservices-rmnet-rtnetlink-boundary-20261108` |
| `hardware_qcom-caf_sm8450_audio_{pal,agm,primary-hal}` | PAL/AGM/HAL that load the closed AudioReach libraries | none |

Bringing these into the Android 17 manifest at verified revisions is a
prerequisite for using the lists.

## Authored in the device trees (next stage)

* VINTF manifest with `target-level` 7 declaring the HALs of the listed
  services (camera provider 2.4-2.7 `legacy/1`, radio 1.6 and radio config
  1.3, sensors 2.1, Codec2 1.0, KeyMint, Gatekeeper, identity, GNSS AIDL,
  DRM Widevine 1.4, Bluetooth 1.0, IR 1.0, fingerprint 2.1, QTI QSEECom/QTEE,
  DSP service).
* Init: `vendor.pd_mapper` (stock `init.target.rc`), `time_daemon` and
  `vendor.qrtr-ns` (stock `init.qcom.rc`), and the camera provider service.
  The stock camera provider script also declares the MIUI
  `campostproc`/`quickcamera`/`bgservice` interfaces, so it is rewritten
  without them.
* Soong/Make build rules for the prebuilts and the VNDK v31 strategy, to be
  validated with a real AOSP 17 tree.
* SELinux policy for the closed services.

## Usage

```
# Verify both lists against the official OTA (downloads only the vendor partition):
python3 tools/extract_proprietary.py --verify-only

# Populate vendor/xiaomi/sm8450-common and vendor/xiaomi/mondrian in an Android tree:
python3 tools/extract_proprietary.py

# From an already extracted vendor partition or image:
python3 tools/extract_proprietary.py --vendor-dir /path/to/vendor
python3 tools/extract_proprietary.py --vendor-image vendor.img
```

`fsck.erofs` (erofs-utils) is required to read the EROFS vendor image.

## Open points

Device testing: camera, GPU, video, Wi-Fi with the drivers listed above;
ultrasound proximity through PAL; VoLTE/VoWiFi with the China modem
configuration and the user's carrier.
