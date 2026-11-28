# Оверлеи ресурсов (RRO) sm8450-common и mondrian

Android 17 настраивает устройство через ресурсы фреймворка и системных
приложений. Мы задаём их статическими RRO (`runtime_resource_overlay`,
`isStatic`), как сток и LineageOS:

| Модуль | Раздел | Цель | Что задаёт |
|---|---|---|---|
| `FrameworksResSm8450` | vendor | `android` | автояркость доступна, AOD доступен (выключен по умолчанию), Doze, аппаратная цветокоррекция, телефония (5G SA/NSA, буферы TCP, таблицы SMS для mcc 234/262), VoLTE/VT/Wi-Fi Calling и сервисы IWLAN `vendor.qti.iwlan` |
| `SystemUIResSm8450` | vendor | SystemUI | дисплей поддерживает состояния doze |
| `SettingsResSm8450` | vendor | Settings | время ручного поиска сети модемом |
| `TelephonyResSm8450` | vendor | Phone | ImsService MMTEL `org.codeaurora.ims` и RCS `vendor.qti.imsrcs` (docs/IMS.md) |
| `CarrierConfigResSm8450` | vendor | CarrierConfig | `vendor.xml`: параметры операторов для IMS Qualcomm (редакция LineageOS) |
| `WifiResSm8450` | vendor | Wi-Fi | возможности QCA6490 и SoftAP (Wi-Fi 6/6E, WPA3, OWE, ACS), MAC-рандомизация, китайские SSID (GBK) |
| `FrameworksResMondrian` | odm | `android` | яркость, кривая автояркости, 120 Гц, защита OLED от выгорания, 2 SIM, вырез камеры, скругления, статус-бар, профиль питания (Redmi K60, 5500 мА·ч) |
| `FrameworksResMondrianGlobal` | odm | `android` | профиль питания POCO F5 Pro (5160 мА·ч), при `ro.boot.hwc=GL` |
| `SystemUIResMondrian` | odm | SystemUI | отступ значков статус-бара от скруглений |
| `SettingsResMondrian` | odm | Settings | настройка «Плавное отображение» (120 Гц) |
| `SettingsProviderResMondrian` (+`CN`) | odm | SettingsProvider | имя устройства: POCO F5 Pro, в Китае (`ro.boot.hwc=CN`) Redmi K60; автояркость включена по умолчанию |
| `WifiResMondrian` (+`CN`) | odm | Wi-Fi | имя точки доступа по умолчанию, так же по региону |

## Откуда значения

- **Сток OS3.0.8.0.** Значения берутся из оверлеев раздела product HyperOS
  (`FrameworksResCommon_Sys`, `AospFrameworkResOverlay`,
  `DevicesAndroidOverlay`, `SystemUIResCommon_Sys`, `SettingsResCommon_Sys`,
  `WifiResCommon_Sys`). Они декодированы из APK (бинарные ресурсы), и в дерево
  попали только ключи, которые есть в Android 17 (`android-17.0.0_r1`) и
  отличаются от его умолчаний. Переименованный ключ перенесён под новым именем
  (`config_dozeAfterScreenOff` → `config_dozeAfterScreenOffByDefault`).
- **Автояркость.** Сток задаёт пары «люксы → уровень подсветки» в шкале
  панели 1..4095. Это видно по DT панели M11A «xiaomi 42 02 0a»:
  `qcom,mdss-brightness-max-level = <0xfff>`. Android 17 читает
  `config_autoBrightnessLcdBacklightValues` в шкале 1..255
  (`BrightnessSynchronizer`), поэтому значения пересчитаны так:
  `1 + round(уровень / 4095 * 254)`.
  Кривую стока в нитах мы не используем. Для неё нужна таблица «ниты ↔
  подсветка» (`config_screenBrightnessNits`/`Backlight` или `displayconfig`),
  которой в стоке нет. Без такой таблицы Android 17 выбирает простую
  стратегию, а с пустыми значениями подсветки автояркость оказалась бы
  выключена. Предел пользовательской подстройки (`config_autoBrightnessAdjustmentMaxGamma`)
  оставлен по умолчанию AOSP: стоковые 100% отключили бы ползунок при
  автояркости.
- **Геометрия панели.** Оверлеи MIUI рассчитаны на разрешение по умолчанию
  1080×2400 (`persist.sys.miui_resolution=1080,2400,420`), а наша сборка
  работает в родном 1440×3200 при 560 dpi. Например, `config_mainDisplayShape`
  в стоке задан в координатах 1080×2400. Поэтому вырез камеры
  (`M 0,0 H -34 V 120 H 34 V 0 H 0 Z`) взят как в дереве LineageOS mondrian
  (lineage-24.0, проверено на устройстве в родном разрешении), форма экрана
  не задаётся (её строят скругления), а скругления (120 px) и высота
  статус-бара (138 px) — стоковые.
- **Профиль питания.** В стоковом framework-res лежит только заглушка AOSP
  (1000 мА·ч), реального профиля в HyperOS нет. Используются измерения,
  опубликованные LineageOS для mondrian (Apache-2.0, указано в файле).
  Ёмкость батареи совпадает с официальными характеристиками моделей.

## Что пока не задано и почему

| Что | Почему |
|---|---|
| Цветовые режимы (`config_availableColorModes`) | номера режимов QDCM панели в AOSP можно узнать только на устройстве (`dumpsys SurfaceFlinger`); до этого режим AOSP Natural (sRGB) |
| UDFPS (положение сенсора, doze по отпечатку) | HAL отпечатка ещё не собран |
| NFC (`config_skuSupportsSecureNfc`) | HAL NFC ещё не собран |
| Ключи, удалённые в Android 17 | `config_wifi5ghzSupport`/`6ghz` (теперь их сообщает HAL), `config_globallyDisabledComponents` (не AOSP), `config_ntpServer` (теперь `config_ntpServers`) и другие — тест не даёт им вернуться |

## Проверить на устройстве

- Вырез и статус-бар: значки не заходят под камеру в портретной и альбомной
  ориентации.
- Автояркость в темноте, в помещении и на солнце.
- Переключатель «Плавное отображение» (60/120 Гц).
- Имя устройства и точки доступа для своей модели (`getprop ro.boot.hwc`).
- Статистика батареи после зарядки.

`tests/test_overlays.py` проверяет структуру, подключение к сборке и то, что
каждое имя ресурса проверено по Android 17. Тест mondrian дополнительно
проверяет значения устройства.
