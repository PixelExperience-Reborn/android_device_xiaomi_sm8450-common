#!/usr/bin/env -S PYTHONPATH=../../../tools/extract-utils python3
#
# SPDX-FileCopyrightText: PixelExperience-Reborn
# SPDX-License-Identifier: Apache-2.0
#
# Build rules for the proprietary files of sm8450-common. The files are
# not redistributed: tools/extract_proprietary.py reproduces them from the
# official OTA (hash-checked) into vendor/xiaomi/sm8450-common/proprietary;
# this script (via setup-makefiles.py) writes the Android.bp and makefiles
# that install them.

from extract_utils.fixups_lib import (
    lib_fixups,
    lib_fixups_user_type,
    libs_proto_3_9_1,
)
from extract_utils.main import (
    ExtractUtils,
    ExtractUtilsModule,
)

namespace_imports = [
    'device/xiaomi/sm8450-common',
]

# The blobs link libchrome and libkeymaster_messages as the AOSP 17 vendor
# variants (vendor_available), like the other AOSP libraries: a stock copy at
# the same vendor path is a duplicate install. What the stock KeyMint uses of
# libkeymaster_messages has the same layout in Android 12 and 17
# (tests/test_proprietary_files.py, SOURCE_BUILT).
lib_fixups: lib_fixups_user_type = {
    # The stock libprotobuf-cpp-{lite,full}-3.9.1 ship in the lists, so the
    # blobs link them as they are instead of a -vendorcompat module.
    **{k: v for k, v in lib_fixups.items() if k != libs_proto_3_9_1},
}

module = ExtractUtilsModule(
    'sm8450-common',
    'xiaomi',
    lib_fixups=lib_fixups,
    namespace_imports=namespace_imports,
)

if __name__ == '__main__':
    utils = ExtractUtils.device(module)
    utils.run()
