# SPDX-License-Identifier: Apache-2.0
#
# PixelExperience-Reborn Android 17: common board of Xiaomi SM8450/SM8475
# (taro) devices; in this project, mondrian (POCO F5 Pro / Redmi K60).
#
# Boot image layout, partitions, super and AVB follow the stock firmware
# OS3.0.8.0.VMNCNXM (official full OTA, payload manifest sha256
# 771becf938d98ba206d09c674bad62054ac43737ca1470bed51479ffb9d5fd2a);
# tests/test_board_config.py checks every value against it.

COMMON_PATH := device/xiaomi/sm8450-common

# Architecture. SM8475 has Cortex-X2, A710 and A510 cores (Armv9.0-A,
# which includes every mandatory feature of Armv8.5-A). armv8-5a uses them
# (LSE atomics, dot product, PAC/BTI branch protection) without SVE2, which
# armv9-a would let the compiler emit although Qualcomm does not enable SVE
# on this SoC. Soong has no Cortex-A510/A710 tuning; cortex-a76 is its
# closest one. The bionic runtime variants are those of the stock vendor
# (ro.bionic.cpu_variant=kryo300, ro.bionic.2nd_cpu_variant=cortex-a75).
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-5a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := cortex-a76
TARGET_CPU_VARIANT_RUNTIME := kryo300

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-2a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := cortex-a75
TARGET_2ND_CPU_VARIANT_RUNTIME := cortex-a75

# Platform
TARGET_BOARD_PLATFORM := taro
TARGET_BOOTLOADER_BOARD_NAME := taro
TARGET_NO_BOOTLOADER := true

# Boot images: header v4, as stock boot, vendor_boot and recovery.
# Offsets from base 0 are those of the stock vendor_boot.
BOARD_BOOT_HEADER_VERSION := 4
BOARD_KERNEL_PAGESIZE := 4096
BOARD_KERNEL_BASE := 0x00000000
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_RAMDISK_OFFSET := 0x01000000
BOARD_KERNEL_TAGS_OFFSET := 0x00000100
BOARD_DTB_OFFSET := 0x01f00000
BOARD_MKBOOTIMG_ARGS += \
    --header_version $(BOARD_BOOT_HEADER_VERSION) \
    --kernel_offset $(BOARD_KERNEL_OFFSET) \
    --ramdisk_offset $(BOARD_RAMDISK_OFFSET) \
    --tags_offset $(BOARD_KERNEL_TAGS_OFFSET) \
    --dtb_offset $(BOARD_DTB_OFFSET)

# Command line and bootconfig of the stock vendor_boot (without Xiaomi's
# swinfo/mtdoops build fingerprints).
BOARD_KERNEL_CMDLINE := \
    video=vfb:640x400,bpp=32,memsize=3072000 \
    disable_dma32=on
BOARD_BOOTCONFIG := \
    androidboot.hardware=qcom \
    androidboot.memcg=1 \
    androidboot.usbcontroller=a600000.dwc3

BOARD_RAMDISK_USE_LZ4 := true
BOARD_INCLUDE_DTB_IN_BOOTIMG := true
# The stock recovery image has no kernel: the bootloader takes it from boot.
BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true

# Raw partitions. boot, vendor_boot and recovery are the stock image sizes.
# dtbo: stock pads its image to 23 MiB, but the partition holds 24 MiB (as
# the dtbo images of other mondrian builds flashed on this device show);
# AVB verifies dtbo through its hash descriptor in vbmeta, whatever the
# padding, so the image fills the 24 MiB partition.
BOARD_FLASH_BLOCK_SIZE := 262144
BOARD_BOOTIMAGE_PARTITION_SIZE := 0x0C000000
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 0x06000000
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 0x06400000
BOARD_DTBOIMG_PARTITION_SIZE := 0x01800000

# Dynamic partitions: one group, as stock, without Xiaomi's mi_ext.
# The super size is the device's (the OTA does not carry it); the group
# takes all of it except the 4 MiB metadata reserve.
BOARD_SUPER_PARTITION_SIZE := 9126805504
BOARD_SUPER_PARTITION_GROUPS := qti_dynamic_partitions
BOARD_QTI_DYNAMIC_PARTITIONS_SIZE := 9122611200
BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST := \
    odm \
    product \
    system \
    system_ext \
    vendor \
    vendor_dlkm

# Filesystems: the logical partitions are EROFS, /data F2FS, /metadata ext4
# (rootdir/etc/fstab.qcom, derived from the stock fstab).
TARGET_USERIMAGES_USE_EROFS := true
TARGET_USERIMAGES_USE_F2FS := true
TARGET_USERIMAGES_USE_EXT4 := true
BOARD_EROFS_COMPRESSOR := lz4hc,9
BOARD_EROFS_PCLUSTER_SIZE := 65536
BOARD_ODMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_PRODUCTIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_SYSTEM_EXTIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_VENDOR_DLKMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_USES_METADATA_PARTITION := true

TARGET_COPY_OUT_ODM := odm
TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_SYSTEM_EXT := system_ext
TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm

# Vendor AIDs (vendor_qti_diag, vendor_qrtr, ...) and file capabilities of
# the stock vendor daemons, as in its etc/passwd and fs_config_files.
TARGET_FS_CONFIG_GEN := $(COMMON_PATH)/config.fs

# A/B: the images this build makes. The stock firmware images (abl, aop,
# modem, tz, xbl, ...) are added with the proprietary files of the device.
AB_OTA_UPDATER := true
AB_OTA_PARTITIONS += \
    boot \
    dtbo \
    odm \
    product \
    recovery \
    system \
    system_ext \
    vbmeta \
    vbmeta_system \
    vendor \
    vendor_boot \
    vendor_dlkm

# Recovery uses the stock-derived fstab of first stage and vendor.
TARGET_RECOVERY_FSTAB := $(COMMON_PATH)/rootdir/etc/fstab.qcom
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888

# Verified boot, with the chain of the stock vbmeta: boot, dtbo,
# vendor_boot, odm, vendor and vendor_dlkm in vbmeta; recovery chained at
# rollback location 1 and vbmeta_system (system, system_ext, product) at 2.
# The AOSP test keys are the default; release builds sign with their own.
BOARD_AVB_ENABLE := true
BOARD_AVB_RECOVERY_KEY_PATH := external/avb/test/data/testkey_rsa2048.pem
BOARD_AVB_RECOVERY_ALGORITHM := SHA256_RSA2048
BOARD_AVB_RECOVERY_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_RECOVERY_ROLLBACK_INDEX_LOCATION := 1
BOARD_AVB_VBMETA_SYSTEM := product system system_ext
BOARD_AVB_VBMETA_SYSTEM_KEY_PATH := external/avb/test/data/testkey_rsa2048.pem
BOARD_AVB_VBMETA_SYSTEM_ALGORITHM := SHA256_RSA2048
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX_LOCATION := 2

# Security patch level of the stock OS3.0.8.0 vendor, whose proprietary
# files the vendor partition carries (ro.vendor.build.security_patch).
VENDOR_SECURITY_PATCH := 2026-02-01

# Properties of the stock OS3.0.8.0 vendor and odm the shipped components
# read (vendor.prop, odm.prop); devices append their own vendor.prop.
TARGET_VENDOR_PROP += $(COMMON_PATH)/vendor.prop
TARGET_ODM_PROP += $(COMMON_PATH)/odm.prop

# VINTF: the device manifest at FCM target level 7 (HALs of the stock
# services this build ships; HALs built from source add their own
# fragments), the framework matrix extension for the Qualcomm vendor HALs
# and the device matrix. See docs/A17_HAL_MATRIX.md.
DEVICE_MANIFEST_FILE += $(COMMON_PATH)/vintf/manifest.xml
DEVICE_MATRIX_FILE := $(COMMON_PATH)/vintf/compatibility_matrix.xml
DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += $(COMMON_PATH)/vintf/framework_compatibility_matrix.xml

# SELinux: the bring-up vendor policy (sepolicy/vendor, generated by
# tools/gen_bringup_sepolicy.py from the stock OS3.0.8.0 policy): the domains,
# init transitions and contexts of the services this build ships. Until the
# allow rules from the denials of the device are in, userdebug and eng builds
# boot permissive (init honours androidboot.selinux=permissive only on them);
# user builds stay enforcing.
BOARD_VENDOR_SEPOLICY_DIRS += $(COMMON_PATH)/sepolicy/vendor
# Contexts of the services built from source here (hand written).
BOARD_VENDOR_SEPOLICY_DIRS += $(COMMON_PATH)/sepolicy/source
ifneq ($(TARGET_BUILD_VARIANT),user)
BOARD_BOOTCONFIG += androidboot.selinux=permissive
endif

# Bring-up diagnostics, userdebug and eng only. A fatal init error (first
# stage, SELinux, a critical service) reboots to recovery instead of the
# bootloader: the reboot is warm, so the kernel log stays in pstore, and
# rootdir/etc/init/debug/pe_bootlog.rc keeps it on /metadata. printk.devkmsg=on
# lifts the rate limit on what init writes to the kernel log, so none of the
# first stage messages is dropped.
ifneq ($(TARGET_BUILD_VARIANT),user)
BOARD_BOOTCONFIG += androidboot.init_fatal_reboot_target=recovery
BOARD_KERNEL_CMDLINE += printk.devkmsg=on
endif

# Proprietary files
include vendor/xiaomi/sm8450-common/BoardConfigVendor.mk
