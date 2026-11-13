# MD770 QMK development

The port lives in the separate `qmk_firmware` repository on branch
`mistel-md770-bt`. QMK has not been tested on the keyboard. The recorded
right half has passed [stock recovery](mistel-md770-stock-restore.json).
Left-half recovery remains unverified.

The refinement is recorded in QMK commit `789e14987a`. Both halves pass
strict lint and formatting checks. Eighteen host tests pass, covering UART
framing, SPI erase geometry and DIP behaviour. Five firmware configurations
build: both defaults, right VIA and both halves without RGB Matrix.
No QMK image has been flashed. The port contains no custom notification
protocol; this work is limited to the wired QMK port.

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
