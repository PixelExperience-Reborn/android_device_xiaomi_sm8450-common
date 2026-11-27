// SPDX-FileCopyrightText: PixelExperience-Reborn
// SPDX-License-Identifier: Apache-2.0
//
// libprocessgroup symbols of Android 12 that stock vendor blobs import and
// that the Android 17 libprocessgroup exports with another linkage. The
// blobs get this library as an extra DT_NEEDED (tools/blob_fixups.py).

#include <sys/types.h>

#include <string>
#include <vector>

#include <processgroup/processgroup.h>

// Before Android 14, processgroup.h declared SetTaskProfiles inside
// __BEGIN_DECLS, so it was exported unmangled; Android 17 has C++
// overloads. Imported by libcamxcommonutils and com.qti.chi.override.
bool SetTaskProfilesWithCLinkage(pid_t tid, const std::vector<std::string>& profiles,
                                 bool use_fd_cache) __asm__("SetTaskProfiles");

bool SetTaskProfilesWithCLinkage(pid_t tid, const std::vector<std::string>& profiles,
                                 bool use_fd_cache) {
    return SetTaskProfiles(tid, profiles, use_fd_cache);
}
