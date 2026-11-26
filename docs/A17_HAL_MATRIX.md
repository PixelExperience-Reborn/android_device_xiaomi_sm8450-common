# HAL mondrian на Android 17: сток OS3.0.8.0 против матрицы A17

Vendor стоковой прошивки OS3.0.8.0.VMNCNXM собран под Android 12 (VINTF
`target-level="6"`, `ro.board.api_level=31`). Android 17 принимает vendor
уровня **7 и выше** (`hardware/interfaces/compatibility_matrices`: 7, 8,
202404–202704), поэтому манифест устройства объявляет уровень 7, и каждый HAL,
который мы ставим, должен подходить под `compatibility_matrix.7.xml` Android 17.

Источник стоковых данных: фрагменты `vendor/etc/vintf/manifest*.xml`,
`vendor/etc/init/*.rc` стока. Источник требований: `compatibility_matrix.7.xml`
тега `android-17.0.0_r1`.

## Решение по каждому HAL

| HAL | В стоке | Матрица A17 ур. 7 | Решение |
|---|---|---|---|
| boot | HIDL 1.2 (`android.hardware.boot@1.2-service`, QTI) | HIDL 1.2 | сток; в recovery — passthrough `android.hardware.boot@1.0-impl-1.2-qti` + `libboot_control_qti`, как в стоковом recovery (нужен для A/B sideload) |
| health | HIDL 2.1 | **только AIDL 1** | из исходников: AIDL health (`android.hardware.health-service` + `_recovery`) |
| power | AIDL (`android.hardware.power-service`, QTI) | AIDL 2–3 | сток (проверить версию фрагмента) |
| thermal | HIDL 2.0 (`thermal@2.0-service.qti-v2`) | HIDL 2.0 | сток |
| usb | HIDL 1.2 (`usb@1.2-service-qti`) | HIDL 1.0–1.3 | сток |
| graphics.composer | HIDL 2.4 + `vendor.qti...composer@3.1` | HIDL 2.1–2.4 | сток |
| graphics.allocator / mapper | HIDL 4.0 | HIDL 4.0 | сток |
| audio / audio.effect / soundtrigger | HIDL 7.0 / 7.0 / 2.3 | HIDL 7.0–7.1 / 7.0 / 2.3 | сток (`audio.service_64`, `audio.primary.taro`, PAL/AGM) |
| bluetooth (HCI) | HIDL 1.0 | HIDL 1.0–1.1 | сток (уже в списках) |
| bluetooth.audio | HIDL 2.0 | **только AIDL 2** | из исходников: AIDL `android.hardware.bluetooth.audio-impl` |
| wifi | HIDL 1.5 | HIDL 1.3–1.6 | сток (`android.hardware.wifi@1.0-service`) |
| wifi.supplicant | HIDL 1.4 | **только AIDL** | из исходников: `wpa_supplicant` (AOSP 17) + `lib_driver_cmd_qcwcn` |
| wifi.hostapd | HIDL 1.3 | **только AIDL 1** | из исходников: `hostapd` (AOSP 17) |
| radio / radio.config | HIDL (QCRIL), config 1.3 | HIDL 1.6, config 1.1/1.3 | сток (уже в списках) |
| nfc | HIDL 1.2 (`vendor.nxp.hardware.nfc@2.0-service`) | HIDL 1.2 или AIDL | из исходников AOSP 17: `android.hardware.nfc-service.nxp` (`hardware/nxp/nfc/snxxx`, SN1xx) со стоковыми `libnfc-*.conf` |
| secure_element | HIDL 1.2 (`vendor.qti.secure_element@1.2-service`) | HIDL 1.0–1.2 | сток (+ `esepowermanager`) |
| security.keymint / gatekeeper / identity | AIDL / HIDL 1.0 / AIDL 3 | AIDL 1–2 / HIDL 1.0 / AIDL 1–4 | сток (уже в списках) |
| drm | HIDL 1.4 (widevine) | HIDL 1.3–1.4 / AIDL 1 | сток widevine (уже в списках); clearkey и cas — AOSP |
| gnss | AIDL + HIDL 2.1 | AIDL 2 / HIDL 2.0–2.1 | сток (уже в списках) |
| sensors | HIDL 2.1 multihal | HIDL 2.0–2.1 | сток (уже в списках) |
| camera.provider | HIDL 2.7 | HIDL 2.4–2.7 | сток (уже в списках) |
| media.c2 | HIDL 1.0 | HIDL 1.0–1.2 | сток (уже в списках) |
| light | AIDL (`vendor.qti.hardware.lights.service`) | AIDL 1–2 | сток |
| vibrator | AIDL, экземпляр **`vibratorfeature`** | AIDL 1–2 (`default`) | системе нужен `IVibrator/default`: HAL из исходников под драйвер вибромотора mondrian |
| memtrack | AIDL (`memtrack_qti`) | AIDL 1 | сток |
| biometrics.fingerprint | HIDL 2.1 + `com.fingerprints.extension` | HIDL 2.1–2.3 / AIDL 2 | 2.1 не умеет UDFPS: обёртка (hardware_xiaomi) поверх стокового демона |
| ir | HIDL 1.0 | **только AIDL 1** | из исходников: AIDL IR (hardware_xiaomi) |
| tetheroffload | HIDL (ipacm) | HIDL config 1.0 / control 1.1 | сток |
| dumpstate | HIDL 1.1 | только AIDL | не ставим (необязательный HAL) |
| atrace | HIDL 1.0 | HIDL 1.0 | не обязателен |
| media.omx | HIDL 1.0 | HIDL 1.0 | не ставим (только Codec2) |

## Правила

- VINTF устройства пишется в дереве (`vintf/manifest.xml`, `target-level="7"`):
  только HAL, которые реально ставятся, ровно в тех версиях и экземплярах, что
  регистрируют службы. Фрагменты VINTF стока не копируются.
- Службы MIUI (`vendor.xiaomi.hardware.*`, misys, mimd, misight и т.п.) не
  ставятся; их init-скрипты не переносятся.
- Каждый стоковый файл — в `proprietary-files.txt` с SHA-256 и полным
  замыканием `NEEDED` (`build_lists.py`).
