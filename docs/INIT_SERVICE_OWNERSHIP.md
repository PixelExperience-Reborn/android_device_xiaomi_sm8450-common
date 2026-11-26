# init vendor-раздела mondrian (Android 17)

Источник правды — стоковая прошивка **OS3.0.8.0.VMNCNXM**: `vendor/etc/init/hw`,
`vendor/etc/init` и скрипты `vendor/bin`. LineageOS только ориентир, код оттуда не
берётся. Проверка: `tests/test_vendor_init.py`.

## Как загружается init

`ro.hardware=qcom` → init читает `/vendor/etc/init/hw/init.qcom.rc`:

```
init.qcom.rc            (дерево, BSD The Linux Foundation, вычищен под taro)
└─ init.target.rc       (дерево, BSD, вычищен под taro)
   └─ init.qti.kernel.rc (сток без изменений, proprietary-files.txt)
```

Плюс все `vendor/etc/init/*.rc` стоковых служб из `proprietary-files.txt`.

## Что оставлено и зачем

| Что | Где | Зачем |
|---|---|---|
| `mount_all fstab.qcom --early/--late`, `/dev/block/bootdevice` | init.target.rc | монтирование vendor-разделов, persist, /data |
| `vendor.modprobe` (`vendor_modprobe.sh`) | init.qti.kernel.rc | загрузка 275 модулей vendor_dlkm (дисплей, тач, WLAN, камера, аудио) |
| запуск ADSP, CDSP, CVP | init.qti.kernel.rc | аудио, датчики, вычисления на DSP |
| `vendor.qrtr-ns`, `vendor.pd_mapper` | init.qcom.rc, init.target.rc | связь с DSP и модемом |
| `vendor.per_mgr`/`per_proxy` (`pm-service`) | init.target.rc | через него голосуют QCRIL, cnss-daemon, GNSS |
| `qcom-c_main-sh` (`init.class_main.sh`) | init.qcom.rc | запускает `vendor.qcrild` и службы данных |
| `cnss-daemon`, `cnss/fs_ready`, `cnss/recovery` | init.qcom.rc, init.target.rc | Wi-Fi |
| `vendor.sensors` (sscrpcd), `sensors.qti`, права реестра датчиков | init.target.rc, стоковые rc | датчики |
| `vendor.nv_mac` | init.target.rc | MAC Wi-Fi и Bluetooth из NV модема |
| `vendor.ssr_setup` | init.qcom.rc | уровень перезапуска подсистем |
| `qti-media` (`init.qti.media.sh`) | стоковый rc | списки кодеков `_cape` |
| режим зарядки: прошивки и ADSP | init.target.rc | состояние батареи при выключенном телефоне |
| каталоги `/data/vendor/*`, права узлов | init.qcom.rc, init.target.rc | данные стоковых служб |

## Что убрано и почему

- Службы без бинарника в прошивке или для другого железа: wigig, SDIO, FM,
  UART-Bluetooth, датчики других плат, внешний модем (mdm).
- `dhcpcd` (в Android 17 нет), `qti-testscripts`, отладка и сбор дампов
  (diag, tcpdump, cnss_diag, ramdump).
- MIUI: migt/metis, `thermal_message`, `mi_display`, `mi_log`, громкость по
  потокам, серийный номер, разделы logfs/rescue.
- `chmod 0666 /dev/uhid` стока: виртуальные устройства ввода доступны всем.
- `init.qcom.sh` (только старые SoC), `init.qti.ufs.rc` (только отладочный скрипт,
  которого нет в прошивке).

## ueventd

- `/vendor/etc/ueventd.rc` — стоковый файл QTI без изменений (права kgsl, adsprpc,
  qseecom, `/dev/nq-nci`, `firmware_directories /vendor/firmware_mnt/image/`).
- `/odm/etc/ueventd.rc` — дерево mondrian (`rootdir/etc/ueventd.odm.rc`): только
  устройство дисплея ядра `/dev/mi_display` (локальный HBM для отпечатка под
  экраном), права `0660 system graphics` вместо стоковых `0666`. Строки vmmgr
  (trusted VM) и `ntag5-nci` (NFC другой модели) убраны.
- Узлы sysfs `/sys/class/mi_display/disp-DSI-0/*` и права `/dev/goodix_fp`
  (в стоке `0666`) настраиваются вместе с HAL отпечатка (этап C).

## Где будет остальное

- `init.qcom.usb.rc` (ADB, MTP): вместе с USB-стеком Qualcomm. Стоковый
  `init.qcom.usb.sh` на не-user сборках включает по умолчанию порт diag модема.
- Службы Wi-Fi supplicant/hostapd, health (и режим зарядки) — вместе с их AIDL HAL.
- `batterysecret` — вместе с драйвером зарядки Xiaomi в ядре.
