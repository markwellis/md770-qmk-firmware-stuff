# MD770 settings-storage regression

This compiles QMK's actual wear-levelling core and SPI backing-store backend
with the keyboard's configuration. The flash model enforces NOR programming
and permits erasure only in the reserved 64 KiB block at `0x0000`–`0xffff`.
The logical EEPROM remains 4 KiB with an 8 KiB backing store. It checks a
native block erase, cold reload, journal consolidation and preservation
outside the reserved block. It does not test physical SPI communication.

Run from this repository with the QMK checkout beside it:

```fish
nix-shell -p gcc --run 'gcc -std=gnu11 -Wall -Wextra -Werror -Wno-old-style-declaration -I../qmk_firmware/quantum -I../qmk_firmware/quantum/wear_leveling -I../qmk_firmware/drivers -I../qmk_firmware/drivers/wear_leveling -I../qmk_firmware/drivers/flash -I../qmk_firmware/platforms/test -I../qmk_firmware/platforms -I../qmk_firmware/tmk_core/common -I../qmk_firmware/lib/fnv -include ../qmk_firmware/keyboards/mistel/md770rgb_bt/config.h -DWEAR_LEVELING_BACKING_SIZE=8192 -DWEAR_LEVELING_LOGICAL_SIZE=4096 -DWEAR_LEVELING_SPI_FLASH ../qmk_firmware/quantum/wear_leveling/wear_leveling.c ../qmk_firmware/drivers/wear_leveling/wear_leveling_flash_spi.c ../qmk_firmware/lib/fnv/hash_64a.c tests/md770_storage/test.c -o /tmp/md770-storage-test && /tmp/md770-storage-test'
```

The command uses the backing and logical sizes from the right keyboard's
JSON. The warning exception covers an existing QMK timer-header declaration.

The temporary hardware backup tools used for the native-allocation test are
archived as `backup_probe.c` and `capture_backup.py`. They are not part of
the normal firmware. The probe handles read-only VIA channel `0x7f` requests
for the first 64 KiB plus a 64-byte guard; the capture requires two identical
complete reads and writes a new private file with file/directory sync.

For a temporary diagnostic build, copy `backup_probe.c` into the keyboard
folder as `flash_backup.c`, add `SRC += flash_backup.c` to the right-half
`rules.mk`, and build with `VIA_ENABLE=yes`. Run the capture with:

```fish
sudo -A python3 tests/md770_storage/capture_backup.py /path/to/private-backup.bin
```

Confirm the flash geometry first. Keep the raw backup private; remove the
probe from the final build. The capture creates the backup as root with
mode `0600`.
