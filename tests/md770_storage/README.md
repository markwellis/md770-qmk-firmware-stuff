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
