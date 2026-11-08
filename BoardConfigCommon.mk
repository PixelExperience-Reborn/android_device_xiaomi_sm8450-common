# PixelExperience-Reborn AOSP 17 shared board foundation for mondrian.
# Qualcomm SM8475 in the Snapdragon 8+ Gen 1 / taro BSP family.
#
# These architecture parameters do NOT establish a bootable device.
# Boot images, partitions, kernel configuration and AVB require verification.

COMMON_DEVICE_PATH := device/xiaomi/sm8450-common

TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := generic

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := generic

TARGET_BOARD_PLATFORM := taro

# Hardware bootloader is supplied by Xiaomi, not built by PE-Reborn.
# Boot/vendor_boot header format and AVB remain separate release gates.
TARGET_BOOTLOADER_BOARD_NAME := taro
TARGET_NO_BOOTLOADER := true

# Deliberately deferred until a verified kernel/vendor/boot-chain BOM exists:
# TARGET_KERNEL_SOURCE, TARGET_KERNEL_CONFIG, boot image layout, DTBO,
# module lists, super partition layout, fstab, SELinux, VINTF and AVB.

# Stable logical partition output paths for the own PE-Reborn product.
# Declaring copy-out mount roots does not choose filesystem type, super
# sizing, AB/AVB flags, fstab contents or recovery boot semantics.
TARGET_COPY_OUT_ODM := odm
TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_SYSTEM_EXT := system_ext
TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm

# The OEM-derived mondrian fstab has a dedicated /metadata mount.
# Actual encryption/wrapped-key configuration remains unselected.
BOARD_USES_METADATA_PARTITION := true



# Native mondrian filesystem policy -- always active, independent of
# the still-unqualified kernel/AVB image packaging stage.
# All six logical dynamic partitions are read-only EROFS.
# /data remains F2FS; /metadata remains ext4 (mount configuration must
# be validated separately against KeyMint and the actual device).
# Stock-derived choice; do not silently revert to ext4 on logical partitions.
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

# Explicit opt-in to the reviewed Android image packaging configuration.
# Ordinary source audit and device-tree builds never activate this until the
# kernel, vendor HAL/firmware, first-stage ramdisk, FBE and AVB are qualified.
ifeq ($(PE_MONDRIAN_BOOT_STAGE),qualified)
include $(COMMON_DEVICE_PATH)/BoardConfigBootImages.mk
else ifneq ($(strip $(PE_MONDRIAN_BOOT_STAGE)),)
$(error Unsupported PE_MONDRIAN_BOOT_STAGE; only 'qualified' is allowed)
endif
