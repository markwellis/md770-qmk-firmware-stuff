#!/usr/bin/env bash
set -euo pipefail
QMK_ROOT=$(realpath "${1:?QMK checkout required}")
BUILD_ROOT=${2:?New build directory required}
PROOF_ROOT=$(cd "$(dirname "$0")" && pwd)
test ! -e "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"
BUILD_ROOT=$(cd "$BUILD_ROOT" && pwd)
for tool in git patch make arm-none-eabi-gcc arm-none-eabi-size arm-none-eabi-objdump python3; do
    command -v "$tool" >/dev/null
done
test "$(git -C "$QMK_ROOT" rev-parse HEAD)" = 42e3f8dd2fdd450533316dda28b18d47806609d3
test "$(git -C "$QMK_ROOT/lib/chibios" rev-parse HEAD)" = 6170ddf92d55be54c89b708d1882eea229edeb2c
test "$(git -C "$QMK_ROOT/lib/chibios-contrib" rev-parse HEAD)" = 410d3636a15485aefc74559a52e38c8a642b8ad9
git clone https://github.com/hansemro/ht32_usb_dfu.git "$BUILD_ROOT/ht32"
git -C "$BUILD_ROOT/ht32" checkout --detach ffe44be6238f1446c15c04f6768b09f198a33f1b
git clone https://github.com/OpenKemove/kemove_lpc_dfu.git "$BUILD_ROOT/gpl-dfu"
git -C "$BUILD_ROOT/gpl-dfu" checkout --detach 4cbfb9d889550fcd6a227fed68cfeb9787aeb86b
cd "$BUILD_ROOT/ht32"
rmdir ChibiOS ChibiOS-Contrib
ln -s "$QMK_ROOT/lib/chibios" ChibiOS
ln -s "$QMK_ROOT/lib/chibios-contrib" ChibiOS-Contrib
cp "$BUILD_ROOT/gpl-dfu/source/usbdfu.c" source/usbdfu.c
cp "$BUILD_ROOT/gpl-dfu/source/usbdfu.h" source/usbdfu.h
cp "$QMK_ROOT/lib/chibios/os/rt/templates/chconf.h" cfg/chconf.h
cp "$QMK_ROOT/lib/chibios/os/hal/templates/halconf.h" cfg/halconf.h
cp "$QMK_ROOT/keyboards/mistel/md770rgb_bt/mcuconf.h" cfg/mcuconf.h
cp "$QMK_ROOT/keyboards/mistel/md770rgb_bt/ld/ht32f52352_md770.ld" secondary.ld
patch -p1 < "$PROOF_ROOT/adapt.patch"
cat > main.c <<'MAIN'
#include "ch.h"
#include "hal.h"
#include "usbdfu.h"

int main(void) {
    halInit();
    chSysInit();
    usbDisconnectBus(&USBD1);
    chThdSleepMilliseconds(1500);
    usbStart(&USBD1, &usbcfg);
    usbConnectBus(&USBD1);
    while (true) {
        chThdSleepSeconds(600);
    }
}
MAIN
make -j4
arm-none-eabi-size -A build/usbdfu.elf
arm-none-eabi-objdump -h build/usbdfu.elf
python3 - <<'CHECK'
from pathlib import Path
import hashlib, struct
image=Path('build/usbdfu.bin').read_bytes()
stack,entry=struct.unpack_from('<II',image)
assert len(image)%4==0 and len(image)<=0x6000-0x3200
assert stack%8==0 and 0x20000000<stack<=0x20003fe0
assert entry&1 and 0x3200<=entry&~1<0x3200+len(image)
assert struct.unpack_from('<III',image,0x9f8)==(0x040450c0,0x34000001,0x00020004)
print('OFFLINE BUILD ONLY; DO NOT FLASH',len(image),hashlib.sha256(image).hexdigest())
CHECK
