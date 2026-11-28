# SPDX-License-Identifier: Apache-2.0
#
# PixelExperience-Reborn Android 17: product configuration shared by the
# Xiaomi SM8450/SM8475 (taro) devices of this project (mondrian).
#
# Every component has a verified source (stock OS3.0.8.0 file with its
# SHA-256, AOSP 17 or an organization fork), a partition owner and a VINTF
# entry that the Android 17 level 7 matrix accepts (docs/A17_HAL_MATRIX.md).

# Soong namespace of this tree (imported by the vendor build rules).
PRODUCT_SOONG_NAMESPACES += \
    device/xiaomi/sm8450-common

# Proprietary files of the stock OS3.0.8.0 firmware (reproduced from the
# official OTA by tools/extract_proprietary.py; rules by setup-makefiles.py).
$(call inherit-product, vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk)

# The vendor partition carries the stock Android 12 vendor files (vendor API
# level 31): a frozen (GRF) vendor, as the stock ro.board.first_api_level=31.
# BOARD_API_LEVEL itself is set by the Android 17 build system only.
BOARD_SHIPPING_API_LEVEL := 31

# Hardware features of the platform: the Android 17 definitions of
# frameworks/native, the set the stock OS3.0.8.0 vendor declares. NFC, IR and
# fingerprint are declared by the device together with their HALs.
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/handheld_core_hardware.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/handheld_core_hardware.xml \
    frameworks/native/data/etc/android.hardware.audio.low_latency.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.audio.low_latency.xml \
    frameworks/native/data/etc/android.hardware.bluetooth.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.bluetooth.xml \
    frameworks/native/data/etc/android.hardware.bluetooth_le.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.bluetooth_le.xml \
    frameworks/native/data/etc/android.hardware.keystore.app_attest_key.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.keystore.app_attest_key.xml \
    frameworks/native/data/etc/android.hardware.location.gps.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.location.gps.xml \
    frameworks/native/data/etc/android.hardware.opengles.aep.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.opengles.aep.xml \
    frameworks/native/data/etc/android.hardware.se.omapi.uicc.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.se.omapi.uicc.xml \
    frameworks/native/data/etc/android.hardware.telephony.cdma.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.cdma.xml \
    frameworks/native/data/etc/android.hardware.telephony.gsm.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.gsm.xml \
    frameworks/native/data/etc/android.hardware.telephony.ims.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.ims.xml \
    frameworks/native/data/etc/android.hardware.touchscreen.multitouch.jazzhand.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.touchscreen.multitouch.jazzhand.xml \
    frameworks/native/data/etc/android.hardware.usb.accessory.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.usb.accessory.xml \
    frameworks/native/data/etc/android.hardware.usb.host.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.usb.host.xml \
    frameworks/native/data/etc/android.hardware.vulkan.compute-0.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.vulkan.compute.xml \
    frameworks/native/data/etc/android.hardware.vulkan.level-1.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.vulkan.level.xml \
    frameworks/native/data/etc/android.hardware.vulkan.version-1_1.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.vulkan.version.xml \
    frameworks/native/data/etc/android.hardware.wifi.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.wifi.xml \
    frameworks/native/data/etc/android.hardware.wifi.direct.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.wifi.direct.xml \
    frameworks/native/data/etc/android.hardware.wifi.passpoint.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.wifi.passpoint.xml \
    frameworks/native/data/etc/android.software.ipsec_tunnels.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.ipsec_tunnels.xml \
    frameworks/native/data/etc/android.software.midi.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.midi.xml \
    frameworks/native/data/etc/android.software.opengles.deqp.level-2021-03-01.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.opengles.deqp.level.xml \
    frameworks/native/data/etc/android.software.sip.voip.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.sip.voip.xml \
    frameworks/native/data/etc/android.software.verified_boot.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.verified_boot.xml \
    frameworks/native/data/etc/android.software.vulkan.deqp.level-2021-03-01.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.vulkan.deqp.level.xml

# ART userfaultfd GC: the kernel is GKI android12-5.10 with
# CONFIG_USERFAULTFD=y and MREMAP_DONTUNMAP, the case the Android 17 build
# names for PRODUCT_ENABLE_UFFD_GC := true. The kernel and its VINTF check
# are mondrian's (the stock GKI 5.10.236, device.mk).
PRODUCT_ENABLE_UFFD_GC := true

# KeyMint version 1, as the stock KeyMint HAL implements (feature version 100).
PRODUCT_PACKAGES += \
    android.hardware.hardware_keystore_V1.xml

# Runtime resource overlays of the SoC (overlay/, vendor): the values of the
# stock OS3.0.8.0 QTI common overlays that Android 17 still defines
# (docs/OVERLAYS.md). The device tree adds its display and model overlays.
PRODUCT_PACKAGES += \
    CarrierConfigResSm8450 \
    FrameworksResSm8450 \
    SettingsResSm8450 \
    SystemUIResSm8450 \
    TelephonyResSm8450 \
    WifiResSm8450

# IMS (VoLTE, video calling, Wi-Fi calling) on the stock Qualcomm stack: the
# ImsService org.codeaurora.ims, QtiTelephony, qcrilmsgtunnel and the RCS
# service are stock system_ext apps (proprietary-files.txt, IMS section) that
# talk to qcrilNrd and imsdaemon. Their shared libraries come from
# vendor/codeaurora/telephony (Qualcomm LA.QSSI.17.0, built for Android 17);
# the Xiaomi apps also need telephony/ (TelephonyBaseUtilsStub on the boot
# classpath, QtiTelephonyCompat). The overlays name the ImsService and the
# IWLAN services for telephony.
PRODUCT_PACKAGES += \
    extphonelib \
    extphonelib-product \
    extphonelib.xml \
    extphonelib_product.xml \
    ims-ext-common \
    ims_ext_common.xml \
    qti-telephony-hidl-wrapper \
    qti-telephony-hidl-wrapper-prd \
    qti_telephony_hidl_wrapper.xml \
    qti_telephony_hidl_wrapper_prd.xml \
    qti-telephony-utils \
    qti-telephony-utils-prd \
    qti_telephony_utils.xml \
    qti_telephony_utils_prd.xml \
    QtiTelephonyCompat \
    xiaomi-telephony-stub

PRODUCT_BOOT_JARS += \
    xiaomi-telephony-stub

# AOSP-owned storage, generic ramdisk and virtual A/B with vendor_boot.
# These are platform make fragments, not LineageOS product inheritance.
$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_ramdisk.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/launch_with_vendor_ramdisk.mk)

# fstab: stock-derived (see the header of rootdir/etc/fstab.qcom and
# tools/validate_fstab.py). Like stock, the same file is the first-stage fstab
# of vendor_boot and vendor/etc/fstab.qcom; recovery uses it too.
PRODUCT_COPY_FILES += \
    device/xiaomi/sm8450-common/rootdir/etc/fstab.qcom:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qcom \
    device/xiaomi/sm8450-common/rootdir/etc/fstab.qcom:$(TARGET_COPY_OUT_VENDOR_RAMDISK)/first_stage_ramdisk/fstab.qcom

# Platform init of the stock OS3.0.8.0 vendor for taro, kept to what this
# build ships (rootdir/etc): init.qcom.rc (ro.hardware=qcom) imports
# init.qcom.usb.rc (USB gadget, no diagnostic functions) and init.target.rc,
# which imports init.qti.kernel.rc.
PRODUCT_COPY_FILES += \
    device/xiaomi/sm8450-common/rootdir/etc/init.qcom.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.qcom.rc \
    device/xiaomi/sm8450-common/rootdir/etc/init.target.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.target.rc \
    device/xiaomi/sm8450-common/rootdir/etc/init.qcom.usb.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.qcom.usb.rc \
    device/xiaomi/sm8450-common/rootdir/etc/charger_fstab.qti:$(TARGET_COPY_OUT_VENDOR)/etc/charger_fw_fstab.qti

# Health: the AOSP 17 health HAL (AIDL, with its own VINTF fragment), reading
# the power supplies of the Qualcomm battery charger driver; it also runs the
# off-mode charger (class charger) and the recovery health service.
PRODUCT_PACKAGES += \
    android.hardware.health-service.example \
    android.hardware.health-service.example_recovery

# Audio: the AOSP 17 audio service (HIDL audio 7.0, effects 7.0, sound
# trigger 2.3) loading the stock audio.primary.taro, sound_trigger.primary.taro
# and effect modules, 64-bit like the stock service; the stock socket of the
# ultrasound proximity sensor (rootdir/etc/init). The audio configuration of
# the SKU comes from the device (sku_cape on mondrian).
$(call soong_config_set,android_hardware_audio,run_64bit,true)
PRODUCT_PACKAGES += \
    android.hardware.audio.service \
    android.hardware.audio@7.0-impl \
    android.hardware.audio.effect@7.0-impl \
    android.hardware.soundtrigger@2.3-impl \
    audio.r_submix.default \
    audio.usb.default \
    default_volume_tables.xml \
    r_submix_audio_policy_configuration.xml \
    libbundlewrapper \
    libdownmix \
    libdynproc \
    libeffectproxy \
    libldnhncr \
    libreverbwrapper \
    libvisualizer
PRODUCT_COPY_FILES += \
    device/xiaomi/sm8450-common/rootdir/etc/init/android.hardware.audio.service_sm8450.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/android.hardware.audio.service_sm8450.rc

# Boot control: the Qualcomm AIDL boot control HAL, built from
# hardware/qcom-caf/bootctrl (LineageOS lineage-24.0-caf): A/B slots in the
# GPT attributes and the UFS boot LUN (ufs-bsg), in Android (update_engine)
# and in recovery (ADB sideload through update_engine_sideload, fastbootd
# set_active). Each service carries its rc and VINTF fragment.
PRODUCT_SOONG_NAMESPACES += \
    hardware/qcom-caf/bootctrl
PRODUCT_PACKAGES += \
    android.hardware.boot-service.qti \
    android.hardware.boot-service.qti.recovery

# Sensors: the stock service is the AOSP default multihal (HalProxy), built
# here with its rc and VINTF fragment; it loads the stock sub-HALs of
# /vendor/etc/sensors/hals.conf. It keeps the stock socket of the
# ultrasound proximity sensor (rootdir/etc/init).
PRODUCT_PACKAGES += \
    android.hardware.sensors@2.1-service.multihal
PRODUCT_COPY_FILES += \
    device/xiaomi/sm8450-common/rootdir/etc/init/android.hardware.sensors@2.1-service-multihal_sm8450.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/android.hardware.sensors@2.1-service-multihal_sm8450.rc

# Symbolic links of the stock vendor: the remote file system (rfs) of the
# DSPs and the modem, and the WLAN configuration the qca_cld3 driver loads
# (rootdir/Android.bp). The firmware mount points come from rootdir/Android.mk.
PRODUCT_PACKAGES += \
    sm8450_vendor_symlinks

# Recovery: the init script and firmware fstab of the stock OS3.0.8.0
# recovery (USB controller in peripheral mode for adb and fastbootd, modem
# firmware partition and ADSP start for the battery status, backlight).
PRODUCT_COPY_FILES += \
    device/xiaomi/sm8450-common/rootdir/etc/init.recovery.qcom.rc:$(TARGET_COPY_OUT_RECOVERY)/root/init.recovery.qcom.rc \
    device/xiaomi/sm8450-common/rootdir/etc/charger_fstab.qti:$(TARGET_COPY_OUT_RECOVERY)/root/vendor/etc/charger_fstab.qti

# fastbootd in recovery: the AOSP fastboot HAL for recovery (stock uses the
# AOSP mock HAL, android.hardware.fastboot@1.1-impl-mock).
PRODUCT_PACKAGES += \
    android.hardware.fastboot-service.example_recovery

# Bring-up log on /metadata, readable in recovery (userdebug and eng only;
# see BoardConfigCommon.mk for the reboot target of fatal init errors).
ifneq ($(TARGET_BUILD_VARIANT),user)
PRODUCT_COPY_FILES += \
    device/xiaomi/sm8450-common/rootdir/etc/init/debug/pe_bootlog.rc:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/init/pe_bootlog.rc
endif

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
