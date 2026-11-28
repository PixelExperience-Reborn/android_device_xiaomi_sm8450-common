# Proprietary files for PE-Reborn Android 17 on mondrian

Scope: **POCO F5 Pro / Redmi K60 (mondrian, SM8475)** only. This document
explains which closed vendor files the product needs, where they come from,
and how they are reproduced.

## Policy

* Only components **without source in the PE Android 17 build manifest**
  are listed. For the first stable build that includes the Qualcomm HALs
  (display, AudioReach PAL/AGM, IPACM, thermal, USB, Wi-Fi, lights, GNSS):
  their source repositories (`hardware/qcom-caf`, `vendor/qcom/opensource`)
  are not in the manifest. The HALs Android 17 does not accept at FCM level 7
  (health, power, Bluetooth audio, supplicant/hostapd, IR, vibrator `default`,
  fingerprint UDFPS, NFC) come from source (docs/A17_HAL_MATRIX.md).
  `tests/test_proprietary_files.py` rejects excluded and AOSP-built files.
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
   Codec2, sensor multi-HAL, KeyMint, ...), including the passthrough
   implementations of `vendor/lib64/hw` that HIDL services register with
   `registerPassthroughServiceImplementation` (Gatekeeper, Bluetooth HCI and
   config store, GNSS 2.1, boot control, capability config store, service
   tracker, eSE power manager): `DT_NEEDED` does not show them.
   The same holds for every library a blob loads by name: the listeners of
   qseecomd (RPMB, SSD, ...) and of the FastRPC daemons, the QCRIL modules
   (voice, SMS, data, ...), `libgnss`, `liboemcrypto`, `libqti-perfd`, the
   Adreno compiler libraries and the CHI camera plugins. The lists hold the
   closure of the names in the listed ELF files that exist in the stock vendor
   (nothing missing is left), minus the excluded subsystems below.
2. The complete `DT_NEEDED` closure inside the vendor partition.
3. Minus every file produced by our source repositories (389 outputs of 24
   repositories) and by AOSP (`android.hardware.*`, `android.hidl.*`).
4. Plus the data each subsystem reads (firmware, configuration, calibration)
   and the per-service init scripts.

| List | Files | Size |
| --- | --- | --- |
| `sm8450-common/proprietary-files.txt` (Qualcomm SoC stack) | 705 | 242 MB |
| `mondrian/proprietary-files.txt` (device-specific, incl. one `odm` file) | 899 | 1195 MB |

Deliberately excluded: the MIUI camera app engine (`libmialgoengine`,
`com.xiaomi.plugin.*`, `campostproc`, `camera.xiaomi.so`), DPM,
WiFi Display, Perf/IOP, Soter, Mlipay, Trusted UI, Dolby, VPP, XR tracking,
diagnostics, factory tests and the `vendor.xiaomi.*` services. Client
libraries the radio stack links directly (for example `libcneapiclient`)
stay, because their users cannot load without them.

IMS (VoLTE, video calling, Wi-Fi calling) adds the stock Qualcomm apps and
libraries of system_ext and product, one library of the system image and
CNE/IWLAN of vendor (docs/IMS.md). `tools/extract_proprietary.py` reads these
partitions too; the system image is system-as-root (`system/<path>` is
`<image root>/system/<path>`).

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

The libraries the blobs link from Qualcomm source repositories elsewhere
(`libgralloc.qti`, `libqdMetaData`, `libdisplayconfig.qti`,
`libqti_vndfwk_detect`, `libgps.utils`/`libloc_core`/`liblocation_api`,
`libcld80211`, `librmnetctl`, the `vendor.qti.*` interface libraries) are the
stock ones in these lists: none of those repositories is in the PE Android 17
build manifest. Replacing a stock library with its source build means moving
the whole stack it belongs to (for example display: composer, allocator,
mapper and `libgralloc.qti` together), never one library.

## Authored in the device trees

* VINTF (`vintf/`): the device manifest at FCM target level 7, the framework
  matrix extension for the `vendor.qti.*` HALs and the device matrix
  (docs/A17_HAL_MATRIX.md, `tests/test_vintf.py`).
* Platform init (`rootdir/etc/init.qcom.rc`, `init.target.rc`) and the odm
  ueventd rules of mondrian (docs/INIT_SERVICE_OWNERSHIP.md).
* The stock camera provider script is listed unmodified. Its `interface`
  lines for MIUI services nobody registers are harmless: init only uses
  `interface` to start a service on demand, and Android 17 init does not
  check them against VINTF.
* SELinux policy for the closed services (stage D).

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
