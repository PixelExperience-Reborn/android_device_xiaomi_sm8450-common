# Стоковые блобы на Android 17: фиксапы, шимы, config.fs

Стоковый vendor OS3.0.8.0 собран под Android 12. Сборка Android 17 проверяет
каждый блоб (`check_elf_file`), каждый `.rc` (`host_init_verifier`) и каждый
XML (`xmllint`), поэтому то, что изменилось в платформе с тех пор, видно ещё
до прошивки. Блобы не хранятся в репозиториях: `tools/extract_proprietary.py`
берёт их из официального OTA (сверяя SHA-256), затем применяет к копии
`tools/blob_fixups.py`. Что изменено, записывается в
`vendor/xiaomi/*/proprietary/provenance.json`.

## Что нужно блобам

| Блоб | Что изменилось в Android 17 | Решение |
|---|---|---|
| `android.hardware.security.keymint-service-qti`, `libqtikeymint.so` | `IRemotelyProvisionedComponent` вынесен из библиотеки keymint в `android.hardware.security.rkp` (keymint-V1 её не импортирует). Без неё сервис KeyMint не загрузится: не будет ключей и расшифровки `/data` | `add_needed android.hardware.security.rkp-V1-ndk.so` |
| `libcamxcommonutils.so`, `hw/com.qti.chi.override.so` (камера) | `SetTaskProfiles` раньше был с C-линковкой, теперь C++-перегрузки | `add_needed libprocessgroup_shim.so` (`compat/libprocessgroup_shim.cpp`) |
| `libMiVideoFilter.so`, `libTrueSight.so`, `libalLDC.so`, `libalhLDC.so` | `libnativewindow` для vendor собирается без версий символов (LLNDK `unversioned`) | импорты версии `LIBNATIVEWINDOW` делаются неверсионными; на устройстве они связываются с версией по умолчанию в настоящей библиотеке |
| `etc/camera/mondrian_*motiontuning.xml`, `pureView_parameter.xml` | битый XML у Xiaomi (`<?xml=version`, атрибуты без кавычек) | правка только этих мест, остальное (в том числе CRLF) не меняется |
| `etc/media_codecs_cape.xml` | подключает `media_codecs_google_{audio,c2,telephony}.xml`, которых в сборке нет (программные кодеки AOSP объявляет APEX swcodec) | эти `Include` удаляются |

`add_needed` работает так же, как patchelf: свободных записей в `.dynamic` у
блобов нет, поэтому в конец файла добавляется сегмент `PT_LOAD` (RW) с новыми
`.dynstr` и `.dynamic`. Старые смещения строк остаются верными. На новый сегмент
перенаправляются `PT_DYNAMIC`, `DT_STRTAB`/`DT_STRSZ` и заголовки секций, как
того требует `ElfReader` bionic. Тесты (`tests/test_blob_fixups.py`) собирают
библиотеку и исполняемый файл с неразрешённым символом, и загрузчик хоста
действительно загружает их после фиксапа. На стоковых файлах тесты проверяют
то же, что проверяет bionic.

## init: пользователи и HIDL-интерфейсы

- `config.fs` (`TARGET_FS_CONFIG_GEN`) задаёт стоковые AID (`vendor_qti_diag`,
  `vendor_qrtr`, `vendor_rfs`, ... 2901–2909) и права и capabilities стоковых
  демонов (`pd-mapper`, `cnd`, `pm-service`, `sensors.qti`, `loc_launcher`,
  IMS, Bluetooth и другие). Генератор Android 17 строит из него `passwd` и
  `fs_config_files`, совпадающие со стоковыми. Без этого `.rc` не прошли бы
  проверку, а демоны остались бы без нужных capabilities.
- `prebuilt_hidl_interfaces` (`Android.bp` здесь и в mondrian) объявляет
  HIDL-интерфейсы стоковых служб, которые есть только в виде блобов
  (`vendor.display.color`, `AGMIPC`, `dsp`, `limits`, интерфейсы камеры), чтобы
  init-проверка знала строки `interface` в их `.rc`.
