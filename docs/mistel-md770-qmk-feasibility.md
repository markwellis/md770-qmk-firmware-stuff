# Mistel MD770BT-M: QMK feasibility

Assessed on 2026-11-12 using the keyboard connected to a Linux host, the public
distributor firmware and current QMK sources. This assessment made no USB
writes and flashed no firmware. Earlier lighting experiments are recorded in
[mistel-md770.md](mistel-md770.md).

**A wired QMK port is technically credible, but it is an embedded firmware
project rather than a keymap configuration task.** There is strong evidence
that the processor family and USB support already exist in QMK. The main
remaining work is board-specific: recovery, communication between halves,
and coordinated key scanning and RGB output. Bluetooth remains a separate,
less predictable task.

The current evidence is sufficient to justify further investigation. It is
not sufficient to produce an image that is safe to flash on this unit.

Further work recovered the owner's V1.07.02 updater and confirmed that
version through a live, read-only version-page query. Both halves have now
been decompiled, and the split transport has been traced. See
[the firmware reconstruction](mistel-md770-firmware.md) for the newer
findings; the initial assessment below records what was known beforehand.

The current target is wired operation with RGB; the owner removed the
Bluetooth hardware and batteries. The later reconstruction supplies enough
information to begin implementing the port. Matrix/key tables and split
behaviour are recovered. The right application's external SPI-flash driver
and four profile sectors are also identified in the reconstruction.
QMK can explicitly initialise inherited clock/timer state. These findings
support a software implementation, including a persistence backend; exact
chip identity and operation on this unit still need confirmation and tests.
Independent physical recovery must be verified before any diagnostic or
QMK firmware write. See the [recovery investigation](mistel-md770-recovery.md)
for the current prerequisite; the historical milestones below are not
instructions to flash.

A first development port now exists in the separate `qmk_firmware`
repository on branch `mistel-md770-bt`. Both halves and optional right-half
VIA support compile. Astra's maximum-effort static review and the offline
checks are recorded in the firmware reconstruction. Later work verified
right-half ROM entry and saved two matching stock-IAP backups. Hardware
validation and a complete restoration procedure remain pending.

## Evidence and confidence

| Area | Evidence | Consequence |
| --- | --- | --- |
| Connected unit | USB `04d9:0419`, product `MD770BT-M`, `bcdDevice 0710`; vendor HID interface with 64-byte reports. | Identifies the right-hand application, but not the exact MCU or PCB revision. |
| Processor family | Decoded applications have a Cortex-M0+ style vector layout, stack near the top of 16 KiB SRAM, and peripheral addresses and interrupt positions matching HT32F523xx. | Strong family-level match; chip markings or a supported identification query must establish the exact part. |
| QMK platform | Mainline `annepro2/c18` selects `HT32F523xx` and an `HT32F52352` linker script. | We should be able to reuse processor, USB and GPIO support if the hardware match is confirmed. |
| Boot arrangement | Both vendor applications start at `0x3200`, with a header at `0x3bf8`. The right application resets to the bootloader using `0x55aafaf5` at `0x20003ffc`. | Closely resembles a working QMK port for another CYKB keyboard. The bootloader itself has not been read or tested here. |
| Separate halves | The updater contains distinct left and right applications with different pin assignments and header words. | A single unmodified image cannot be assumed to work on both halves. |
| RGB and matrix | The right application changes PA1–PA8 between key inputs and lighting row outputs within its timer routine. | Lighting and key scanning need one coordinated implementation. Two independent stock QMK drivers would be an unsafe assumption. |

The processor comparison uses the
[QMK HT32 device header](https://github.com/qmk/ChibiOS-Contrib/blob/qmk-master/os/common/ext/CMSIS/HT32/HT32F523xx/ht32f523x2.h)
and [Anne Pro 2 C18 configuration](https://github.com/qmk/qmk_firmware/blob/master/keyboards/annepro2/c18/rules.mk).
For example, the right image's active ADC, BFTM0, SPI0, SPI1 and USB vectors
occupy the interrupt positions in that header, and their handlers access the
corresponding peripheral addresses. This is stronger evidence than the
Holtek USB vendor ID alone.

The [MK Typist port](https://github.com/jpsutton/mk-typist-research)
demonstrates that QMK can run under this style of stock bootloader. It is a
useful starting point, not compatible MD770 firmware. Its application header
starts `04040000`; the decoded MD770 right and left headers start
`040450c0` and `04046080` respectively.

## What the binaries already reveal

These findings describe the old public updater images, not a dump of the
installed firmware. The extraction method, source ZIP and right RGB image
hash are recorded in [mistel-md770.md](mistel-md770.md).

The right RGB image is 62,444 bytes. Its matrix read at `0xcd82` samples
PA1–PA8. The row table at `0x11574` gives PB14, PB7, PD0, PA15, PA11, PB13,
PD2 and PC1. This is an eight-by-eight electrical scan; some positions may
be unused or reserved. Physical key positions still need mapping.

The important complication is visible at `0x3498`: the timer interrupt
blanks lighting, stops its PWM timer, calls the matrix scan at `0x602c`,
then selects the next lighting row and resumes PWM. The matrix scan
temporarily makes PA1–PA8 inputs. The same pins are subsequently driven as
outputs for lighting. This sharing is established in the analysed firmware;
PCB continuity checks are still needed to confirm the connected revision.

The RGB conversion at `0xa1b4` maps colour slots into a hardware buffer.
The serial output routines at `0xa32c`, `0xef58` and `0xefa0` provide leads
for reconstructing the LED protocol: PC12 carries serial data, PC15 clock
pulses, and PB10 participates in the latch/control sequence. PC11 is used
in the lighting enable/disable path. The LED driver chip, its electrical
limits and the complete timing contract remain unidentified. Do not assume
WS2812 LEDs or copy the Typist's LED pinout.

The left updater application is 36,396 bytes, SHA-256
`3b49993276d8a6cce109af30f5eae6eea759c298bdc297479b7dc87c652da591`.
Its scan at `0x4df8` samples PA0–PA7. The table at `0xac30` gives PB10,
PB11, PD0, PA10, PA11, PA8, PD1 and PD2. Its timer routine at `0x3370`
also coordinates scanning and lighting. These differences rule out simply
reusing the right-hand matrix and LED configuration on the left.

## Implementation scope

| Milestone | Assessment | Main work |
| --- | --- | --- |
| One half over USB, lights disabled | Plausible; moderate work once hardware and recovery are established. | Clock and board setup, correct linker/header arrangement, watchdog handling, matrix mapping and a bootloader return command. |
| Complete wired keyboard | Plausible; substantial work. | Establish the electrical interconnect and protocol, integrate both matrices, verify simultaneous keys and modifiers across the split. |
| Programmable keys and layers | Low additional effort after reliable wired scanning. | Use normal QMK keymaps, layers and macros. Compiled keymaps do not require writable settings storage. |
| Clean notification lighting | Plausible; substantial driver work. | Coordinate multiplexing with scanning, map LEDs, implement stable brightness and device-timed alerts. |
| VIA/Vial-style persistent remapping | Separate medium-sized task. | Identify settings storage and implement a suitable persistence backend. Do not add internal-flash writes before its layout and protection are understood. |
| Bluetooth with stock behaviour | Uncertain; potentially the largest task. | Identify the radio and interface, retain or replace its protocol, then validate pairing, reconnect, sleep, wake and battery management. |

For someone experienced with QMK and embedded reverse engineering, the
wired keyboard plus reliable RGB is a project spanning multiple development
and hardware-testing sessions, potentially weeks of part-time work. A full
Bluetooth replacement could become a much longer project. These are effort
categories, not delivery estimates; recovery and the interconnect could
change the scope substantially.

There are two reasonable split approaches. If the existing left firmware
exposes usable key state, a QMK right half could initially retain it.
Otherwise port both halves and use an appropriate transport over the
existing wiring. The USB-C connector does not establish the electrical
protocol. QMK supports a
[custom split transport](https://docs.qmk.fm/features/split_keyboard), so
an unusual stock link is not automatically a blocker. Whether it can use
an existing driver remains unverified.

For notifications, a small [Raw HID command](https://docs.qmk.fm/features/rawhid)
can request a colour, pulse interval and duration. The keyboard would time
the alert locally, restore the previous state and stop on timeout. This
would remove the competition with the stock renderer that causes the
current flicker. It still depends on getting the low-level LED scanning
right; QMK alone does not fix that driver.

Bluetooth is not categorically incompatible with QMK: its
[Anne Pro 2 driver](https://github.com/qmk/qmk_firmware/blob/master/keyboards/annepro2/annepro2_ble.c)
communicates with a separate radio controller. That demonstrates an
architecture we could use if the MD770 has an accessible radio protocol.
It does not demonstrate MD770 compatibility. USB Raw HID alerts would also
not automatically become available over Bluetooth.

## What must happen before flashing

The first useful hardware evidence is clear photographs of both sides of
both PCBs: MCU markings, crystals, LED drivers, radio/module markings,
external memory, test pads and board revision. With power disconnected,
continuity measurements should identify reset, SWD and boot-selection pads
and the inter-half cable connections. Chip markings and boot access are the
first blockers to a defensible prototype, before spending time on a full
keymap or animation engine.

Recovery needs its own investigation. The
[Typist recovery research](https://github.com/jpsutton/mk-typist-research/blob/main/docs/flashing-and-recovery.md)
shows why owning an SWD probe is not by itself a recovery guarantee: its
chip is read-protected, and unlocking erases the stock bootloader. We have
not established the MD770's protection settings, physical boot-entry path
or whether the same watchdog recovery mechanism exists.

No complete backup of either MD770 controller or its bootloader exists from
this investigation. The owner subsequently supplied the V1.07.02 updater,
matching the live right-half version metadata. It supplies applications,
not a complete recovery image. The installed application's checksum has
not yet been compared against the extracted layout variants.

The next device session should first collect non-mutating information and
version-page replies from each half, then establish bootloader entry and
exit without erasing anything. Compare a matching official application
against the device's checksum if the bootloader supports that query.
Entering the bootloader interrupts typing and is a separate step from
ordinary read-only queries.

A full backup may require a narrowly patched, matching stock application
if debug reads are locked, as on the Typist. That method itself requires a
firmware write; it is not a risk-free preliminary read. Its applicability
and recovery trade-off must be settled before attempting it. Preserve both
bootloaders, version data and any external settings storage when a backup
route is available. Do not mass-erase or unlock merely to discover whether
it helps.

A logic analyser is likely useful for passive capture of the stock split,
radio and LED traffic. A suitable 3.3 V SWD probe may help after the chip and
pads are identified. Neither should be connected using a guessed pinout.

## First prototype and acceptance criteria

After the recovery gate, start with one half connected directly to USB,
lighting held disabled, no Bluetooth and a compiled keymap. Prove stable
enumeration, all local key presses/releases, modifiers, and return to the
stock bootloader through a path independent of the key matrix. Reserve the
bootloader's SRAM word and verify the actual vector/header addresses in the
built image. A host return command still cannot rescue broken USB, so it
does not replace independent recovery.

Then establish the full wired split before enabling RGB. Test held keys,
rapid typing and modifiers across halves, followed by disconnect/reconnect
and suspend/resume. Finally add steady RGB and device-timed alerts while
typing, checking for both visible flicker and lost key events. Bluetooth
and persistent remapping should follow only after these stages work.

A small patch to the matching stock renderer could deliver lighting alerts
with less engineering than QMK, while retaining existing split and Bluetooth
behaviour. It has the same image-matching and recovery prerequisites, and
would not deliver QMK's programmable-key features. For both programmability
and lighting, the staged wired QMK route is worth pursuing once the hardware
and recovery questions are answered.

Mistel's [MD770 PRO QMK announcement](https://www.mistelkeyboard.com/whats-new/ec834031e69ebc0ee19705c1d27cac66)
concerns a separate product and is not evidence that its firmware can be
flashed on the MD770BT-M.
