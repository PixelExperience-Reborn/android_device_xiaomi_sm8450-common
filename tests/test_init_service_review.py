import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InitServiceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((ROOT / "init-service-qualification.json").read_text())

    def test_exact_device_and_reference_sources(self):
        self.assertEqual(self.d["device"], "mondrian")
        self.assertEqual(self.d["platform"], "AOSP 17")
        self.assertEqual(sum(r["service_declarations"] for r in self.d["reference_repos"]), 69)
        for r in self.d["reference_repos"]:
            self.assertRegex(r["blob_sha"], r"^[0-9a-f]{40}$")

    def test_vital_services_not_deleted_or_falsely_qualified(self):
        status = {x["name"]: x["status"] for x in self.d["key_service_candidates"]}
        for name in ("vendor.qrtr-ns", "vendor.pd_mapper", "vendor.per_mgr",
                     "vendor.audio-hal", "vendor.sensors-hal-multihal", "vendor.modprobe"):
            self.assertIn(name, status)
            self.assertTrue(status[name].startswith("blocked_until_"))

    def test_no_legacy_processes_enabled_before_vendor(self):
        self.assertEqual(self.d["new_tree"]["copied_init_service_definitions"], 0)
        self.assertEqual(self.d["new_tree"]["active_vendor_services_approved"], 0)
        config = (ROOT / "common.mk").read_text()
        active = "\n".join(line for line in config.splitlines()
                           if line.strip() and not line.lstrip().startswith("#"))
        for disallowed in ("init.qcom.rc", "init.xiaomi_sm8450.rc", "dhcpcd",
                           "qti-testscripts", "init.f2fs_tune.sh", "bt_fm_slim.ko"):
            self.assertNotIn(disallowed, active)

    def test_fm_remains_excluded_without_disabling_audio(self):
        self.assertTrue(self.d["constraints"]["no_fm_radio"])
        self.assertTrue(self.d["constraints"]["no_disable_of_required_vendor_services_without_proof"])
        services = {x["name"] for x in self.d["key_service_candidates"]}
        self.assertIn("vendor.audio-hal", services)


if __name__ == "__main__":
    unittest.main()
