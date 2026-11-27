"""VINTF of sm8450-common against Android 17 (FCM target level 7).

vintf/manifest.xml declares the HALs of the stock OS3.0.8.0 services this
build ships, with the instance names of the stock manifests. Android 17
(libvintf checkUnusedHals) requires every instance of the device manifest to
match a framework matrix: the android.* ones must be accepted by the AOSP
level 7 matrix, the vendor.* ones by vintf/framework_compatibility_matrix.xml.
Every declared HAL must have its server (and the passthrough implementation
it loads) in the proprietary lists.
"""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sibling(*names):
    """A sibling tree: next to this one (device/xiaomi/* in the source tree,
    android_device_xiaomi_* side by side) or in .ci/ (checked out by CI)."""
    for base in (ROOT.parent, ROOT / ".ci"):
        for name in names:
            if (base / name).is_dir():
                return base / name
    return None


DEVICE = sibling("mondrian", "android_device_xiaomi_mondrian")

# compatibility_matrix.7.xml of Android 17 (hardware/interfaces,
# android-17.0.0_r1) for the AOSP packages declared here:
# (format, package, interface) -> (version ranges, instances; "~" = regex).
LEVEL7 = [
    ("hidl", "android.hardware.bluetooth", "IBluetoothHci", ["1.0-1"], ["default"]),
    ("hidl", "android.hardware.boot", "IBootControl", ["1.2"], ["default"]),
    ("hidl", "android.hardware.drm", "ICryptoFactory", ["1.3-4"], ["~.*"]),
    ("hidl", "android.hardware.drm", "IDrmFactory", ["1.3-4"], ["~.*"]),
    ("hidl", "android.hardware.gatekeeper", "IGatekeeper", ["1.0"], ["default"]),
    ("hidl", "android.hardware.gnss", "IGnss", ["2.0-1"], ["default"]),
    ("aidl", "android.hardware.gnss", "IGnss", ["2"], ["default"]),
    ("hidl", "android.hardware.graphics.allocator", "IAllocator", ["2.0", "3.0", "4.0"], ["default"]),
    ("hidl", "android.hardware.graphics.composer", "IComposer", ["2.1-4"], ["default"]),
    ("hidl", "android.hardware.graphics.mapper", "IMapper", ["2.1", "3.0", "4.0"], ["default"]),
    ("aidl", "android.hardware.identity", "IIdentityCredentialStore", ["1-4"], ["default"]),
    ("aidl", "android.hardware.light", "ILights", ["1-2"], ["default"]),
    ("hidl", "android.hardware.media.c2", "IComponentStore", ["1.0-2"],
     ["software", "~default[0-9]*", "~vendor[0-9]*_software"]),
    ("aidl", "android.hardware.memtrack", "IMemtrack", ["1"], ["default"]),
    ("hidl", "android.hardware.radio", "ISap", ["1.2"], ["slot1", "slot2"]),
    ("hidl", "android.hardware.radio", "IRadio", ["1.6"], ["slot1", "slot2", "slot3"]),
    ("hidl", "android.hardware.radio.config", "IRadioConfig", ["1.1"], ["default"]),
    ("hidl", "android.hardware.radio.config", "IRadioConfig", ["1.3"], ["default"]),
    ("hidl", "android.hardware.secure_element", "ISecureElement", ["1.0-2"],
     ["~eSE[1-9][0-9]*", "~SIM[1-9][0-9]*"]),
    ("aidl", "android.hardware.security.keymint", "IKeyMintDevice", ["1-2"], ["default", "strongbox"]),
    ("aidl", "android.hardware.security.secureclock", "ISecureClock", ["1"], ["default"]),
    ("aidl", "android.hardware.security.sharedsecret", "ISharedSecret", ["1"], ["default", "strongbox"]),
    ("hidl", "android.hardware.sensors", "ISensors", ["1.0", "2.0-1"], ["default"]),
    ("hidl", "android.hardware.tetheroffload.config", "IOffloadConfig", ["1.0"], ["default"]),
    ("hidl", "android.hardware.tetheroffload.control", "IOffloadControl", ["1.1"], ["default"]),
    ("hidl", "android.hardware.thermal", "IThermal", ["2.0"], ["default"]),
    ("hidl", "android.hardware.usb", "IUsb", ["1.0-3"], ["default"]),
    ("hidl", "android.hardware.wifi", "IWifi", ["1.3-6"], ["default"]),
    ("hidl", "android.hardware.camera.provider", "ICameraProvider", ["2.4-7"], ["~[^/]+/[0-9]+"]),
    ("hidl", "android.hardware.audio", "IDevicesFactory", ["6.0", "7.0-1"], ["default"]),
    ("hidl", "android.hardware.audio.effect", "IEffectsFactory", ["6.0", "7.0"], ["default"]),
    ("hidl", "android.hardware.soundtrigger", "ISoundTriggerHw", ["2.3"], ["default"]),
]
# HIDL parents the device may serve next to a child the matrix accepts
# (libvintf checks the children of a manifest instance).
CHILDREN = {
    ("android.hardware.gnss", (1, 1), "IGnss"): [(2, 0), (2, 1)],
    ("android.hardware.thermal", (1, 0), "IThermal"): [(2, 0)],
}

QCRIL = ["vendor/bin/hw/qcrilNrd", "vendor/lib64/libqcrilNr.so"]
COMPOSER = ["vendor/bin/hw/vendor.qti.hardware.display.composer-service"]
ALLOCATOR = ["vendor/bin/hw/vendor.qti.hardware.display.allocator-service"]
MAPPER = ["vendor/lib/hw/android.hardware.graphics.mapper@4.0-impl-qti-display.so",
          "vendor/lib64/hw/android.hardware.graphics.mapper@4.0-impl-qti-display.so"]
BT = ["vendor/bin/hw/android.hardware.bluetooth@1.0-service-qti"]
KEYMINT = ["vendor/bin/hw/android.hardware.security.keymint-service-qti"]
# Declared package -> files of its server in the proprietary lists.
SERVERS = {
    "android.hardware.bluetooth": BT + ["vendor/lib64/hw/android.hardware.bluetooth@1.0-impl-qti.so"],
    "vendor.qti.hardware.btconfigstore": BT + ["vendor/lib64/hw/vendor.qti.hardware.btconfigstore@2.0-impl.so"],
    "android.hardware.drm": ["vendor/bin/hw/android.hardware.drm@1.4-service.widevine"],
    "android.hardware.gatekeeper": ["vendor/bin/hw/android.hardware.gatekeeper@1.0-service-qti",
                                    "vendor/lib64/hw/android.hardware.gatekeeper@1.0-impl-qti.so"],
    "android.hardware.gnss": ["vendor/bin/hw/android.hardware.gnss-aidl-service-qti",
                              "vendor/lib64/hw/android.hardware.gnss@2.1-impl-qti.so"],
    "android.hardware.graphics.allocator": ALLOCATOR,
    "vendor.qti.hardware.display.allocator": ALLOCATOR,
    "android.hardware.graphics.composer": COMPOSER,
    "vendor.qti.hardware.display.composer": COMPOSER,
    "vendor.qti.hardware.display.config": COMPOSER,
    "vendor.display.config": COMPOSER + ["vendor/lib64/libdisplayconfig.qti.so"],
    "android.hardware.graphics.mapper": MAPPER,
    "vendor.qti.hardware.display.mapper": MAPPER,
    "vendor.display.color": ["vendor/bin/hw/vendor.display.color@1.0-service"],
    "vendor.display.postproc": ["vendor/bin/hw/vendor.display.color@1.0-service"],
    "android.hardware.identity": ["vendor/bin/hw/android.hardware.identity-service-qti"],
    "android.hardware.light": ["vendor/bin/hw/vendor.qti.hardware.lights.service"],
    "android.hardware.media.c2": ["vendor/bin/hw/vendor.qti.media.c2@1.0-service"],
    "android.hardware.memtrack": ["vendor/bin/hw/vendor.qti.hardware.memtrack-service"],
    "android.hardware.radio": QCRIL,
    "android.hardware.radio.config": QCRIL,
    "vendor.qti.hardware.radio.am": QCRIL,
    "vendor.qti.hardware.radio.ims": QCRIL,
    "vendor.qti.hardware.radio.lpa": QCRIL,
    "vendor.qti.hardware.radio.qcrilhook": QCRIL,
    "vendor.qti.hardware.radio.qtiradio": QCRIL,
    "vendor.qti.hardware.radio.uim": QCRIL,
    "vendor.qti.hardware.radio.uim_remote_client": QCRIL,
    "vendor.qti.hardware.radio.uim_remote_server": QCRIL,
    "android.hardware.secure_element": QCRIL + ["vendor/bin/hw/vendor.qti.secure_element@1.2-service"],
    "vendor.qti.esepowermanager": ["vendor/bin/hw/vendor.qti.esepowermanager@1.1-service",
                                   "vendor/lib64/hw/vendor.qti.esepowermanager@1.1-impl.so"],
    "android.hardware.security.keymint": KEYMINT,
    "android.hardware.security.secureclock": KEYMINT,
    "android.hardware.security.sharedsecret": KEYMINT,
    "android.hardware.tetheroffload.config": ["vendor/bin/ipacm"],
    "android.hardware.tetheroffload.control": ["vendor/bin/ipacm"],
    "android.hardware.thermal": ["vendor/bin/hw/android.hardware.thermal@2.0-service.qti-v2"],
    "vendor.qti.hardware.limits": ["vendor/bin/hw/vendor.qti.hardware.limits@1.1-service"],
    "android.hardware.usb": ["vendor/bin/hw/android.hardware.usb@1.2-service-qti"],
    "android.hardware.wifi": ["vendor/bin/hw/android.hardware.wifi@1.0-service"],
    "vendor.qti.hardware.AGMIPC": ["vendor/bin/hw/vendor.qti.hardware.AGMIPC@1.0-service"],
    "vendor.qti.hardware.capabilityconfigstore": [
        "vendor/bin/hw/vendor.qti.hardware.capabilityconfigstore@1.0-service",
        "vendor/lib64/hw/vendor.qti.hardware.capabilityconfigstore@1.0-impl.so"],
    "vendor.qti.hardware.servicetracker": [
        "vendor/bin/hw/vendor.qti.hardware.servicetracker@1.2-service",
        "vendor/lib64/hw/vendor.qti.hardware.servicetracker@1.2-impl.so"],
    "vendor.qti.hardware.dsp": ["vendor/bin/dspservice"],
    "vendor.qti.hardware.perf": ["vendor/bin/hw/vendor.qti.hardware.perf-hal-service"],
    "vendor.qti.hardware.qseecom": ["vendor/bin/hw/vendor.qti.hardware.qseecom@1.0-service"],
    "vendor.qti.hardware.qteeconnector": ["vendor/bin/hw/vendor.qti.hardware.qteeconnector@1.0-service"],
    "vendor.qti.ims.factory": ["vendor/bin/imsdaemon"],
    "vendor.qti.imsrtpservice": ["vendor/bin/ims_rtp_daemon"],
    "vendor.qti.ims.callinfo": ["vendor/bin/imsdaemon", "vendor/lib64/lib-imsservice.so"],
    "com.qualcomm.qti.imscmservice": ["vendor/bin/imsdaemon", "vendor/lib64/lib-imsrcsservice.so"],
    "com.qualcomm.qti.uceservice": ["vendor/bin/imsdaemon", "vendor/lib64/lib-imsrcsservice.so"],
    "vendor.qti.hardware.data.connection": QCRIL + ["vendor/lib64/libqcrilDataModule.so"],
    "vendor.qti.hardware.data.iwlan": QCRIL + ["vendor/lib64/libqcrilDataModule.so"],
    "vendor.qti.hardware.data.connectionfactory": QCRIL + ["vendor/lib64/libqcrildataaidl.so"],
    "vendor.qti.hardware.radio.internal.deviceinfo": QCRIL + ["vendor/lib64/deviceInfoServiceModuleNr.so"],
    # Served by the AOSP audio service (BUILT) with the stock modules.
    "android.hardware.audio": ["vendor/lib64/hw/audio.primary.taro.so"],
    "android.hardware.audio.effect": ["vendor/lib64/soundfx/libqcompostprocbundle.so"],
    "android.hardware.soundtrigger": ["vendor/lib64/hw/sound_trigger.primary.taro.so"],
}
# Declared HALs whose service is built from AOSP 17 (PRODUCT_PACKAGES of common.mk).
BUILT = {
    "android.hardware.audio": ["android.hardware.audio.service", "android.hardware.audio@7.0-impl"],
    "android.hardware.audio.effect": ["android.hardware.audio.effect@7.0-impl"],
    "android.hardware.soundtrigger": ["android.hardware.soundtrigger@2.3-impl"],
}
# Stock HALs Android 17 does not accept at level 7, or that come from source
# with their own VINTF fragments, or that this build does not ship.
NOT_DECLARED = [
    ("hidl", r"android\.hardware\.health"), ("hidl", r"android\.hardware\.bluetooth\.audio"),
    ("hidl", r"android\.hardware\.wifi\.(supplicant|hostapd)"), ("hidl", r"android\.hardware\.ir"),
    ("hidl", r"android\.hardware\.nfc"), ("aidl", r"android\.hardware\.gnss"),
    # AOSP 17 boot control and sensors multihal services, declared by their
    # own VINTF fragments.
    ("hidl", r"android\.hardware\.(boot|sensors)"),
    ("aidl", r"android\.hardware\.power"), ("aidl", r"android\.hardware\.vibrator"),
    ("hidl", r"android\.hardware\.(dumpstate|media\.omx|atrace|keymaster)"),
    ("hidl", r"android\.hardware\.biometrics\.fingerprint"),
    (None, r"vendor\.(xiaomi|dolby|nxp)\..*"), (None, r"com\.(fingerprints|dsi)\..*"),
    (None, r"vendor\.qti\.hardware\.(eid|qccvndhal|wifidisplaysession|fm|bluetooth_sar|soter|tui_comm|vpp|qxr)"),
]


def listed():
    paths = set()
    for lst in (ROOT / "proprietary-files.txt", DEVICE and DEVICE / "proprietary-files.txt"):
        if lst is None:
            continue
        for line in lst.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                paths.add(line.split("|")[0].split(";")[0].lstrip("-"))
    return paths


def version_range(text, fmt):
    if fmt == "aidl":
        low, _, high = text.partition("-")
        return 1, int(low), int(high or low)
    major, _, minor = text.partition(".")
    low, _, high = minor.partition("-")
    return int(major), int(low), int(high or low)


def manifest_instances(path):
    """(format, package, (major, minor), interface, instance) of a manifest."""
    root = ET.parse(path).getroot()
    out = []
    for hal in root.findall("hal"):
        fmt, name = hal.get("format", "hidl"), hal.findtext("name")
        aidl_version = int(hal.findtext("version") or 1)
        for fq in hal.findall("fqname"):
            if fmt == "hidl":
                m = re.fullmatch(r"@(\d+)\.(\d+)::(\w+)/(.+)", fq.text)
                out.append((fmt, name, (int(m[1]), int(m[2])), m[3], m[4]))
            else:
                m = re.fullmatch(r"(\w+)/(.+)", fq.text)
                out.append((fmt, name, (1, aidl_version), m[1], m[2]))
    return root, out


def matrix_entries(path):
    root = ET.parse(path).getroot()
    out = []
    for hal in root.findall("hal"):
        fmt, name = hal.get("format", "hidl"), hal.findtext("name")
        versions = [v.text for v in hal.findall("version")] or (["1"] if fmt == "aidl" else [])
        for intf in hal.findall("interface"):
            instances = [i.text for i in intf.findall("instance")]
            instances += ["~" + i.text for i in intf.findall("regex-instance")]
            out.append((fmt, name, intf.findtext("name"), versions, instances))
    return root, out


def accepts(entries, fmt, name, version, interface, instance):
    for efmt, ename, eintf, versions, instances in entries:
        if (efmt, ename, eintf) != (fmt, name, interface):
            continue
        if not any(version[0] == major and low <= version[1] <= high
                   for major, low, high in (version_range(v, fmt) for v in versions)):
            continue
        if any(re.fullmatch(i[1:], instance) if i.startswith("~") else i == instance
               for i in instances):
            return True
    return False


class VintfTest(unittest.TestCase):
    MANIFEST = ROOT / "vintf/manifest.xml"
    FCM = ROOT / "vintf/framework_compatibility_matrix.xml"

    def setUp(self):
        self.root, self.instances = manifest_instances(self.MANIFEST)
        _, self.fcm = matrix_entries(self.FCM)
        self.listed = listed()

    def test_target_level_7(self):
        self.assertEqual(self.root.get("type"), "device")
        self.assertEqual(self.root.get("target-level"), "7")

    def test_hals_are_fqname_only_with_transport(self):
        for hal in self.root.findall("hal"):
            name = hal.findtext("name")
            self.assertFalse(hal.findall("interface"), name)
            self.assertTrue(hal.findall("fqname"), name)
            if hal.get("format", "hidl") == "hidl":
                self.assertFalse(hal.findall("version"), name)
                self.assertIn(hal.findtext("transport"), ("hwbinder", "passthrough"), name)
            else:
                self.assertIsNone(hal.find("transport"), name)
                self.assertEqual(len(hal.findall("version")), 1, name)

    def test_no_duplicate_instances(self):
        self.assertEqual(len(self.instances), len(set(self.instances)))

    def test_every_instance_is_in_a_framework_matrix(self):
        for fmt, name, version, interface, instance in self.instances:
            with self.subTest(name=name, version=version, instance=instance):
                if not name.startswith("android."):
                    self.assertTrue(accepts(self.fcm, fmt, name, version, interface, instance))
                    continue
                ok = accepts(LEVEL7, fmt, name, version, interface, instance)
                for child in CHILDREN.get((name, version, interface), []):
                    ok = ok or accepts(LEVEL7, fmt, name, child, interface, instance)
                self.assertTrue(ok)

    def test_framework_matrix_extension_matches_the_manifest(self):
        declared = {(f, n, i, x) for f, n, _, i, x in self.instances if not n.startswith("android.")}
        in_fcm = {(f, n, i, x) for f, n, i, _, xs in self.fcm for x in xs}
        self.assertEqual(declared, in_fcm)
        for fmt, name, interface, versions, instances in self.fcm:
            self.assertFalse(name.startswith("android."), name)
            for v in versions:
                ver = version_range(v, fmt)
                self.assertEqual(ver[1], ver[2], (name, v))
                self.assertIn((fmt, name, (ver[0], ver[1])),
                              {(f, n, vv) for f, n, vv, _, _ in self.instances})

    def test_every_declared_hal_has_its_server_listed(self):
        if DEVICE is None:
            self.skipTest("needs the mondrian tree next to this one or in .ci/")
        for name in sorted({n for _, n, _, _, _ in self.instances}):
            with self.subTest(name=name):
                self.assertIn(name, SERVERS)
                for path in SERVERS[name]:
                    self.assertIn(path, self.listed)

    def test_aosp_built_servers_are_in_the_product(self):
        common = (ROOT / "common.mk").read_text()
        for name in {n for _, n, _, _, _ in self.instances} & set(BUILT):
            for module in BUILT[name]:
                self.assertRegex(common, rf"(?m)^\s+{re.escape(module)}( \\)?$", (name, module))

    def test_health_is_the_aosp_aidl_hal(self):
        # Stock health is HIDL 2.1, which level 7 does not accept.
        common = (ROOT / "common.mk").read_text()
        for module in ("android.hardware.health-service.example",
                       "android.hardware.health-service.example_recovery"):
            self.assertRegex(common, rf"(?m)^\s+{re.escape(module)}( \\)?$")

    def test_boot_and_sensors_services_from_source_load_the_stock_parts(self):
        common = (ROOT / "common.mk").read_text()
        for module in ("android.hardware.boot@1.2-service", "android.hardware.sensors@2.1-service.multihal"):
            self.assertRegex(common, rf"(?m)^\s+{re.escape(module)}( \\)?$")
        for path in ("vendor/lib64/hw/android.hardware.boot@1.0-impl-1.2-qti.so", "vendor/lib64/sensors.ssc.so",
                     "vendor/etc/sensors/hals.conf"):
            self.assertIn(path, self.listed)
        rc = (ROOT / "rootdir/etc/init/android.hardware.sensors@2.1-service-multihal_sm8450.rc").read_text()
        self.assertIn("    override\n", rc)
        self.assertIn("socket audio_us_socket_1 seqpacket", rc)

    def test_left_out_stays_out(self):
        for fmt, name, _, _, _ in self.instances:
            for nfmt, pattern in NOT_DECLARED:
                if nfmt in (None, fmt):
                    self.assertIsNone(re.fullmatch(pattern, name), (fmt, name))

    def test_device_matrix_has_no_vendor_ndk(self):
        root = ET.parse(ROOT / "vintf/compatibility_matrix.xml").getroot()
        self.assertEqual(root.get("type"), "device")
        self.assertIsNone(root.find("vendor-ndk"))
        self.assertTrue(all(h.findtext("name").startswith(("android.hidl.", "android.frameworks."))
                            for h in root.findall("hal")))

    def test_board_wiring(self):
        board = (ROOT / "BoardConfigCommon.mk").read_text()
        for line in ("DEVICE_MANIFEST_FILE += $(COMMON_PATH)/vintf/manifest.xml",
                     "DEVICE_MATRIX_FILE := $(COMMON_PATH)/vintf/compatibility_matrix.xml",
                     "DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += "
                     "$(COMMON_PATH)/vintf/framework_compatibility_matrix.xml"):
            self.assertIn(line, board)

    def test_kernel_is_kept_and_uffd_gc_is_explicit(self):
        common = (ROOT / "common.mk").read_text()
        code = "\n".join(l for l in common.splitlines() if not l.lstrip().startswith("#"))
        self.assertIn("PRODUCT_ENABLE_UFFD_GC := true", code)
        self.assertNotIn("PRODUCT_OTA_ENFORCE_VINTF_KERNEL_REQUIREMENTS", code)


if __name__ == "__main__":
    unittest.main()
