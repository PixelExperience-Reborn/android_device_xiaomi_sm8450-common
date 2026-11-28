# SPDX-License-Identifier: Apache-2.0
"""Runtime resource overlays (overlay/): structure, build wiring and names.

Every resource an overlay sets must exist in its target on Android 17: a name
the target no longer defines is silently ignored at runtime, so the value
would just be lost. The names below were checked against android-17.0.0_r1
(frameworks/base core/res and packages/SystemUI, packages/apps/Settings,
SettingsProvider, packages/modules/Wifi ServiceWifiResources, packages/services/
Telephony); add a name here only after checking it there. CarrierConfig is
overlaid with its res/xml/vendor.xml (DefaultCarrierConfigService). docs/OVERLAYS.md explains the values.
"""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

VERIFIED_A17 = {
    "android": set("""
        config_ambientBrighteningThresholds config_ambientDarkeningThresholds config_ambientThresholdLevels
        config_autoBrightnessBrighteningLightDebounce config_autoBrightnessDarkeningLightDebounce
        config_autoBrightnessLcdBacklightValues config_autoBrightnessLevels config_automatic_brightness_available
        config_carrier_volte_available config_defaultPeakRefreshRate config_defaultRefreshRate
        config_default_cellular_usage_setting config_device_volte_available config_device_vt_available
        config_device_wfc_ims_available config_enable_iwlan_handover_policy config_enhanced_iwlan_handover_check
        config_qualified_networks_service_package config_wlan_data_service_package
        config_wlan_network_service_package
        config_dozeAfterScreenOffByDefault config_dozeAlwaysOnDisplayAvailable config_dozeAlwaysOnEnabled
        config_dozeComponent config_enableBurnInProtection config_hotswapCapable config_mainBuiltInDisplayCutout
        config_network_type_tcp_buffers config_num_physical_slots config_powerDecoupleAutoSuspendModeFromDisplay
        config_screenBrightnessDimFloat config_screenBrightnessDoze config_screenBrightnessSettingDefaultFloat
        config_screenBrightnessSettingMaximumFloat config_screenBrightnessSettingMinimumFloat
        config_setColorTransformAccelerated config_showNavigationBar config_sms_enabled_locking_shift_tables
        config_sms_enabled_single_shift_tables config_stkNoAlphaUsrCnf config_supportAudioSourceUnprocessed
        config_switch_phone_on_voice_reg_state_change config_telephony5gNonStandalone config_telephony5gStandalone
        config_unplugTurnsOnScreen config_voice_data_sms_auto_fallback config_wifiDisplaySupportsProtectedBuffers
        rounded_corner_radius rounded_corner_radius_bottom rounded_corner_radius_top skip_restoring_network_selection
        status_bar_height_default status_bar_height_landscape status_bar_height_portrait
    """.split()),
    "com.android.systemui": {"doze_display_state_supported", "rounded_corner_content_padding"},
    "com.android.phone": {"config_ims_mmtel_package", "config_ims_rcs_package"},
    "com.android.carrierconfig": set(),
    "com.android.settings": {"config_network_scan_helper_max_search_time_sec", "config_show_smooth_display"},
    "com.android.providers.settings": {"def_device_name_simple", "def_screen_brightness_automatic_mode"},
    "com.android.wifi.resources": set("""
        config_wifiAllowMultipleNetworksOnSameAwareNdi config_wifiApplicationCentricQosPolicyFeatureEnabled
        config_wifiCharsetsForSsidTranslation config_wifiDelayDisconnectOnImsLostMs
        config_wifiDisableReasonByWrongPasswordThreshold config_wifiDriverSupportedNl80211RegChangedEvent
        config_wifiEnablePartialInitialScan config_wifiForcedSoftApRestartWhenCountryCodeChanged
        config_wifiHardwareSoftapMaxClientCount config_wifiMaxNumWifiConfigurations
        config_wifiNetworkCentricQosPolicyFeatureEnabled config_wifiSaeH2eSupported config_wifiSaeUpgradeOffloadEnabled
        config_wifiSoftApDynamicCountryCodeUpdateSupported config_wifiSoftap2gChannelList config_wifiSoftap6ghzSupported
        config_wifiSoftapAcsIncludeDfs config_wifiSoftapHeSuBeamformeeSupported config_wifiSoftapHeSuBeamformerSupported
        config_wifiSoftapIeee80211axSupported config_wifiSoftapOweSupported config_wifiSoftapOweTransitionSupported
        config_wifiStaDynamicCountryCodeUpdateSupported config_wifiUseHalApiToDisableFwRoaming
        config_wifi_background_scan_support config_wifi_connected_mac_randomization_supported
        config_wifi_only_link_same_credential_configurations config_wifi_p2p_mac_randomization_supported
        config_wifi_softap_acs_supported config_wifi_softap_ieee80211ac_supported config_wifi_softap_sae_supported
        config_wifi_tcp_buffers wifi_tether_configure_ssid_default
    """.split()),
}
# Stock names Android 17 removed or renamed: they must not come back.
GONE_IN_A17 = {"config_dozeAfterScreenOff", "config_globallyDisabledComponents", "config_wifi5ghzSupport",
               "config_wifi6ghzSupport", "config_ntpServer", "config_bluetooth_le_peripheral_mode_supported",
               "config_lockscreenAntiFalsingClassifierEnabled", "config_gesture_settings_enabled"}
# Not set yet: the color modes (their IDs need the device) and the stock nits
# curve (no nits-to-backlight map), see docs/OVERLAYS.md.
DEFERRED = {"config_availableColorModes", "config_autoBrightnessDisplayValuesNits"}


def overlays(root):
    """name -> (directory, manifest attributes, Android.bp text)."""
    out = {}
    for manifest in sorted((root / "overlay").glob("*/AndroidManifest.xml")):
        tree = ET.parse(manifest).getroot()
        overlay = tree.find("overlay")
        attrs = {k.replace(ANDROID_NS, ""): v for k, v in overlay.attrib.items()}
        attrs["package"] = tree.get("package")
        out[manifest.parent.name] = (manifest.parent, attrs, (manifest.parent / "Android.bp").read_text())
    return out


def resources(directory):
    for f in sorted((directory / "res").glob("values*/*.xml")):
        for element in ET.parse(f).getroot():
            yield f, element


def packages(mk):
    text = mk.read_text()
    return set(re.findall(r"^\s+(\w+)(?: \\)?$", text, re.M))


def check_tree(case, root, partition, mk, min_priority, max_priority):
    found = overlays(root)
    case.assertTrue(found, f"no overlays in {root}")
    listed = packages(mk)
    seen_packages = set()
    for name, (directory, attrs, bp) in found.items():
        with case.subTest(overlay=name):
            case.assertRegex(bp, rf'runtime_resource_overlay \{{\s+name: "{name}",\s+{partition}: true,\s+\}}')
            case.assertIn(name, listed, f"{name} is not in PRODUCT_PACKAGES of {mk.name}")
            case.assertEqual(attrs.get("isStatic"), "true")
            case.assertTrue(min_priority <= int(attrs["priority"]) <= max_priority, attrs["priority"])
            case.assertNotIn(attrs["package"], seen_packages)
            seen_packages.add(attrs["package"])
            target = attrs["targetPackage"]
            case.assertIn(target, VERIFIED_A17)
            if "requiredSystemPropertyName" in attrs:
                case.assertEqual(attrs["requiredSystemPropertyName"], "ro.boot.hwc")
                case.assertIn(attrs["requiredSystemPropertyValue"], {"CN", "GL"})
            names = []
            for f, element in resources(directory):
                n = element.get("name")
                case.assertIn(n, VERIFIED_A17[target], f"{f}: {n} is not checked against Android 17")
                case.assertNotIn(n, GONE_IN_A17 | DEFERRED)
                names.append((f.parent.name, n))
            case.assertEqual(len(names), len(set(names)), "duplicate resource")
    return found


class OverlayTest(unittest.TestCase):
    def test_common_overlays(self):
        found = check_tree(self, ROOT, "vendor", ROOT / "common.mk", 100, 100)
        self.assertEqual(set(found), {"CarrierConfigResSm8450", "FrameworksResSm8450", "SettingsResSm8450",
                                      "SystemUIResSm8450", "TelephonyResSm8450", "WifiResSm8450"})

    def test_ims_services_are_the_shipped_apps(self):
        # The ImsService and IWLAN packages the overlays name are the stock apps in the list.
        listed = (ROOT / "proprietary-files.txt").read_text()
        phone = ET.parse(ROOT / "overlay/TelephonyResSm8450/res/values/config.xml").getroot()
        values = {e.get("name"): e.text for e in phone}
        self.assertEqual(values, {"config_ims_mmtel_package": "org.codeaurora.ims",
                                  "config_ims_rcs_package": "vendor.qti.imsrcs"})
        self.assertIn("system_ext/priv-app/ims/ims.apk", listed)
        self.assertIn("system_ext/app/ImsRcsService/ImsRcsService.apk", listed)
        fw = ET.parse(ROOT / "overlay/FrameworksResSm8450/res/values/config.xml").getroot()
        for key in ("config_wlan_data_service_package", "config_wlan_network_service_package",
                    "config_qualified_networks_service_package"):
            self.assertEqual(fw.find(f"string[@name='{key}']").text, "vendor.qti.iwlan")
        self.assertIn("vendor/app/IWlanService/IWlanService.apk", listed)

    def test_carrier_config_is_a_carrier_config_list(self):
        root = ET.parse(ROOT / "overlay/CarrierConfigResSm8450/res/xml/vendor.xml").getroot()
        self.assertEqual(root.tag, "carrier_config_list")
        self.assertTrue(root.findall("carrier_config"))
        for config in root.findall("carrier_config"):
            for attr in ("mcc", "mnc"):
                if config.get(attr) is not None:
                    self.assertRegex(config.get(attr), r"^\d{2,3}$")

    def test_mcc_overrides_are_complete(self):
        directory = ROOT / "overlay/FrameworksResSm8450/res"
        for d in directory.glob("values-mcc*"):
            names = {e.get("name") for e in ET.parse(d / "config.xml").getroot()}
            self.assertEqual(names, {"config_sms_enabled_single_shift_tables",
                                     "config_sms_enabled_locking_shift_tables"}, d.name)

    def test_chinese_ssid_charset_is_one_item(self):
        root = ET.parse(ROOT / "overlay/WifiResSm8450/res/values/config.xml").getroot()
        charsets = root.find("string-array[@name='config_wifiCharsetsForSsidTranslation']")
        self.assertEqual([i.text for i in charsets], ["zh,GBK"])


if __name__ == "__main__":
    unittest.main()
