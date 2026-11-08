# PixelExperience-Reborn AOSP 17 / mondrian: final Android boot image contract

Target: **POCO F5 Pro / Redmi K60 (mondrian, SM8475)**. Hardware
reference: `LF52406/mondrian_android_device_xiaomi_sm8450-common`,
`lineage-24.0/BoardConfigCommon.mk` (read-only technical reference).

## The actual output is .img, NOT a raw kernel Image

The Linux compilation generates `arch/arm64/boot/Image` (a temporary
**kernel input**). Android's build system must package it into:

| Final build artifact | Device function | Required |
| --- | --- | --- |
| `boot.img` | boot header v4 plus kernel and generic boot payload | Yes |
| `dtbo.img` | selected *mondrian* cape/PM8008/M11A/camera overlays | Yes |
| `vendor_boot.img` | header v4, vendor DTB, ramdisk fragments and bootconfig | Yes |
| `recovery.img` | dedicated recovery partition image | Yes |
| `vendor_dlkm.img` | matched signed/qualified Qualcomm kernel modules | Yes |
| `vbmeta.img`, `vbmeta_system.img` | Android Verified Boot metadata | Yes |

`Image` is **never** a substitute for `boot.img` and is not considered
an acceptable final flashable output. It is normal to find the
intermediate `Image` under kernel build intermediates.

## Own AOSP image-packaging source

`BoardConfigBootImages.mk` contains the independently maintained
boot header v4, 4096-byte page size, partition sizes, kernel Kconfig
fragments, dynamic partitions, A/B update list and DTBO requests from
the published mondrian board reference. The separate `BOARD_KERNEL_IMAGE_NAME
:= Image` setting defines only what file the Android build reads to
create `boot.img`.

`BoardConfigCommon.mk` **does not** include the file by default.
`PE_MONDRIAN_BOOT_STAGE=qualified` is a guarded opt-in and the
included file rejects the build until all of these have been
independently verified:

- compiled kernel, Qualcomm modules, DTBO and exported KMI/Module.symvers;
- proper vendor firmware/HAL, first-stage module load and fstab placement;
- KeyMint, FBE and recovery decryption on physical device;
- Android Verified Boot keys, descriptors, signing and rollback indexes.

The source is *not yet sufficient to produce those images*. In
particular, no validated `vendor_boot` fragment/module set, production
AVB key or target firmware is present in this draft; there are no
bootable release images in PE-Reborn yet. Never bypass the checks just
to make an output filename exist.

AOSP's boot header v4 defines `boot.img` separately from `vendor_boot.img`.
The vendor-specific DTB belongs in the vendor_boot image. This is not
the same thing as the **separate** `dtbo.img` partition. The older
Qualcomm standalone build config's header version 3 is not the final
Android product boot header. Do not copy that v3 value to mondrian's
Android BoardConfig.

## Automated release artifact preflight

After a future real full AOSP 17 product build:

```bash
python3 device/xiaomi/sm8450-common/tools/verify_boot_artifacts.py \
  out/target/product/mondrian \
  --json out/target/product/mondrian/boot-artifact-check.json
```

The check fails if `boot.img`, `dtbo.img`, `vendor_boot.img`,
`recovery.img`, `vendor_dlkm.img` or the vbmeta images are missing,
empty, unexpectedly large or have incompatible Android boot v4 /
vendor_boot v4 / Android DT table / AVB header magic. It explicitly
rejects a directory containing only raw `Image`.

This is **not** proof of a valid AVB signature, DT overlay selection,
kernel/modules KMI, ramdisk correctness or a bootable ROM; those
require further build/cryptographic and on-device tests. Unit tests
use deliberately non-bootable synthetic headers solely to validate
the fail-closed checker. They are not flash images.

References:
- https://source.android.com/docs/core/architecture/bootloader/boot-image-header
- https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions
- https://source.android.com/docs/core/architecture/kernel/modules
