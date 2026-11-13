# Mistel MD770BT-M firmware reconstruction

Analysed on 2026-11-12. The target is wired operation: the owner has
removed the Bluetooth hardware and batteries. This work extracts and
decompiles the vendor applications; it does not flash the keyboard.

**The firmware reveals enough of the board to design its matrix, split
transport and RGB drivers.** The split connection uses USART0; the right
half sends RGB values to the left and receives its key matrix. Both halves
share GPIO pins between key sensing and multiplexed lighting, so these
functions must remain coordinated. The outstanding hardware questions are
now principally identification, electrical validation and recovery, rather
than an unknown communication architecture.

## Images and confidence

The owner supplied `MD770 RGB BT v1.07.02`, containing
`MD770R_FW_0419_7.02_20230421.exe` and
`MD770L_FW_041A_4.01_20230424.exe`. The right updater contains JP, EU and US
applications; the left contains JP and US applications. Updater metadata
identifies these variants. The connected right half reports `V1.07.02`,
version word `0x00070002`, and USB `04d9:0419`, matching the supplied right
updater's version metadata. Its boot-information reply also contains the
right application's header identifier. Subsequent stock-IAP sum/CRC checks
match both installed US applications: right 7.02 and left 4.01. See the
[right](mistel-md770-updater-check.json) and [left](mistel-md770-left-updater-check.json)
records. The right USB descriptor
at `0xe550` has `bcdDevice 0710`, matching the connected keyboard; the EU
and JP variants use `0720` and `0730`. This identifies the US layout variant.

Addresses below are absolute MCU addresses for the **US** images. EU and
JP builds have different addresses; do not apply these offsets to them.

| Application | Extractor suffix | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Right US 7.02 | `g4e8.firmware.bin` | 49,008 | `8fafdca096756f23626802d5b586b270b0bd512fe5d1c0327db4eafcd4f689b2` |
| Left US 4.01 | `g3e8.firmware.bin` | 36,404 | `febc84d9dc1fd23152218232839279ecb59f255615a6d6c5b4d951a848c85064` |

Both load at `0x3200`, start with stack pointer `0x20003fe0`, and reset at
`0x32c1`. Their headers at `0x3bf8` are respectively
`040450c0 34000001 00020004` and `04046080 34000001 00020004`.
The processor register map and interrupt vectors match HT32F523xx. A
16 KiB SRAM arrangement and the use of PD0–PD2 make an HT32F52352 in a
64-pin package a strong candidate within that family. This is an inference,
not a chip identification read. Compare the
[Holtek datasheet](https://www.holtek.com.tw/webapi/11842/HT32F52342_52_Datasheetv160.pdf)
and [QMK device header](https://github.com/qmk/ChibiOS-Contrib/blob/qmk-master/os/common/ext/CMSIS/HT32/HT32F523xx/ht32f523x2.h).

Subsequent owner photographs identify the right MCU's actual marking as
**HT50F52352**, in a 64-lead package, and both LED drivers as **MBIA043GP**.
The board is marked `MD770BR-RIGHT`, revision `V06 1223BJ`. These physical
observations support the earlier reconstruction; they do not constitute a
read of the MCU's device ID. The photographs and candidate recovery
connections are recorded in the [recovery investigation](mistel-md770-recovery.md#right-half-photographs-and-unpowered-measurements).

The findings below come from matching decompiled control flow to Thumb
instructions, literal pools and data tables in both applications. They
describe what the supplied firmware drives, not measurements of the PCB.
Ghidra output alone is insufficient: indirect callbacks need explicit
function seeds, and its inferred types and function boundaries are
occasionally wrong.

## Split transport

Both halves configure USART0 at `0x40000000`. The UART device descriptors
are at right `0xdfd4` and left `0xab24`; both contain the same settings:

| Setting | Recovered value |
| --- | --- |
| TX | PB0 |
| RX | PB1 |
| Alternate function | AF6 |
| Base baud divisor | `0x10` |
| Control register | `0x01b0`, including eight-bit asynchronous data, no parity and one stop bit |
| Transfer mechanism | Peripheral DMA for transmission and a receive ring buffer |

Pin bytes `0x20` and `0x21` are decoded as port `value >> 5`, pin
`value & 31`. The descriptor's final byte `0x03` is a GPIO mode setting,
not the alternate-function number. The GPIO template's `0x30 >> 3`
selects AF6. Right routines `0xa64c`, `0x39b0` and `0x38f0` establish this
path; the datasheet independently assigns PB0/PB1 to USART0 TX/RX.

Right `0xa040` writes the divider and control register. Divider helper
`0x3788` multiplies the base divider by six in the faster clock mode:
`16` or `96`. These values imply **500,000 baud** with 8 MHz or 48 MHz
peripheral clocks. The divisor is established from code; the absolute baud
rate follows the clock configuration recovered below, conditional on the
inherited AHB/APB dividers retaining their reset values. Holtek's
[USART implementation](https://github.com/RT-Thread/rt-thread/blob/master/bsp/ht32/libraries/HT32_STD_5xxxx_FWLib/library/HT32F5xxxx_Driver/src/ht32f5xxxx_usart.c)
defines the divider as peripheral clock divided by baud rate.

The wire format is the same in both directions, with little-endian words:

| Byte offset | Contents |
| ---: | --- |
| 0 | 16-bit CRC |
| 2 | Bitwise complement of that CRC |
| 4 | `0xa800 | payload_length` |
| 6 | Payload |

The CRC covers the length word and payload, not the preceding checksum
words. It uses polynomial `0x1021`, initial value zero, no reflection and
no final complement: CRC-16/XMODEM parameters. Right encoder `0xa22c` and
parser `0xa1b4`, and left encoder `0x8120` and parser `0x80ac`, agree.
The helper selects hardware CRC control zero, seed zero, and byte writes;
this matches Holtek's
[CRC-CCITT implementation](https://github.com/RT-Thread/rt-thread/blob/master/bsp/ht32/libraries/HT32_STD_5xxxx_FWLib/library/HT32F5xxxx_Driver/src/ht32f5xxxx_crc.c).

```text
body = little_endian_u16(0xa800 | len(payload)) + payload
crc = crc16_xmodem(body, initial=0)
frame = little_endian_u16(crc) + little_endian_u16(crc ^ 0xffff) + body
```

The parser checks the upper five length-word bits, the complementary CRC
words, available byte count and calculated CRC. Its input buffer starts
with an internal two-byte available-count field; that field is not sent on
the wire. Invalid headers advance the parser by one byte. A complete frame
with an invalid CRC is consumed without invoking the payload callback.

The payload callbacks establish the purpose of the link:

| Direction | Payload | Producer | Consumer |
| --- | --- | --- | --- |
| Right → left | 126 bytes: 42 RGB triples | Right `0x5d08`, from `0x2000027a` | Left `0x532c`, to `0x20000164` |
| Left → right | Eight matrix row bytes | Left `0x5318`, from `0x20000131` | Right `0x5d1c`, to `0x20000229` |

### Scheduling, initialisation and loss behaviour

Both directions send periodic complete snapshots. The only direct calls
to the split enqueue functions are right `0x66ca` → `0x42dc` and left
`0x547e` → `0x3d84`. No function-pointer references to either enqueue
function occur in these images. Key-change paths, right `0x5350` and left
`0x4c20`, update their buffers and activity/USB-notification state; they
do not request an immediate split transmission. Receiving RGB also does
not immediately send a matrix reply. There is no acknowledgement,
sequence number or separate handshake/control frame in this path.

| Direction | Scheduling rule | Nominal active-mode interval |
| --- | --- | --- |
| Right → left | `0x66ac` adds elapsed SysTick counts to byte `0x20000028`; at 64 or above it resets the byte and enqueues descriptor `0xdf10` | Approximately 32 ms |
| Left → right | `0x5468` increments byte `0x20000016` once per main-loop batch containing elapsed ticks; every 64 such calls it enqueues descriptor `0xaab4`, provided mode byte `0x20000014` is 2 | Approximately 32 ms when each tick is serviced separately |

These are roughly 31.25 snapshots/s with the nominal 0.5 ms active
SysTick below. Right main routine `0xda78` passes the accumulated tick
count; left `0xa954` passes it but `0x5468` ignores that argument. Thus
coalesced ticks lengthen the left interval; neither side queues catch-up
frames. These are code-derived nominal rates, not measured link timing.
At nominal 500 kbaud, a 132-byte RGB frame takes 2.64 ms on the wire and
a 14-byte matrix frame takes 0.28 ms, including 8N1 framing.

Left mode selection is a separate physical input. Routine `0x53bc` reads
**PB8** and maintains a saturating counter at `0x20000015`. Reaching 16
with PB8 high selects mode 2 and permits periodic matrix transmission;
reaching zero with PB8 low selects mode 1, disables active LEDs and changes
USB state through `0x7a0c` → `0xa30c`. The counter counts main-loop
observations, not SysTick periods. The latter USB routine disables the USB
interrupt/controller when entering its disabled state. PB8's connection
to the interconnect or another board signal remains electrically
unverified; valid RGB packets alone do not replace this mode input.

The first normal enqueue registers the receive callback and arms the
transport. No special initial packet is needed after that registration.
Left callback `0x532c` copies the 126 RGB bytes, enables the LED driver on
the first non-zero frame and disables it on an all-zero frame. Subsequent
non-zero frames refresh its general activity counter. A replacement right
half therefore needs the electrical mode condition and ordinary framed
RGB snapshots, including zero frames when lighting is off.

Enqueue returns without replacing the outstanding packet while its TX
state is busy. The transport retries a local start that was not accepted;
DMA/USART completion clears the pending state. This is local transmission
management, not acknowledgement or retransmission of a lost wire packet
(right `0x4258`, `0xa338`; left `0x3d00`). The next periodic snapshot
repairs a lost update. Incomplete frames wait for more bytes; invalid
headers and CRC failures follow the parser rules above.

Right receive callback `0x5d1c` only copies the eight matrix bytes. No
packet-age counter or automatic release of remote keys was found in this
receive path; the remote buffer is initialised to `0xff` by `0x5584`.
Loss of UART traffic must not be assumed to release held keys. Left
`0x6874` loads a 600-count activity timer, decremented by active SysTick
handler `0x6cb0`; both key changes and non-zero RGB reset it. Power routine
`0x67d4` uses it when USB is absent. Its nominal 300 ms interval is therefore
a general inactivity/sleep mechanism, not a dedicated packet watchdog or
a guaranteed link-disconnect timeout. The physical USB-C contact mapping
and actual unplug/reconnect behaviour remain unverified.

## Key matrix and shared pins

| Half | Sense pins | Select pins, in scan order | Scan routine | Select table |
| --- | --- | --- | --- | --- |
| Right | PA1–PA8 | PB14, PB7, PD0, PA15, PA11, PB13, PD2, PC1 | `0x55f8` | `0xe12c` |
| Left | PA0–PA7 | PB10, PB11, PD0, PA10, PA11, PA8, PD1, PD2 | `0x4dfc` | `0xac48` |

Each scan temporarily changes the sense pins to inputs with pull-downs, sets one select
pin, samples GPIOA, resets the select pin and restores the sense pins to
outputs. Samples are inverted: a low input produces a set matrix bit.
The stored and transmitted matrix is **active-low**: released rows are
`0xff`, a pressed key clears its bit, and the corresponding raw GPIO sense
input is high while that select pin is asserted. Right `0xa8e4` and left
`0x8648` turn a cleared stored bit into a press event. A QMK adapter must
invert these bytes to its usual pressed-bit representation.
Debounce keeps a candidate value and an eight-count stability counter for
each row; changed samples reset that counter. A count is a scan, not an
established number of milliseconds.

Right `0x5350` combines seven local row bytes with all eight remote row
bytes. Its eighth local row follows a separate switch/configuration path.
Consequently, the eight-by-eight electrical scan should not be translated
blindly into 64 physical keys per half. The remaining key work is to
validate the populated key positions against the translation tables below;
the firmware also includes positions for alternative physical layouts.

## RGB output and scan timing

The BFTM0 interrupt is right `0x347c`, left `0x3370`. It does the following:

```text
acknowledge BFTM0
clear all shared GPIOA lighting-row outputs
stop GPTM1 and reset its counter
if lighting is disabled:
    scan and debounce the entire key matrix
    return
issue the LED latch/control sequence
scan and debounce the entire key matrix
select the current lighting row on GPIOA
restart GPTM1
advance the lighting row modulo eight
shift the next row's LED channel data
```

The precise row-index update differs slightly between halves, but both
preload the next row after enabling the current one. This is why replacing
the matrix and LED code with independently scheduled drivers would be
incorrect. A port needs one timing owner for the shared pins, blanking and
row transition. The timer configuration and delay calibration are recovered
below; their nominal frequencies have not been measured on the keyboard.

| LED signal | Right | Left |
| --- | --- | --- |
| Serial data | PC12 | PC12 |
| Grayscale clock, GPTM1 CH0 | PC10, AF4 | PC10, AF4 |
| Clock | PC15 | PA14 |
| Latch/control | PB10 | PA15 |
| Disable control | PC11 high disables | PC11 high disables |
| Multiplexed row selects | PA1–PA8 | PA0–PA7 |
| Row shifter | `0x89f8` | `0x6be0` |
| Serial-bit helper | `0xc494` | `0x99dc` |
| Control-pulse helper | `0xc45c` | `0x99a8` |

This is clocked, latched, multiplexed output; it does not resemble a
WS2812 one-wire stream. The right row buffer is 512 bytes, eight rows of
32 halfwords. Its shifter processes 16 pairs per row: ten bits from one
halfword, nine from the other, then its tenth bit with a latch transition.
The left buffer is 256 bytes, eight rows of 16 halfwords, and transmits
one ten-bit value per iteration using the corresponding latch transition.
The serial helper sends the high bits of each 16-bit value first. In both
cases a normal row therefore contains 16 latch groups, with respectively
320 or 160 channel-data clock pulses. Additional control sequences occur
during initialisation and row transitions.

Right conversion `0x887c` and left conversion `0x6a8c` map RGB slots to
those channel buffers. Both use an identical 256-entry nonlinear
brightness lookup, ranging from 0 to 65535; the shifters transmit its upper
ten bits. Right lookup/mapping tables are at `0xe184`/`0xe384`, left at
`0xaca0`/`0xaea0`. The right mapping occupies eight groups of seven slots,
the left eight groups of five, with `0xff` denoting unused positions.
These are useful executable wiring maps; they do not identify the LED
driver chip or prove its current-setting limits.

## Clock, timers and electrical sequencing

The register meanings below were checked against the
[Holtek HT32F52342/52 user manual, revision 1.60](https://www.holtek.com/webapi/187531/HT32F52342_52_UserManual_v160.pdf),
chapters 6, 14 and 15. Frequencies are nominal calculations, not scope
measurements.

Startup was traced before interpreting the clock setup. Right reset
`0x32c0` first calls watchdog initialisation `0x34f0`, then `0x32dc` sets
the stack and calls `0x3394`. That is a scatter loader: its two records at
`0xf130` copy 32 bytes to `0x20000000`, then clear 9,172 bytes from
`0x20000020`. The copy/clear routines are `0xd57a`/`0xd58a`; neither
accesses peripheral registers. It then enters `0xd998`, which calls clock
initialisation `0x3624`. Left startup follows the same structure through
`0x33dc`, `0x334c`, table `0xc004`, and main `0xa8a0` → `0x3510`.
The apparent bad instruction at right `0x33b0` is a literal pool after a
call to the non-returning main routine, not an unexplored clock function.

| Configuration | Right code | Left code | Recovered setting |
| --- | --- | --- | --- |
| Oscillator/PLL setup | `0x3624` | `0x3510` | `GCFGR=0x102`: HSI PLL source; `PLLCFGR=0x03000000`: multiply 8 MHz HSI by six, output divide by one |
| Fast state | `0x379c`, argument 0 | `0x35dc`, argument 0 | Enable PLL, wait ready, set flash timing field to 2, select PLL as system clock: nominal 48 MHz |
| Slow state | Same, argument 3 | Same, argument 3 | Select HSI, wait for switch, set flash timing field to 1, disable PLL: nominal 8 MHz |
| USB oscillator trimming | `0xd298` → `0x3874(0x20)` | Corresponding USB initialisation | Enable HSI auto-trimming against USB's 1 kHz frame reference |
| Delay helper | `0x8bd0` | `0x6da4` | Measure SysTick elapsed cycles; requested units multiplied by 48 or 8, less ten cycles overhead: nominal microseconds |
| Scheduler SysTick | `0xc87c` | `0x9c84` | Fast reload `0x5db0`, slow reload `0x0f90`: approximately 0.5 ms per tick |

The application does not establish every clock register from scratch.
The startup audit found no write to `AHBCFGR` (`0x40088020`),
`APBPCSR0` (`0x40088038`) or `APBPCSR1` (`0x4008803c`). Their documented
reset values select no division, but the bootloader runs first. Thus the
code specifies a 48/8 MHz clock design while its absolute peripheral
rates additionally depend on inherited divider state. In particular,
`APBPCSR0[25:24]`, `[23:22]` and `[13:12]` select the USART0, GPTM1 and
BFTM0 divisions. Reading those registers or obtaining the bootloader
would close this specific remaining clock-state question.

BFTM0 has the same two descriptors on both halves: right `0xe10c` and
`0xe114`, left `0xac28` and `0xac30`. Their compare values are `0x9a11`
(39,441) at the fast clock and `0x19ad` (6,573) at the slow clock.
The generic initialiser, right `0x8b1c`, sets the compare register and
resets the counter. Right `0xab04`/left `0x879c` subsequently write control
`5`, enabling repetitive counting and its interrupt. The nominal interval
is approximately 822 microseconds: about 1,217 complete matrix scans per
second and 152 complete eight-row lighting cycles per second. Eight stable
debounce scans therefore take about 6.6 ms after the changed sample;
startup also performs explicit scans outside the interrupt.

GPTM1 is a fast clock generator for the LED circuitry, not the serial
data clock. Descriptor right `0xe3bc`/left `0xaec8`, decoded by right
`0xcbec`, sets:

| GPTM1 register | Offset | Value |
| --- | ---: | ---: |
| CH0 output mode | `0x40` | `7`, PWM mode 2, preload disabled |
| Channel enable | `0x50` | `1`, channel 0 enabled |
| DMA/interrupt control | `0x74` | `0` |
| Counter | `0x80` | `0` |
| Prescaler | `0x84` | `0` |
| Reload | `0x88` | `2` |
| Channel 0 compare | `0x90` | `1`, written immediately after descriptor initialisation |

PC10 uses AF4 for this output: right pin record `0xe643`, left `0xb0f5`.
With the reset up-counting mode and normal polarity, the counter repeats
0, 1, 2, producing one low and two high peripheral-clock periods per
cycle. At 48 MHz this is a nominal **16 MHz clock**, low for 20.8 ns and
high for 41.7 ns. The application leaves counter-mode/polarity registers
at their inherited state; this is another explicit reset-state dependency.
The fixed compare value does not implement the user's brightness setting:
brightness is applied to RGB channel data upstream.

At each row boundary, the interrupt clears the GPIOA row outputs, writes
GPTM1 control zero and calls right `0x8c08`/left `0x6ddc`. That helper
resets the counter to zero for up-counting, or to reload for down-counting;
**it does not wait**. The subsequent latch, scan, row-select and restart
sequence creates the blank interval. Its duration is the execution time
of those operations; there is no separately programmed blanking delay.
Key sensing similarly has no microsecond delay call: the row write is
followed by the read/helper instructions and row reset. The input template
enables pull-downs, and both the select pins and lighting-row pins use
GPIO outputs outside sensing.

LED enable is right `0x8974`, left `0x6b60`: configure the three serial
pins as outputs, delay 10,000 units, clear PC11, clear the channel buffer,
set row index zero, delay 100 units, set the startup counter to `0xff`,
shift a zero row, issue two control clocks, raise latch and start GPTM1.
Disable stops/resets GPTM1, raises PC11 and disables the serial pin
configuration. These are nominal 10 ms and 100 microsecond delays under
the clock assumptions above.

The control-clock helper lowers and raises latch, pulses the serial clock
the requested number of times, then lowers latch. Normal row boundaries
request two pulses. In the row shifter, decrementing the startup counter
to 12, 8, 4 or 0 additionally triggers the configuration sequence:

1. Issue 18 control clocks.
2. Right: send the upper ten bits of `0x0300`, then two zero bits. Left:
   send two zero bits.
3. Lower serial clock, raise latch and send the upper eight bits of
   `0x0c00`.
4. Raise serial data and toggle latch low then high.

This sends a 20-bit configuration value `0x0300c` on the right and a
10-bit value `0x00c` on the left. The four transmissions occur late in
the initial 255 row-shifter calls, not immediately when PC11 is cleared.
The stream is known; assigning meanings such as gain/current selection
to its bits still requires identifying the external LED driver.

During ordinary data output, both halves send row-buffer halfwords in
descending index order. The right latches every pair of ten-bit values;
the left latches each ten-bit value. The final bit is sent while latch is
high, with a clock rising edge, before the next iteration lowers latch.
These edge relationships, including the final data-high state, must be
preserved alongside the channel values.

## Complete key and LED lookup data

[mistel-md770-driver-data.json](mistel-md770-driver-data.json) records the
120-byte main key table, the independent left-half 64-byte table, layout
and Fn remaps, the matrix-to-RGB lookup, both LED channel mapping tables,
and all 256 intensity lookup values. Values are decimal integers with
source addresses and image hashes; this is extracted specification data,
not a firmware implementation. `0xff` means no LED slot and zero means
no base key assignment.

Right `0x5b7c` copies `0xe6d0` to the live keymap at `0x200006d0`.
The combined matrix index is `right_row*8+column`, or
`56+left_row*8+column`. Columns follow the sense-pin order above.
The default effective assignments, before user remaps, are:

| Half/row | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Right 0 | Page Down | Y | H | N | Space | Down | F12 | — |
| Right 1 | 7 | U | J | M | Right Alt | Delete | F11 | — |
| Right 2 | 8 | I | K | , | Fn | Home | F10 | — |
| Right 3 | 9 | O | L | . | Left | End | F9 | — |
| Right 4 | 0 | P | ; | / | Right Ctrl | Backslash | F8 | — |
| Right 5 | - | [ | ' | Right Shift | Up | Backspace | F7 | — |
| Right 6 | = | ] | Enter | Right | Page Up | Pn | Insert | — |
| Left 0 | Grave | Q | C | V | — | — | — | — |
| Left 1 | F6 | Tab | Z | X | — | — | — | — |
| Left 2 | F5 | 6 | G | ISO extra position | — | — | — | — |
| Left 3 | F4 | 5 | D | F | Space | — | — | — |
| Left 4 | F3 | 4 | A | S | Left Alt | — | — | — |
| Left 5 | F2 | 3 | T | Caps Lock | Left GUI | — | — | — |
| Left 6 | F1 | 2 | Left Shift | R | Left Ctrl | — | — | — |
| Left 7 | Escape | 1 | W | E | B | — | — | — |

The ISO position has usage `0x64`; its presence in the table does not
prove a switch is populated on the US PCB. The left standalone table at
`0xb270` is almost identical to the left portion above, but directly uses
Space `0x2c` and also assigns International5 `0x8b` at left row 2 column 4.
That additional alternative-layout position is also not evidence of a
populated US key.

The main table's `0xc9`, `0xca` and `0xcb` are placeholders, not ordinary
USB keyboard usages. Factory initialisation `0x4a10` loads Fn matrix index
`0x14` and Pn index `0x35` from `0xdd6e`. Right `0x6804` installs internal
Fn/Pn values `0xd8`/`0xd9`; `0x5884` tracks their press/release state rather
than sending those bytes as keys. Right `0xd5e0` turns index `0x54`, the
left Space, into usage `0x2c` for the ordinary layer. Fn relocation first
restores right index `0x14` to Right GUI `0xe7` and index `0x35` to
Application `0x65`, then installs the configured Fn/Pn positions.

The eighth right row, selected by PC1, is stored separately at
`0x20000240`. Its four low bits correspond to DIP settings, asserted when
the stored bit is zero:

| Bit / sense pin | Effect in `0x6804` |
| --- | --- |
| 0 / PA1 | Mac mode: apply 15 source→target substitutions from `0xdf44`, including F-key media functions and left/right Alt↔GUI swaps |
| 1 / PA2 | Swap left Caps Lock and left Ctrl: indices `0x63`/`0x6c` |
| 2 / PA3 | In non-Mac mode, swap left Alt and GUI: indices `0x5c`/`0x64` |
| 3 / PA4 | If bit 1 is not asserted, move Fn to Caps Lock index `0x63` and assign Caps Lock to the former right Fn position |

This records the actual conditional precedence of the supplied US 7.02
routine. In Mac mode the separate bit-2 branch is skipped because the Mac
substitution table already swaps those modifiers. In non-Mac mode bit 2
is applied independently after the bit-1/bit-3 choice. User configuration
can bypass or modify this factory path; the JSON's effective map assumes
factory Fn/Pn positions and inactive DIP switches.

Layout selector `0x5b98` starts with the base map, then applies 34 Dvorak
pairs at `0xe748`, 17 Colemak pairs at `0xe78c`, or four modifier-swap
pairs at `0xe6c8`. The JSON preserves every pair. The Fn tables at
`0xde40` and `0xde90` contain matrix indices and output words, not a
second electrical matrix. Internal outputs `0xec`–`0xfd` select bits in
the consumer report rather than keyboard-page usages; for example `0xf0`
is Play/Pause, `0xf2` Previous, `0xf3` Next, `0xf4` Mute, `0xf5` Volume
Down and `0xf6` Volume Up. This follows the consumer report descriptor at
`0xe491` and the bit-setting path in `0x56a8`.

The matrix-to-RGB table at `0xe87c` gives the colour slot for each matrix
index. Slots 0–41 belong to the data sent left; right keys map into the
remaining slots. Right buffer placement for each seven-slot hardware row
is, in halfword offsets, component 0 at `[0,2,4,6,8,10,12]`, component 1
at `[14,16,18,20,22,24,26]`, and component 2 at
`[28,30,1,3,5,7,9]`. Left placement for each five-slot row is component 0
at offsets 0–4, component 1 at 5–9, and component 2 at 10–14. Other
channel positions remain zero after buffer initialisation. This completes
the path from a physical matrix position to its serial LED data.

## Persistent settings in external SPI flash

Further inspection of the right US 7.02 application identifies an external
SPI-flash storage path. These findings come from its instructions and
callers; no storage command was sent to the keyboard. The addresses below
are MCU code addresses unless explicitly labelled as flash offsets.

| Operation | Routine | Recovered behaviour |
| --- | --- | --- |
| Initialise | `0xd478` | Initialise transport 2, send `0xab`, wait nominally 10 microseconds, read three identification bytes using `0x9f`; compare the low 16 result bits with `0x40c8` |
| Command transfer | `0xd4e4` | Submit command and reply buffers through transport 2; command lengths determine which little-endian argument bytes go on the wire |
| Read | `0x9bb8` | Send `0x03` and a three-byte, most-significant-byte-first address, then receive the requested bytes |
| Page write | `0x9b38`, `0x9ba8` | Send write-enable `0x06`, then `0x02`, a three-byte address and data; wait for completion |
| Write range | `0x9c94` | Split writes at 256-byte page boundaries |
| Sector erase | `0x9c24` | Align to a 4,096-byte sector, send write-enable and `0x20` with its address; repeat for the requested range |
| Busy poll | `0x9c68` | Read status with `0x05` until bit 0 clears, with nominal 100-microsecond delays and a bounded retry count |
| Erase and write | `0xd556` | Erase the requested range, then write it; retry failed operations |

Initialisation also sends write-enable followed by the three bytes
`01 02 00`, then waits for completion. Record that sequence when reproducing
the driver; do not assume a different part's status-register interpretation.
The identification check tests only two returned bytes. It does not
establish the capacity byte, exact part number or installed chip identity.

The settings callers establish this layout in the external flash:

| Data | Flash offset | Record bytes | Read/write callers |
| --- | --- | ---: | --- |
| Global settings, including selected profile | `0x0000` | `0xa8` (168) | `0x48a0`, `0x48f8`, `0x4b68` |
| Profile 0 | `0x1000` | `0xc3c` (3,132) | `0x48f8`, `0x4b4c` |
| Profile 1 | `0x2000` | `0xc3c` | Same |
| Profile 2 | `0x3000` | `0xc3c` | Same |
| Profile 3 | `0x4000` | `0xc3c` | Same |

Global settings use RAM `0x200014fc`; selected profile is byte 6.
The active profile record uses RAM `0x200008c0`. Factory reset `0x49b8`
iterates four profiles. Record loader `0xa764` checks the first halfword
through mask `0xf0ff`, reads the record and verifies its stored checksum.
Writer `0xa7c0` calculates that checksum using `0x3830` before calling
`0xd556`. Further callers use other flash regions for macro data, so the
table above is not a complete allocation map or permission to erase the
rest of the device.

Persistent QMK remapping therefore has an identified software route.
The copied initial data at `0xf150` places the storage descriptor at RAM
`0x2000000c`. Its first halfword is `0x4108`: eight-bit SPI master, mode 0.
Its SPI index is 1; the chip-select bytes identify PA9. Pin table `0xdf94`
selects PC2 clock, PC3 MOSI and PB6 MISO for SPI1 through AF5. These are
recovered code/data assignments, not continuity measurements.

The first QMK implementation reuses the existing SPI-flash wear-levelling
backend for external offsets `0x0000`–`0x0fff`. This replaces stock global
settings, so preserve any stock settings that must be retained before first boot. It keeps
the four profile sectors outside that allocation. The full macro-storage
allocation and a flash dump remain unavailable.
The owner uses stock defaults and accepts replacing the global-settings
sector, so preserving that sector is not a prerequisite for this unit.

Review found that QMK's `flash_erase_block()` always sent opcode `0xd8`,
even with a configured 4 KiB block. The prepared change selects `0x20`
when block and sector sizes match. Host tests check both the 4 KiB sector
command and the unchanged 64 KiB block command. Changing only the size
macro would not constrain the physical erase to the allocated sector.

## What this makes possible

The recovered information supports a first wired QMK implementation.
Builds have now been prepared in the separate `qmk_firmware` repository
on branch `mistel-md770-bt`, under `keyboards/mistel/md770rgb_bt/`.
The right default, left default and right VIA configurations compile.
This is not a hardware-validated specification or a tested port; no image
has been flashed and no device commands were sent during preparation.

A wired port can start with stock-compatible frame handling and the
recovered matrix tables, then reproduce the coordinated LED sequence.
Keeping one half on stock firmware while developing the other is now a
concrete option because both payload directions are known. It still needs
bench validation of timing, connection loss and any state-dependent UART
behaviour before relying on mixed firmware.

For the requested programmable keys and lighting alerts, QMK can own the
keymap and RGB framebuffer once these board drivers exist. Bluetooth
drivers are outside the target. The full stock macro/effect engine need
not be reproduced to provide those features. The earlier
[feasibility assessment](mistel-md770-qmk-feasibility.md) records the QMK
platform and recovery comparison; its older-image addresses are superseded
by this document for the supplied US applications.

Later physical inspection, ROM option queries and two CRC-oracle reads
establish the right controller marking, board revision, protection options
and installed IAP contents. Its watchdog-reset fallback is now reconstructed.
See the [recovery record](mistel-md770-recovery.md). Remaining unit-specific
checks include:

- Whether removed components changed relevant power or connection paths.
- SWD accessibility and bit-for-bit preservation of undocumented option metadata.
- Left-half stock restoration and first QMK hardware tests.
- Connector contact routing, actual waveforms and the LED driver's
  electrical limits.

The remaining work separates into recoverable software details and tests
of the actual unit:

| Area | What the recovered software establishes | Remaining work |
| --- | --- | --- |
| Controller | Photographed HT50F52352 in a 64-lead package; ROM model-slot value `52352` | Validate operation on hardware; the OEM marking is not a literal HT32 part marking |
| Clock/timer state | Application clock selection, divisors and timer settings; both IAPs available for startup analysis | Validate the prepared QMK clock and scan timing on hardware |
| Key positions | Matrix-to-key tables, Fn/Pn and layout remaps | Match the US key layout and test each key; alternative-layout entries do not prove physical switches exist |
| Split behaviour | UART pins, framing, checksums, payloads, scheduling and PB8 mode selection | Implement the recovered behaviour and test connection loss/reconnection; physical contact routing and waveforms remain unmeasured |
| Persistent settings | SPI1 pin/mode assignments, external flash commands, global record and four profile sectors | Validate the prepared QMK backend on hardware after preserving the stock flash; broader stock macro allocation remains to be mapped |
| Recovery | Right SEL2 and left SEL4 ROM entry; two matching IAP backups per half; both boot policies decoded; right stock restoration verified | Validate left stock restoration before calling its complete restore path tested |

### First port preparation and review

This section records the initial 2026-11-12 implementation and binaries.
The subsequent [upstream refinement](qmk-upstream-readiness.md) supersedes
its keymap and notification details: DIP/Fn/Pn compatibility is now
implemented, and the custom notification protocol has been removed.

The separate `qmk_firmware` checkout contains the development port on
branch `mistel-md770-bt`. Its `keyboards/mistel/md770rgb_bt/readme.md`
records build commands, the notification protocol and current limitations.
Default images exist for both halves; a right-half build flag enables VIA.
The default keymap targets the 85-key US layout and lighting defaults off.
Bluetooth, stock macros and DIP remapping remain outside this port.

The implementation reuses QMK's serial, timer, debounce, RGB Matrix, VIA
and SPI-flash wear-levelling components. Custom code coordinates the
shared scan/lighting pins and implements the recovered split framing.
The left receives colour snapshots approximately every 32 ms, so its
alert edges have that resolution; very short phases may disappear.

Astra reviewed the implementation at maximum reasoning effort. Review
corrected the erase opcode, pre-debounce split transmission, inherited
watchdog servicing, clock handover, per-row discharge, suspended alert
expiry and interrupt priorities. It independently matched both channel
maps, all 256 brightness values and all 85 matrix-to-LED mappings against
the supplied binaries, together with shifter edges and SPI assignments.
The final static-code review found no remaining blockers; that finding
does not establish hardware operation or bootloader acceptance.

QMK's pinned platform declares eight interrupt-priority bits. Holtek's
[CMSIS device header](https://github.com/RT-Thread/rt-thread/blob/master/bsp/ht32/libraries/HT32_STD_5xxxx_FWLib/library/Device/Holtek/HT32F5xxxx/Include/ht32f5xxxx_01.h)
declares two for this part, contradicting the manual's four-bit statement.
The board encodes priorities into the upper two bits so USB and UART can
pre-empt RGB scanning with either physical interpretation. This workaround
can be removed after the platform declarations and defaults are corrected
together. The separate reset-controller correction is retained as a
reproducible patch pending its own ChibiOS-Contrib upstream fix.

Validation includes three successful firmware configurations, eleven
host-side tests, both halves' strict QMK lint and C/C++ formatting checks.
The linker asserts the vector base, compatibility-record location and
reserved SRAM boundary. Recovery verification, actual key/lighting tests,
split disconnect/reconnect tests and persistent-write tests remain pending.

Final prepared binaries in `qmk_firmware`, checked on 2026-11-12:

| Output | File bytes | SHA-256 |
| --- | ---: | --- |
| `mistel_md770rgb_bt_right_default.bin` | 29,052 | `d96c35da650da83262450330b844c127fe8cb72796daa2673bd54944b618ddef` |
| `mistel_md770rgb_bt_left_default.bin` | 26,400 | `1f4ffaae6eb10e0ae569f695fef38ab22de0daa88c2a2034990008b33129f950` |
| `mistel_md770rgb_bt_right_via.bin` | 31,900 | `a25826ff7bc863b00d38f4902fb12b466853984421396786b806182c17aa7de1` |

Binary checks confirm the correct half-specific compatibility records,
Thumb reset vectors, vector base and reserved RAM boundary. The QMK
initial stack pointer is `0x20000400`, using ChibiOS's allocated interrupt
stack; the stock application's initial pointer is `0x20003fe0`. Bootloader
acceptance of the prepared images has not been tested.

Follow-up manual review corrected the upper application-flash boundary to
`0x1fe00`. The final 512-byte main-flash page holds option bytes and is
excluded from both the linker region and board `FLASH_SIZE`. Available
application space from `0x3200` is therefore 117,760 bytes, or **115 KiB**.
Astra reviewed the correction; all three rebuilt images retain the hashes
above and pass the corrected boundary checks. The earlier 115.5 KiB figure
included the reserved option page.

These are not five additional prerequisites for writing a first port.
The recovered behaviour supports implementation of the wired keyboard,
RGB alerts and persistent settings. Recovery remains the prerequisite for
flashing; subsequent hardware tests establish whether the implementation
works on this unit. The known QMK platform reset-register error also needs
correcting; see the [prior-art findings](mistel-md770-prior-art.md).

The current vendor package resolves the earlier absence of a matching
application release. It does not by itself provide a complete recovery
image. Before flashing, establish a way back to IAP independent of a
working application and obtain a recoverable bootloader/flash backup where
protection permits. The application boot request is visible at right
`0x87c4`: it writes `0x55aafaf5` to `0x20003ffc` before reset. That proves
the request mechanism, not a recovery path for a broken application.

The most useful next hardware work is a passive capture of PB0/PB1 and
the LED clock/latch/row lines, plus chip markings and accessible SWD/reset
pads. It validates specific recovered behaviour rather than searching for
the architecture from scratch. No programmer connection, protection
change or firmware write was performed for this reconstruction.

## Reproducing the extraction and decompilation

The extractor and Ghidra scripts are in this repository. Extraction never
executes the Windows updaters. Generated images and pseudocode are local
analysis outputs; keep them out of commits. From the repository root in fish:

```fish
set PACKAGE "$HOME/Downloads/MD770 RGB BT v1.07.02"
set ANALYSIS "$PWD/md770-analysis"
mkdir -p "$ANALYSIS/images" "$ANALYSIS/projects" "$ANALYSIS/c"
python3 scripts/md770-extract.py "$PACKAGE/Right(Master)/MD770R_FW_0419_7.02_20230421.exe" "$ANALYSIS/images"
python3 scripts/md770-extract.py "$PACKAGE/Left(Slave)/MD770L_FW_041A_4.01_20230424.exe" "$ANALYSIS/images"
```

Each extraction writes version templates, applications and a manifest with
layout names, sizes and SHA-256 hashes. Compare the US image hashes with
the table above before using the addresses in this document.

Ghidra 12.0.4 was used with the ARM Cortex language and base address
`0x3200`. For the right US image:

```fish
nix shell nixpkgs#ghidra --command ghidra-analyzeHeadless \
  "$ANALYSIS/projects" md770-right \
  -import "$ANALYSIS/images/MD770R_FW_0419_7.02_20230421.g4e8.firmware.bin" \
  -loader BinaryLoader -loader-baseAddr 0x3200 \
  -processor ARM:LE:32:Cortex -cspec default \
  -scriptPath "$PWD/scripts/md770-ghidra" \
  -preScript PrepareMd770.java \
  -postScript SeedFunctions.java 0x5d08 0x5d1c \
  -postScript ExportMd770.java "$ANALYSIS/c"
```

For the left US image, use project name `md770-left`, import
`MD770L_FW_041A_4.01_20230424.g3e8.firmware.bin`, and seed callbacks
`0x5318 0x532c`. The preparation script maps SRAM and volatile peripheral
regions, marks the application read-only, and seeds Thumb vector handlers.
The extra seeds recover functions reached through callback tables.

The checked runs exported 403 right-half functions and 293 left-half
functions without script errors. The right export still reports an
unresolved instruction while decompiling `0x3394`; its pseudocode must not
be treated as a complete or buildable replacement source tree. The recovered
driver behaviour above was checked against disassembly and data tables.
