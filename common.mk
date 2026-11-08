# PixelExperience-Reborn AOSP 17 shared device product foundation.
LOCAL_PATH := $(call my-dir)

# Intentionally no HAL packages or vendor inheritance here yet.
# Each module must have a verified source, partition owner, VINTF contract,
# proprietary ABI and Android 17 Soong definition before inclusion.
