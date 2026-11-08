# Native AOSP 17 / mondrian — init service ownership

This document is **source evidence**, not a recommendation to delete
running phone processes or to disable services from existing ROM builds.
The independent PE-Reborn common product does not yet package the
historical init files or claim that vendor HALs are working.

## Reviewed service sources

The working LF52406 common reference has **55** `service` declarations
in `init.qcom.rc`, **7** in `init.target.rc`, **3** in
`init.xiaomi_sm8450.rc`, and **4** in `init.qti.kernel.rc`.
These files are shared with other Qualcomm boards, and service names
can overlap or be overridden. The counts are not equivalent to
the number of active processes on a running mondrian.

`init-service-qualification.json` records key candidates and source
Git blob SHA. Import is blocked until exact vendor binary, binary
partition, interface VINTF/SELinux, boot trigger and service owner are
verified. A successful source checkout does NOT demonstrate runtime.

### P0: core, but verify before enabling

- `vendor.qrtr-ns`, `vendor.pd_mapper`, `vendor.per_mgr`: modem and
  Qualcomm subsystem/peripheral dependencies; **do not delete** as
  "bloat". Verify against the correct Android17 vendor/QMI image.
- `vendor.audio-hal`, `vendor.sensors-hal-multihal`: actual
  vendor-supplied HALs. Original files use `override`, so blindly
  importing could collide with Android17 AIDL/HIDL HAL instance
  ownership and service definitions.
- `vendor.modprobe`: staged module loading depends on complete
  kernel/modules/DTBO/KMI and filesystem ownership. Do not start with
  empty module or mismatched kernel trees.

### Not enabled without need

- `vendor.msm_irqbalance` and `vendor_f2fs_tune`: first measure
  scheduler/IRQ behaviour and validate F2FS/KeyMint, respectively.
  Tuning is not inherently an optimization for this device.
- Historical `dhcpcd_*`, WiGig utilities, factory/debug/test scripts:
  must be justified against current Android17 Mainline networking and
  actual device SKU before any import.
- Legacy FM radio modules and application are explicitly excluded.

## Acceptance for each imported service

Identify a single owning component, executable path, service class and
trigger, user/group/capabilities, SELinux domain and executable labels,
partition and firmware dependencies, AIDL/HIDL registration, property
namespace, init action ordering, and runtime logs. Ensure no duplicate
service names, invalid `override` or stale users/groups. Verify
shutdown/resume and recovery separately.

Only verified required services should be started. Deleting presumed
extras from the original ROM without testing could break modem,
Wi-Fi, audio, biometrics, encryption or recovery.
