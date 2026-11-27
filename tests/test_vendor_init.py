"""The vendor init of sm8450-common against what this build ships.

init.qcom.rc and init.target.rc (rootdir/etc) are the stock OS3.0.8.0 ones
kept to taro; the other scripts come unmodified from the stock vendor
through the proprietary lists. Every import must be shipped, every service
binary must be listed, and what was left out must stay out.
"""
import re
import unittest
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


DEVICE = sibling("mondrian", "android_device_xiaomi_mondrian") or ROOT.parent / "mondrian"
RC = ("init.qcom.rc", "init.target.rc", "init.qcom.usb.rc")
DISALLOWED = re.compile(r"dhcpcd|wigig|qti-testscripts|migt|metis|thermal_message|mi_log"
                        r"|miui|/dev/uhid|fmsmd|radio_iris|init\.qcom\.usb\.sh|init\.qcom\.sh")
VITAL = {"vendor.qrtr-ns", "vendor.pd_mapper", "vendor.per_mgr", "vendor.per_proxy",
         "qcom-c_main-sh", "cnss-daemon", "vendor.nv_mac", "vendor.ssr_setup"}


def listed():
    paths = set()
    for lst in (ROOT / "proprietary-files.txt", DEVICE / "proprietary-files.txt"):
        if not lst.exists():
            continue
        for line in lst.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                paths.add(line.split("|")[0].split(";")[0].lstrip("-"))
    return paths


class VendorInitTest(unittest.TestCase):
    def setUp(self):
        self.text = {name: (ROOT / "rootdir/etc" / name).read_text() for name in RC}
        self.listed = listed()
        self.common = (ROOT / "common.mk").read_text()

    def test_installed_to_vendor_init_hw(self):
        for name in RC:
            self.assertIn(f"device/xiaomi/sm8450-common/rootdir/etc/{name}:"
                          f"$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/{name}", self.common)

    def test_imports_are_shipped(self):
        shipped = {f"/vendor/etc/init/hw/{n}" for n in RC}
        shipped |= {"/" + p for p in self.listed if p.startswith("vendor/etc/init/")}
        for name, text in self.text.items():
            for target in re.findall(r"(?m)^import\s+(\S+)", text):
                self.assertIn(target, shipped, f"{name} imports {target}")

    def test_service_binaries_are_listed(self):
        names = set()
        for name, text in self.text.items():
            for service, binary in re.findall(r"(?m)^service\s+(\S+)\s+(\S+)", text):
                names.add(service)
                path = binary.lstrip("/")
                self.assertIn(path, self.listed, f"{name}: {service} runs {binary}")
        self.assertLessEqual(VITAL, names)

    def test_scripts_run_by_init_are_listed(self):
        for name, text in self.text.items():
            for script in re.findall(r"/vendor/bin/([\w.\-]+\.sh)", text):
                self.assertIn(f"vendor/bin/{script}", self.listed, f"{name} runs {script}")

    def test_left_out_stays_out(self):
        for name, text in self.text.items():
            code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
            self.assertIsNone(DISALLOWED.search(code), name)

    def test_platform_ueventd_is_the_stock_one(self):
        # Device node permissions of the platform (kgsl, adsprpc, qseecom...).
        self.assertIn("vendor/etc/ueventd.rc", self.listed)

    def test_usb_gadget_without_diagnostic_functions(self):
        usb = self.text["init.qcom.usb.rc"]
        code = "\n".join(l for l in usb.splitlines() if not l.lstrip().startswith("#"))
        self.assertIsNone(re.search(r"diag|qdss|dpl|rmnet|gsi\.|cser\.|serial_cdev|usb\.sh", code))
        self.assertNotIn("persist.vendor.usb.config", code)
        for function in ("ffs.adb", "ffs.mtp", "ffs.ptp", "accessory.gs2", "audio_source.gs3", "midi.gs5"):
            self.assertIn(f"mkdir /config/usb_gadget/g1/functions/{function}", code)
        for config in ("adb", "mtp", "mtp,adb", "ptp", "ptp,adb", "rndis", "rndis,adb", "midi", "accessory"):
            self.assertIn(f"on property:sys.usb.config={config} && property:sys.usb.configfs=1", code)
        self.assertIn("import /vendor/etc/init/hw/init.qcom.usb.rc", self.text["init.qcom.rc"])
        self.assertIn("vendor.usb.use_ffs_mtp=1", (ROOT / "vendor.prop").read_text())

    def test_vendor_dlkm_loading_and_dsp_boot(self):
        for path in ("vendor/etc/init/hw/init.qti.kernel.rc", "vendor/bin/vendor_modprobe.sh",
                     "vendor/bin/init.class_main.sh", "vendor/bin/pm-service"):
            self.assertIn(path, self.listed)
        self.assertIn("mount_all /vendor/etc/fstab.qcom --early", self.text["init.target.rc"])
        self.assertIn("mount_all /vendor/etc/fstab.qcom --late", self.text["init.target.rc"])


if __name__ == "__main__":
    unittest.main()
