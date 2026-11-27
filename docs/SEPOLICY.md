# SELinux mondrian на Android 17

## Решение

Архивная политика Qualcomm CAF/Lineage `device_qcom_sepolicy_vndr_sm8450`
(Android 14) **не подключается**: аудит организации
(`docs/ANDROID_17_MONDRIAN_SM8450_VENDOR_SEPOLICY_AUDIT.md` в её ветке audit)
показал, что она тянет заблокированный `device/qcom/sepolicy`, массовые
`dontaudit` и права под чужое железо. Политика пишется в наших деревьях и
покрывает только реально поставленные службы.

## Этап первой загрузки (сейчас)

`tools/gen_bringup_sepolicy.py` строит `sepolicy/vendor` обоих деревьев из
скомпилированной стоковой политики OS3.0.8.0 (`vendor/etc/selinux` OTA):

- домены и типы исполняемых файлов служб, которые запускают наши init-скрипты,
  с атрибутами HAL-серверов как в стоке, и переходы `init_daemon_domain`;
- переход `init → vendor_qti_init_shell` для служб, запускаемых через
  `/vendor/bin/sh` (как в стоке);
- метки исполняемых файлов из стокового `vendor_file_contexts`;
- `hwservice_contexts` и `service_contexts` HAL, объявленных в нашем VINTF.

Типы, которые уже определяет политика AOSP 17 (`hal_*_default`, `rild`, `tee`,
`mediacodec`, `vendor_modprobe`, ...), не дублируются. Правил `allow` нет.

init не запускает службу без перехода в домен даже в permissive, поэтому эти
объявления нужны с первой загрузки. Сборки userdebug/eng грузятся с
`androidboot.selinux=permissive` (bootconfig; init учитывает его только на
них), user остаётся enforcing.

Проверка: `tests/test_sepolicy.py`; актуальность сгенерированных файлов —
с `PE_STOCK_ROOT` (распакованная OTA) и `PE_AOSP_SEPOLICY` (system/sepolicy).

## Дальше

1. Первая загрузка: собрать отказы (`dmesg`, `logcat -b events | grep avc`).
2. Правила `allow` по каждому домену — минимальные, для подтверждённых
   потребителей; метки устройств `/dev`, sysfs, свойств и данных.
3. Переход на enforcing и проверка neverallow/CTS/VTS.
