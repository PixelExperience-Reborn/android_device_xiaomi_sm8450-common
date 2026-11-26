# HAL mondrian на Android 17: сток OS3.0.8.0 против матрицы A17

Vendor стоковой прошивки OS3.0.8.0.VMNCNXM собран под Android 12 (VINTF
`target-level="6"`, `ro.board.api_level=31`). Android 17 принимает vendor
уровня **7 и выше** (`hardware/interfaces/compatibility_matrices`: 7, 8,
202404–202604), поэтому манифест устройства объявляет уровень 7, и каждый HAL,
который мы ставим, должен подходить под `compatibility_matrix.7.xml` Android 17.

Источник стоковых данных: `vendor/etc/vintf/manifest_cape.xml` (SKU cape),
`vendor/etc/vintf/manifest/*.xml`, `odm/etc/vintf/manifest_mondrian.xml`,
init-скрипты служб и зависимости ELF. Источник требований:
`compatibility_matrix.7.xml` тега `android-17.0.0_r1` и libvintf
`android-security-17.0.0_r3`.

## Файлы

| Файл | Что в нём |
|---|---|
| `vintf/manifest.xml` (sm8450-common) | HAL стоковых служб платформы, `target-level="7"` |
| `vintf/framework_compatibility_matrix.xml` | дополнение матрицы фреймворка для HAL `vendor.qti.*` (`DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE`) |
| `vintf/compatibility_matrix.xml` | матрица устройства: что стоковым службам нужно от фреймворка, без `<vendor-ndk>` |
| `vintf/manifest.xml` (mondrian) | провайдер камеры и службы камеры CHI (postproc, AON) |
| `vintf/framework_compatibility_matrix.xml` (mondrian) | дополнение матрицы для служб камеры |

HAL, собираемые из исходников (этап C), объявляют себя своими фрагментами
VINTF (`vintf_fragments` модулей).

## Правила Android 17, которые здесь учтены

- **Каждый экземпляр манифеста должен быть в матрице фреймворка**
  (`check_vintf` → `checkUnusedHals` для уровня ≥ R). Для `android.*` это
  матрицы AOSP 7–202604, для `vendor.qti.*` — наше дополнение матрицы.
- **Конфликт мажорных версий** HIDL одного пакета (`ISap` 1.2 и `IRadio` 1.6)
  обходится формой `<fqname>@1.2::ISap/slot1</fqname>`, как в стоке.
- Атрибут `optional` в матрицах Android 17 не разбирается: все HAL
  необязательны. Проверка «у HAL матрицы есть определение интерфейса»
  пропускает матрицы без уровня, то есть наши дополнения.
- Проверка устаревших HAL (`checkDeprecation`) сравнивает манифест с
  матрицами ниже целевого уровня; в Android 17 их нет.
- Матрица устройства не сверяется по HAL с манифестом фреймворка, только по
  `vendor-ndk`/`system-sdk`; `<vendor-ndk>` указывать нельзя (VNDK в Android 17
  нет, фреймворк его не объявляет).
- **Ядро.** Матрица уровня 7 требует для 5.10 `minlts 5.10.107`, у нас 5.10.81
  (ядро не обновляется). Сборка проверяет ядро только при
  `PRODUCT_OTA_ENFORCE_VINTF_KERNEL_REQUIREMENTS=true` (не задано), проверка при
  загрузке (`verifyBuildAtBoot`) идёт с `disableKernel()`. Требования к конфигу
  ядра T 5.10 (`android-base.config` и условные ARM64) выполнены полностью;
  расходится только символ тулчейна `AS_IS_LLVM`, которого в 5.10.81 нет.
  Остаётся только тест VTS на версию ядра.
- **ART UFFD GC**: версию ядра сборка не знает, поэтому
  `PRODUCT_ENABLE_UFFD_GC := true` задано явно (GKI android12-5.10,
  `CONFIG_USERFAULTFD=y`).

## Решение по каждому HAL

| HAL | В стоке | Матрица A17 ур. 7 | Решение |
|---|---|---|---|
| boot | HIDL 1.2 | HIDL 1.2 | сток (служба + passthrough `boot@1.0-impl-1.2-qti`) |
| health | HIDL 2.1 | **только AIDL 1** | из исходников: AIDL health + режим зарядки |
| power | AIDL v1 | AIDL 2–3 | из исходников: `vendor/qcom/opensource/power`; стоковый perf HAL остаётся |
| thermal | HIDL 1.0/2.0 (`thermal@2.0-service.qti-v2`) | HIDL 2.0 | сток; 1.0 объявлен рядом с 2.0, как в стоке (для клиентов @1.0) |
| usb | HIDL 1.2 | HIDL 1.0–1.3 | сток |
| graphics.composer | HIDL 2.4 + `IQtiComposer` 3.1 | HIDL 2.1–2.4 | сток; плюс `vendor.display.config` 2.0 (`libdisplayconfig.qti`) и AIDL `display.config` v5 |
| graphics.allocator / mapper | HIDL 4.0 | HIDL 4.0 | сток (`mapper` passthrough 32+64) |
| display color | `vendor.display.color` 1.7, `postproc` 1.0 | — (vendor) | сток |
| audio / effect / soundtrigger | HIDL 7.0 / 7.0 / 2.3 | HIDL 7.0–7.1 / 7.0 / 2.3 | этап C: служба аудио AOSP 17 со стоковыми модулями; тогда же `vendor.qti.hardware.pal` |
| AGM | `vendor.qti.hardware.AGMIPC` 1.0 | — (vendor) | сток |
| bluetooth (HCI) | HIDL 1.0 | HIDL 1.0–1.1 | сток (служба + passthrough `bluetooth@1.0-impl-qti`, `btconfigstore@2.0-impl`) |
| bluetooth.audio | HIDL 2.0 | **только AIDL 2** | из исходников: AIDL Bluetooth Audio |
| wifi | HIDL 1.5 | HIDL 1.3–1.6 | сток |
| wifi.supplicant / hostapd | HIDL 1.4 / 1.3 | **только AIDL** | из исходников: `wpa_supplicant`/`hostapd` AOSP 17 + `lib_driver_cmd_qcwcn` |
| radio / radio.config | HIDL 1.6 + ISap 1.2 / config 1.3 | те же | сток (QCRIL `libqcrilNr`), телефония A17 поддерживает HIDL 1.6 |
| QTI radio | qtiradio 1.0/2.6 + AIDL v5, IMS radio AIDL v7, uim, lpa, am, qcrilhook | — (vendor) | сток, все экземпляры, которые регистрирует QCRIL |
| IMS | `ims.factory` 1.1/2.2, `imsrtpservice` 3.0 | — (vendor) | сток (`imsdaemon`, `ims_rtp_daemon`) |
| tetheroffload | config 1.0, control 1.1 | те же | сток (`ipacm`) |
| nfc | HIDL 1.2 (`vendor.nxp.hardware.nfc` 2.0) | HIDL 1.2 или AIDL | этап C: `android.hardware.nfc-service.nxp` (AOSP 17) |
| secure_element | HIDL 1.2 SIM1/SIM2/eSE1 | HIDL 1.0–1.2 | сток: SIM1/SIM2 — QCRIL, eSE1 — служба QTI; плюс `esepowermanager` 1.1 |
| keymint / sharedsecret / secureclock | AIDL v1 | AIDL 1–2 / 1 / 1 | сток |
| gatekeeper | HIDL 1.0 | HIDL 1.0 | сток (служба + passthrough `gatekeeper@1.0-impl-qti`) |
| identity | AIDL v3 | AIDL 1–4 | сток |
| drm | HIDL 1.4 widevine | HIDL 1.3–1.4 | сток widevine; clearkey — AOSP |
| gnss | AIDL **v1** + HIDL 2.1 в одной службе | AIDL **2** / HIDL 2.0–2.1 | сток, объявлен **только HIDL 1.1/2.1** (+ passthrough `gnss@2.1-impl-qti`). AIDL v1 уровень 7 не принимает; служба при отказе регистрации AIDL пишет ошибку и продолжает с HIDL 2.1 |
| sensors | HIDL 2.1 multihal | HIDL 2.0–2.1 | сток (`sensors.ssc`, `sensors.touch.detect`) |
| camera.provider | HIDL 2.7 `legacy/1` (+ `external/0`) | HIDL 2.4–2.7 | сток, только `legacy/1` (внешнюю камеру никто не обслуживает); плюс `camera.postproc` и `camera.aon` |
| media.c2 | HIDL 1.0 `default` (+ `dolby`, `software`) | HIDL 1.0–1.2 | сток, только `default` (`software` — APEX swcodec, Dolby не ставим) |
| light | AIDL v1 | AIDL 1–2 | сток |
| memtrack | AIDL v1 | AIDL 1 | сток |
| perf, capabilityconfigstore, servicetracker, limits, dsp, qseecom, qteeconnector | — (vendor) | — | сток (с passthrough-реализациями, где служба их грузит) |
| vibrator | AIDL, экземпляр **`vibratorfeature`** | AIDL 1–2 (`default`) | этап C: HAL из исходников под драйвер mondrian |
| biometrics.fingerprint | HIDL 2.1 + расширения Xiaomi | HIDL 2.1–2.3 / AIDL 2 | этап C: AIDL UDFPS поверх стокового `mfp-daemon` |
| ir | HIDL 1.0 | **только AIDL 1** | этап C: AIDL IR (`/dev/ir_spi`) |
| dumpstate, atrace, media.omx | HIDL | — | не ставим |

## Не объявлено, хотя есть в стоке

Сервера этих HAL в нашей сборке нет. Если объявить HAL без сервера, клиенты
будут ждать его бесконечно:

- `vendor.qti.hardware.data.connection`, `data.iwlan`, `eid`,
  `vendor.qti.data.factory`, `data.connectionfactory`, CNE, DPM, imscm/uce,
  `wifidisplaysession`, FM, ANT, Bluetooth SAR, `qccvndhal`, `soter`, `tui_comm`,
  `vpp`, `qxr`, `diaghal`, `sensorscalibrate`, `alarm`.
- Все `vendor.xiaomi.*`, `vendor.dolby.*`, `vendor.nxp.*`.

## Правила

- VINTF устройства пишется в дереве: только HAL, которые реально
  регистрируются, ровно с теми версиями и экземплярами, что в стоковых
  манифестах. Фрагменты VINTF стока не копируются (тест списков запрещает
  `vendor/etc/vintf/`).
- У каждого объявленного HAL сервер и его passthrough-реализация должны быть в
  `proprietary-files.txt` (`tests/test_vintf.py`).
- Службы MIUI (`vendor.xiaomi.hardware.*`, misys, mimd, misight и т.п.) не
  ставятся.
