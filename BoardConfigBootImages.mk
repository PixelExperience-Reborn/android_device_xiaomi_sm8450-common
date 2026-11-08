# SPDX-License-Identifier: Apache-2.0
# PixelExperience-Reborn AOSP 17 -- mondrian (SM8475/taro).
#
# THIS IS A GUARDED, INACTIVE AOSP IMAGE-PACKAGING CONFIGURATION.
# Include only after the kernel/Qualcomm modules/DTBO, proprietary vendor
# firmware, FBE and verified-boot chain have been built and qualified.
# Output images are boot.img, dtbo.img, vendor_boot.img and recovery.img,
# NOT a naked Linux Image. "Image" is the compiler's temporary kernel input.
#
# Do not bypass the gates to make the Android build appear successful.
ifneq ($(PE_MONDRIAN_BOOT_STAGE),qualified)
$(error Mondrian boot image config included outside an explicitly qualified stage)
endif
ifneq ($(PE_MONDRIAN_KERNEL_BSP_VERIFIED),true)
$(error Mondrian requires compiled Image + modules + DTBO and matched Module.symvers)
endif
ifneq ($(PE_MONDRIAN_VENDOR_FIRMWARE_VERIFIED),true)
$(error Mondrian vendor HAL/firmware and first-stage modules have not been qualified)
endif
ifneq ($(PE_MONDRIAN_FBE_AND_RECOVERY_VERIFIED),true)
$(error Mondrian FBE/KeyMint and normal/recovery fstab layouts require hardware validation)
endif
ifneq ($(PE_MONDRIAN_AVB_SIGNING_VERIFIED),true)
$(error Mondrian boot/vbmeta production AVB keys and rollback strategy not verified)
endif

# Kernel input to the AOSP build system. Not a flashable user-facing artifact.
TARGET_KERNEL_SOURCE := kernel/xiaomi/sm8450
TARGET_KERNEL_CONFIG := \
    gki_defconfig \
    vendor/waipio_GKI.config \
    vendor/xiaomi_GKI.config \
    vendor/mondrian_GKI.config \
    vendor/debugfs.config
BOARD_KERNEL_IMAGE_NAME := Image
TARGET_KERNEL_ADDITIONAL_FLAGS := TARGET_PRODUCT=mondrian
# Qualcomm Kbuild external modules must come from the same matched BSP.
TARGET_KERNEL_EXT_MODULE_ROOT := kernel/xiaomi/sm8450-modules

# Real Qualcomm/Xiaomi board reference; header v4 is the Android product
# mkbootimg output, distinct from the historical Qualcomm stand-alone
# build.config.msm.waipio value of BOOT_IMAGE_HEADER_VERSION=3.
BOARD_BOOT_HEADER_VERSION := 4
BOARD_MKBOOTIMG_ARGS := --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_KERNEL_BASE := 0x00000000
BOARD_KERNEL_PAGESIZE := 4096
BOARD_FLASH_BLOCK_SIZE := 0x020000
BOARD_RAMDISK_USE_LZ4 := true
BOARD_USES_GENERIC_KERNEL_IMAGE := true
BOARD_INCLUDE_DTB_IN_BOOTIMG := true

# Kernel DTBO output must be built from actual mondrian overlays: cape base,
# mondrian PM8008, M11A display, and camera. Never package generic DTBOs.
TARGET_NEEDS_DTBOIMAGE := true
# Do NOT copy BOARD_USES_QCOM_MERGE_DTBS_SCRIPT from the reference ROM:
# it relies on an unimported ROM-specific kernel helper. The independent
# AOSP17 product must integrate actual DTB/DTBO compilation explicitly.

# Vendor boot is a SEPARATE v4 output, hosting the vendor ramdisk.
# Actual module lists/fragments, fstab copying and DTB selection must be
# supplied by the qualified vendor/kernel integration (not guessed here).
BOARD_VENDOR_RAMDISK_FRAGMENTS := dlkm
BOARD_VENDOR_RAMDISK_FRAGMENT.dlkm.KERNEL_MODULE_DIRS := top
# Stock-derived mondrian board has a distinct recovery partition and a
# recovery ramdisk instead of a second independently compiled kernel image.
BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true

# Device-specific partition reference values, subject to hardware validation.
BOARD_BOOTIMAGE_PARTITION_SIZE := 0x0C000000
BOARD_DTBOIMG_PARTITION_SIZE := 0x01800000
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 0x06400000
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 0x06000000
BOARD_SUPER_PARTITION_SIZE := 9126805504
BOARD_SUPER_PARTITION_GROUPS := qti_dynamic_partitions
BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST := odm product system system_ext vendor vendor_dlkm
BOARD_QTI_DYNAMIC_PARTITIONS_SIZE := 9122611200

# The reference A/B update set contains these images (not a standalone Image).
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

# Match independently authored fstab candidates only once validated on
# a physical mondrian with vendor firmware and complete KeyMint/FBE stack.
TARGET_RECOVERY_FSTAB := $(COMMON_DEVICE_PATH)/rootdir/etc/recovery.fstab
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

# Deliberately do not hard-code public test keys or disable verification.
# Production key paths, vbmeta descriptors, signing algorithms and rollback
# indexes must be configured in a separate audited security-owned file.
