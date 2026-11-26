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
)
from extract_utils.main import (
    ExtractUtils,
    ExtractUtilsModule,
)

namespace_imports = [
    'device/xiaomi/sm8450-common',
]

lib_fixups: lib_fixups_user_type = {
    **lib_fixups,
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
