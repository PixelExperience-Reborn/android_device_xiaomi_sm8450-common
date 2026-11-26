#
# SPDX-FileCopyrightText: PixelExperience-Reborn
# SPDX-License-Identifier: Apache-2.0
#

ifeq ($(TARGET_BOARD_PLATFORM),taro)
ifneq ($(filter mondrian,$(TARGET_DEVICE)),)

# Mount points of the firmware partitions in fstab.qcom (modem, dsp and
# bluetooth), empty directories of the vendor image as in the stock
# OS3.0.8.0 vendor. Installed files are what Android 17 copies into the
# image, so the directories are installed targets.
SM8450_VENDOR_MOUNT_POINTS := $(addprefix $(TARGET_OUT_VENDOR)/,bt_firmware dsp firmware_mnt)
$(SM8450_VENDOR_MOUNT_POINTS):
	@mkdir -p $@
ALL_DEFAULT_INSTALLED_MODULES += $(SM8450_VENDOR_MOUNT_POINTS)

endif
endif
