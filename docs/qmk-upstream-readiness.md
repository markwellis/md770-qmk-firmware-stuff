# MD770 QMK development

The port lives in the separate `qmk_firmware` repository on branch
`mistel-md770-bt`. The right half has passed USB-only QMK installation,
basic typing and cold reconnect. The recorded
right half has passed [stock recovery](mistel-md770-stock-restore.json).
Both halves now have verified ROM entry, two matching IAP backups and
successful stock restoration. Left-half QMK, split operation and RGB remain
untested. The [first right-half test record](mistel-md770-right-qmk-first-test.json)
records the exact build and verified behaviour.

The refinement is recorded in QMK commit `789e14987a`. Both halves pass
strict lint and formatting checks. Eighteen host tests pass, covering UART
framing, SPI erase geometry and DIP behaviour. Five firmware configurations
build: both defaults, right VIA and both halves without RGB Matrix.
The first right-half hardware build disables RGB animations. The port
contains no custom notification protocol; this work is limited to the wired
QMK port.

## Build prerequisites

The branch contains the SPI-flash erase-geometry correction as a separate
commit, `2ae8c20db1`. Submit that independently of keyboard support.

The pinned ChibiOS-Contrib revision has an incorrect HT32 reset-controller
address. The correction is preserved in
`patches/ht32f523xx-reset-register.patch` in this repository. With the QMK
checkout beside this repository, apply it from here before building:

```fish
git -C ../qmk_firmware/lib/chibios-contrib apply - < patches/ht32f523xx-reset-register.patch
```

That correction must land in ChibiOS-Contrib and QMK's dependency pin
before the keyboard can build from an upstream checkout without a patch.
The board's priority encoding also accounts for the pinned platform's
eight-bit priority declaration on a controller with two implemented bits.

## Implementation boundaries

Hardware configuration, layouts, RGB coordinates, supported settings and
the default keymap data use QMK JSON. Clock setup, the shared matrix/RGB
multiplexer and the existing UART framing need board-specific C.
Ordinary GPIO uses QMK helpers. Grouped GPIOA direction/input operations
remain in the scan interrupt because those pins alternate between matrix
inputs and LED row outputs. Peripheral alternate functions use ChibiOS PAL.

The RGB driver retains electrical slot mappings and the inter-half payload
order. Its vendor brightness table has been removed; RGB Matrix supplies
its own CIE1931 conversion and the driver expands PWM bytes linearly.
Brightness is therefore not visually equivalent to the old implementation,
and a stock left half can apply a different brightness curve.

The default keeps the manual's Fn shortcuts, DIP functions, layout cycle
and main Pn lighting controls. DIP2 takes precedence over DIP4. Mac mode
already swaps Alt/GUI, so DIP3 does not apply that swap twice. DIP changes
clear held reports before changing modifier mappings. The default retains
QMK's other magic flags and restores the DIP-owned flags after magic-key
EEPROM reloads.

The right matrix has eight rows, including the DIP row. The left occupies
global rows 8–15. QMK generates the DIP row's key-event mask from the
layout; the DIP driver can still read that row. An initial physical scan
prevents the active-low DIP contacts being mistaken for four active switches.

## Manual

The supplied [Mistel manual](mistel-md770-user-manual.pdf) is copied unchanged.
Its SHA-256 is
`8b3da7a4256e76d48dfe1a52ecf1a3415847e8c9e8f62b56c2a9ee0f2bda9865`.
English PDF pages 2, 6, 7 and 8 cover DIP, Fn/Pn, lighting and Mac functions.
The firmware reconstruction records the conditional DIP precedence omitted
from the short manual descriptions.

Vendor macro programming and Bluetooth are outside the wired QMK port.
Pn lighting uses native QMK effects and a named palette, not the vendor
effect engine. Per-key vendor colour editing is not reproduced.
Vial-specific code belongs downstream; it is not accepted in upstream QMK.

## Before submission

Complete the dependency updates and document a supported flashing workflow.
Then validate both halves on hardware: every key, the split link, all DIP
combinations, Mac/Fn behaviour, lighting, settings and USB reconnect/suspend.
Keep research images, dumps, decompiler output and host recovery tools in
this repository rather than the QMK keyboard directory.

## First hardware test

The first prepared test uses only the recorded red-switch right half, with
the inter-half cable and battery power disconnected. The DIP positions are
unconfirmed; check them when interpreting key mappings. The left half remains
on stock firmware.

Build the default keymap after applying the reset-register correction above:

```fish
make -j4 mistel/md770rgb_bt/right:default RGB_MATRIX_ENABLE=no TARGET=mistel_md770rgb_bt_right_first_test
```

This disables QMK RGB animations. The shared matrix/LED scan driver still
runs and sends zero PWM data; it is not an electrically isolated LED test.
The build retains the normal external-flash settings backend.

The prepared application is 26,824 bytes, SHA-256
`ef455622c99999992ceb39ed965434fcd5ea6a0c566e15f12adfbbbbef67e3b5`.
It was built from QMK commit `aba11aa9f9` with the dependency correction.
Its initial stack is `0x20000400`, reset vector `0x00003ce1`, and right-hand
compatibility record at `0x3bf8` is `040450c0 34000001 00020004`.

A fallback ROM image preserves bytes `0x0000`–`0x31ff` from the verified
right stock recovery image, places QMK at `0x3200`, and fills the remainder
through `0x1fdff` with `ff`. It excludes the option page. The resulting
130,560-byte image has SHA-256
`d82f62cbe46f23f71ef652d0852008bf12c59a434ed7f01e98e9d6d6ac9f76a3`.
The private test package includes that image, the original stock recovery
image, the reviewed writer, matching source, runtime and checksums.

Normal installation uses the [stock USB updater](usb-flashing.md), preserving
its bootloader and option page. The full reconstructed image and ROM writer
above are fallback recovery artefacts, not the normal flashing route.
SEL2 on the right and SEL4 on the left are only needed if software entry
and the resident updater are unavailable.

After programming succeeds, check that QMK enumerates and then cold-reconnect
USB with all pads open. Check USB identification, every right-half key, held
keys, modifiers and cold reconnect before adding the split link or RGB.
USB programming, basic typing, Backspace/Enter/arrows and cold reconnect
have passed. Every individual key, DIP combination, RGB and settings
persistence still need verification. Pn+Insert entered the retained updater,
and its software reset returned to QMK. A visible updater-entry indication
is deferred until baseline testing is complete. The left half remains on
stock firmware.

## DIP input polarity correction

The first image inverted the right DIP row even though its GPIO scanner
already supplies active-high contact bits. All four physical switches off
therefore reported all four switches as on, enabling Mac-mode media keys.
Removing that complement is a one-line correction in the matrix adapter.
The rebuilt application changes only four binary bytes. Its SHA-256 is
`fdbe9864ab58b5c92294c75c9da6290962430fe081fb2a98b05bf1a936811480`.
The [correction test record](mistel-md770-right-dip-polarity-test.json)
records programming and physical retest results separately.

The actual adapter passes all 256 raw DIP-byte values, including upper-bit
masking, unchanged local key rows and unchanged repeated scans. The original
code fails the all-off case. Seven existing DIP behaviour tests also pass.
The small native harness is under `tests/md770_matrix/`; it stubs hardware
services while compiling the real QMK matrix adapter. With the QMK checkout
beside this repository, run it using:

```fish
nix-shell -p gcc --run 'gcc -std=c11 -Wall -Wextra -Werror -ffunction-sections -fdata-sections -Itests/md770_matrix ../qmk_firmware/keyboards/mistel/md770rgb_bt/md770rgb_bt.c tests/md770_matrix/test.c -Wl,--gc-sections -o /tmp/md770-matrix-test && /tmp/md770-matrix-test'
```

The corrected application passed USB programming and QMK enumeration.
DIP1 OFF → ON → OFF and cold reconnect passed: F12 switches between
normal F12 and Volume Up as expected, and Fn+F12 remains F12. All switches
were left off. The other DIP functions still need the complete keyboard.
