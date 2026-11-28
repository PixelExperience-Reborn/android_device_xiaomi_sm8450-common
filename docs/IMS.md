# IMS: VoLTE, видеозвонки и Wi-Fi Calling

IMS работает на стоковом стеке Qualcomm из OS3.0.8.0, так же, как в
LineageOS lineage-24.0 для sm8450 (Android 17). Исходников у этого стека нет:
файлы берутся из официальной OTA по SHA-256 (`proprietary-files.txt`, разделы
Radio, IMS, CNE and IWLAN).

## Как это устроено

| Звено | Что это | Откуда |
|---|---|---|
| Модем | регистрация в IMS по профилю оператора (MBN) | firmware OS3.0.8.0 |
| `qcrilNrd`, `imsdaemon`, `ims_rtp_daemon` | RIL, SIP-стек и медиа (RTP) | vendor, сток; `ims_rtp_daemon` грузит seccomp `imsrtp.policy` |
| `vendor.qti.hardware.radio.ims` (AIDL v7) | связь ImsService с RIL | сервер — qcrilNrd, объявлен в нашем VINTF |
| `org.codeaurora.ims` (`ims.apk`) | ImsService (MMTEL): VoLTE, VT, VoWiFi | system_ext/priv-app, сток, подпись платформы |
| `com.qti.phone` (`QtiTelephony`), `qcrilmsgtunnel`, `QtiTelephonyService` | расширения телефонии Qualcomm, туннель OEM-hook | system_ext, сток |
| `vendor.qti.imsrcs` (`ImsRcsService`) и jar `vendor.qti.ims.*-java` | RCS (UCE/presence) | system_ext, сток |
| `ims-ext-common`, `qti-telephony-utils`, `qti-telephony-hidl-wrapper`, `extphonelib` | общие библиотеки этих приложений (`uses-library`) | `vendor/codeaurora/telephony`, Qualcomm LA.QSSI.17.0 (ветка `port/a17-qti-telephony-qssi17-20261127`), собираются под Android 17 |
| `qcrilhook.jar`, `uim*library.jar`, `uimgbaservice` | OEM-hook и GBA-аутентификация SIM | system_ext/product, сток |
| `vendor.qti.iwlan` (`IWlanService`) | WLAN-сервисы данных, сети и qualified networks для Wi-Fi Calling | vendor/app, сток; HAL IWLAN у qcrilNrd (`libqcrilDataModule`) |
| `cnd`, `CneApp` | оценка качества Wi-Fi для переключения LTE/NR ↔ Wi-Fi | vendor, сток; cnd регистрирует `vendor.qti.data.factory@2.5`, `data.latency`, `mwqemadapter` |
| `CACertService` | сертификаты ePDG для Wi-Fi Calling (`vendor.qti.hardware.cacert`) | vendor/app, сток |

Telephony привязывает ImsService по `config_ims_mmtel_package` и
`config_ims_rcs_package` (`overlay/TelephonyResSm8450`), IWLAN — по
`config_wlan_*_service_package` и `config_qualified_networks_service_package`
(`overlay/FrameworksResSm8450`). Значения взяты из стоковых оверлеев HyperOS
(`TelephonyResCommon_Sys`, `FrameworksResCommon_Sys`).

## Что нужно этим приложениям на AOSP

- **`android.telephony.TelephonyBaseUtilsStub.isMiuiRom()`** — класс
  фреймворка HyperOS. Его вызывают `ims.apk` и `QtiTelephony.apk` (проверено
  по dex). Заглушка `xiaomi-telephony-stub` (`hardware/xiaomi/telephony`, как у
  LineageOS) стоит в boot classpath (`PRODUCT_BOOT_JARS`), чтобы класс
  находился в любом процессе. Boot jar должен быть в корневом пространстве
  имён Soong: `platform-bootclasspath` не видит модули из `soong_namespace`
  (у LineageOS это делает их собственный патч Soong), поэтому заглушка не в
  дереве устройства.
- **`QtiTelephonyCompat`** объявляет защищёнными broadcast'ы, которые
  отправляет QtiTelephony (`RADIO_POWER_STATE`, `ESSENTIAL_RECORDS_LOADED`).
- **Подпись платформы.** Приложения подписываются ключом сборки: `ims.apk` и
  `QtiTelephony` используют скрытые API телефонии, а CneApp, IWlanService и
  CACertService делят `sharedUserId` `com.qualcomm.qti.qtidataservices`.
  Разрешения priv-app — стоковый `telephony_system-ext_privapp-permissions-qti.xml`.
- **Одноимённые библиотеки.** `vendor.qti.imsrtpservice@3.0` есть и в
  system_ext (для `lib-imsvt`), и в vendor (для `ims_rtp_daemon`): у
  вендорной копии модуль `_vendor` (`MODULE_SUFFIX`, `extract-files.py`).
- `telephony-ext` не нужен: на `org.codeaurora.internal` эти приложения не
  ссылаются.
- `libgui`: `libimsmedia_jni` и `lib-imsvideocodec` импортируют
  `Surface(sp<IGraphicBufferProducer>, bool, sp<IBinder>)` и
  `Surface::getIGraphicBufferProducer()`; в Android 17 обе сигнатуры есть.

## Свойства

`persist.dbg.{volte,vt,wfc}_avail_ovr=1` показывают переключатели VoLTE, VT и
Wi-Fi Calling для любого оператора: регистрацию решают модем (MBN оператора) и
CarrierConfig (`overlay/CarrierConfigResSm8450/res/xml/vendor.xml`, профиль
Qualcomm в редакции LineageOS). `persist.vendor.cne.feature=1` включает CNE,
`persist.vendor.data.mode=concurrent` — QTI и ADPL рядом с netmgrd
(`init.class_main.sh`), как в стоке.

## Не входит

DPM (`dpmd`, `tcmd`, `dpmQmiMgr`, `vendor.dpmd`): системные службы с доменами
SELinux system_ext, которых в сборке пока нет; IMS, IWLAN и CNE без него
работают. AT-команды модема (`ATFWD`), диагностика (`diag-router`), HIDL
`vendor.qti.hardware.radio.ims@1.x` (ни один поставляемый бинарник их не
грузит).

## Проверить на устройстве

Регистрация IMS (`*#*#4636#*#*` → IMS-статус), звонок VoLTE в обе стороны, VT,
Wi-Fi Calling с выключенной сотовой сетью, переход Wi-Fi ↔ LTE во время звонка,
экстренный вызов, SMS по IMS, обе SIM. Логи: `adb logcat -b all` (теги
`ImsService`, `QtiImsExt`, `IWlan`, `CnE`), `adb shell dumpsys telephony.registry`.
