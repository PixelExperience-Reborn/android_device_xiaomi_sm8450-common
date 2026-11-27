// SPDX-FileCopyrightText: PixelExperience-Reborn
// SPDX-License-Identifier: Apache-2.0
//
// libbase symbols of Android 12 that stock vendor blobs import and that the
// Android 17 libbase exports with another signature. The blobs get this
// library as an extra DT_NEEDED (tools/blob_fixups.py).

#include <string>
#include <string_view>

#include <android-base/file.h>

namespace android::base {

// Android 17 has std::string Basename(std::string_view) only.
// Imported by libboot_control_qti.
std::string Basename(const std::string& path);

std::string Basename(const std::string& path) {
    return Basename(std::string_view(path));
}

}  // namespace android::base
