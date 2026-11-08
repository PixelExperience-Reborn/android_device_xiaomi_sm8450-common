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
