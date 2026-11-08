# PixelExperience-Reborn AOSP 17 shared device product foundation.
LOCAL_PATH := $(call my-dir)

# Intentionally no HAL packages or vendor inheritance here yet.
# Each module must have a verified source, partition owner, VINTF contract,
# proprietary ABI and Android 17 Soong definition before inclusion.


# AOSP-owned storage, generic ramdisk and virtual A/B with vendor_boot.
# These are platform make fragments, not LineageOS product inheritance.
$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_ramdisk.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/launch_with_vendor_ramdisk.mk)

# Xiaomi mondrian uses dynamic partitions and A/B. The board-level EROFS
# selections live in BoardConfigCommon.mk, not in a disabled boot-only fragment.
PRODUCT_USE_DYNAMIC_PARTITIONS := true

# Native Android OTA/fastboot infrastructure. Vendor HAL integration follows
# separately after matching binary firmware and AVB verification.
PRODUCT_PACKAGES += \
    fastbootd \
    update_engine \
    update_engine_sideload \
    update_verifier \
    otapreopt_script

# OTA post-install must understand the actual filesystem used by the product.
AB_OTA_POSTINSTALL_CONFIG += \
    RUN_POSTINSTALL_system=true \
    POSTINSTALL_PATH_system=system/bin/otapreopt_script \
    FILESYSTEM_TYPE_system=erofs \
    POSTINSTALL_OPTIONAL_system=true

# Vendor checkpoint_gc and vendor-side OTA post-install are intentionally
# deferred until the matching AOSP17 vold/vendor implementation is available.
# No legacy vendor/lineage, FM radio, unofficial HAL or test signing keys.
