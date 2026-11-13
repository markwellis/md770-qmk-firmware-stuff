# Mistel MD770BT-M recovery investigation

Investigated on 2026-11-12. The subsequent right-half stock restore
passed on 2026-11-13; its [record and logs](mistel-md770-stock-restore.json)
document the erase, write, full readback, protection restoration and normal boot.
Initial queries read the running right
application. The owner later verified SEL2's BOOT/VSS connections and
entered the independent ROM loader at power-on. Subsequent USB queries
read identification, option data and CRCs. Two fresh ROM sessions produced
byte-identical right-half stock-IAP backups. A later stock-updater check
used its software entry/return resets and verified application checksums.
Those initial queries performed no flash write, erase or protection change.

**Right-half stock restoration is verified on this unit. Left-half ROM entry
and two matching IAP backups are also verified; left stock restoration
remains untested.** See the [left investigation](left-recovery-investigation.md).
The ROM
queries returned coherent option data with read security and option-byte
protection enabled. The verified right-IAP backup is kept outside this repository as `red_right_MD770R_IAP_0419_stock_20261112.bin`.

The [verified procedure](right-recovery-package.md) uses the saved stock
IAP after mass erase. Keep the measured SEL2 bridge secure through reset;
the test needed cold ROM re-entry after its first bridge contact failed.

## Information obtained without changing device state

[mistel-md770-live-info.json](mistel-md770-live-info.json) records the
replies, including the full 480-byte version-page read. The right half is
running V1.07.02 in application mode. Its USB device revision `0710`
matches the supplied **US** application; the EU and JP descriptors use
`0720` and `0730` respectively. The decoded version template matches the
first 180 live version-page bytes exactly.

The supplied `maaV105` version template already has its final device
format. Do not apply the older `maaV102` template conversion described in
the MK Typist research: moving byte `0xae` to `0xb2` would corrupt this
template's magic word.

The live information block, read from MCU address `0x400`, identifies:

| Field | Value |
| --- | --- |
| Stock IAP USB identity | `04d9:1419` |
| Application signature | `0x040450c0` |
| Application offset within update area | `0x200` |
| Update pages | `0xe7`, or 231 |
| Page size | `0x200`, or 512 bytes |
| Model text | `KB0419` |
| Application header at `0x3c00` | `0x00020004` |

Both supplied updater executables end their PE sections at file offset
`0x1f1600`. Their declared application/version payloads start at exactly
that offset and account for the entire appended data before the `maaV105`
trailer. The PE resources are UI assets: BMP/JPG/XML, cursors, bitmaps,
icons, dialogs, strings, group cursors/icons, version and manifest data.
No separate stock-IAP image was identified.

## Offline application-checksum candidates

The related CYKB protocol returns the sum and CRC32 of the encoded
application through `1d 01` and `1d 02`, with relative offset `0x200`.
Applying its 52-byte XOR stream to the decoded US images gives:

| Image | Bytes | Encoded little-endian word sum | Encoded CRC32 |
| --- | ---: | --- | --- |
| Right US 7.02 | 49,008 | `0x0e685d2a` | `0x6785727c` |
| Left US 4.01 | 36,404 | `0x2a82d590` | `0x90309827` |

The right-half values now match the observed stock-IAP replies in the
[updater check](mistel-md770-updater-check.json). The left-half values
now match the [left-half updater check](mistel-md770-left-updater-check.json).
See the [left recovery investigation](left-recovery-investigation.md) for
its measured software behaviour and remaining physical recovery checks.

## Three distinct entry and recovery mechanisms

### Running application's IAP request

Right handler `0x86e4` dispatches command `11 00` to `0x87c4`. It writes
`0x55aafaf5` to SRAM `0x20003ffc`, prepares USB shutdown and requests a
system reset through AIRCR. Command `11 01` uses `0x55aafaf0` instead.

The [stock-updater check](mistel-md770-updater-check.json) exercised this
entry and the `11 01` return on the same USB port. The IAP identified as
`04d9:1419`; encoded sum `0x0e685d2a` and CRC32 `0x6785727c` matched the
official US 7.02 application. Normal `04d9:0419` operation returned.
This mechanism still requires a working application to request entry.

### Stock IAP's reset policy

The recovered right IAP now establishes this policy directly. Main
routine `0x1dd8` reads SRAM `0x20003ffc` and reset status `0x40088100`:

- Values outside `0x55aafaf0` through `0x55aafaf5` become `0x55aafaf0`.
- A value below `0x55aafaf5` increments when watchdog-reset bit 2 is set.
- At `0x55aafaf5`, the IAP remains in its resident USB updater.
- Otherwise, passing application checks lead to the jump at `0x1e56`.

Five qualifying watchdog resets from `0x55aafaf0` therefore reach the
updater if the application does not clear or decrement the counter.
Application `0xd998` checks this state at startup; normal stock execution
decrements it. Ordinary power cycles are not a five-reset recovery recipe.
A broken application that keeps servicing the watchdog can also avoid
this fallback. No GPIO or key check appears in the IAP's boot decision.

The IAP clears reset flags at `0x1e5a`, after the possible application
jump, on the resident-updater path. The same routine checks the initial
application stack pointer in `0x20000000`–`0x20004000`, reset vector in
`0x3200`–`0x1fdff`, signature `0x040450c0` at `0x3bf8` and version-page
validity before that jump. The IAP's own initial stack is `0x20001fe0`;
its retained boot-request word is still at the top of 16 KiB SRAM.

These are static findings from the exact saved right-half image, not a
hardware test of watchdog recovery or a finding about the left IAP.

### Holtek's independent ROM loader

The [Holtek user manual, Table 6 and FMC security section](https://www.holtek.com/webapi/187531/HT32F52342_52_UserManual_v160.pdf)
specifies that BOOT low at reset selects the independent loader, while
BOOT high selects main flash. The [datasheet](https://www.holtek.com.tw/webapi/11842/HT32F52342_52_Datasheetv160.pdf)
identifies PA9 as BOOT and provides USB and USART communication in loader
mode. This route does not depend on QMK or the stock application working.

For the indicated 64-pin HT32F52352 package, the documented physical pins
are PA9/BOOT 35, nRST 20, PA12/SWCLK 38 and PA13/SWDIO 39. These are MCU
pin numbers, not identified MD770 test-pad numbers. Confirm the actual
marking/package and continuity before using them.

[ht32-dfu-tool](https://github.com/hansemro/ht32-dfu-tool) implements
read-only ROM-loader device identification, protection queries and flash
readback for this family. Its usual ROM USB identity is `04d9:8010`,
distinct from the MD770's stock IAP identity. The observed ROM session
below records this tool's identification and option-area queries.

## Why the remaining state cannot be read through the identified app API

The right application's low-level USB reader at `0x86e4` exposes only:

| Request | Returned memory |
| --- | --- |
| `12 00` | 52 bytes at `0x400` |
| `12 01` | Four bytes at `0x3c00` |
| `12 02` | Application-mode byte |
| `12 20` through `12 27` | Eight 60-byte slices starting at `0x3000` |

The higher-level read commands examined operate on bounded key, profile,
effect and RGB structures. No general address-based flash or register
reader was identified in the unmodified application. In particular, the
stock application does not expose the IAP's checksum command or return
the FMC protection registers through the reader above.

The MCU manual locates read-only security status at FMC CPSR
`0x40080030`: bit 0 clear means flash security enabled; bit 1 clear means
option-byte protection enabled. Page-protection status occupies
`0x40080020` through `0x4008002f`; manufacturer/device ID is at
`0x40080180`. These are specific query targets, not values observed on
this unit. With security enabled, debug flash reads return zero and
unlocking requires mass erase. A successful transfer of zeros is not a
valid bootloader backup.

The related [Typist backup method](https://github.com/jpsutton/mk-typist-research/blob/main/docs/flashing-and-recovery.md)
adds an address-based reader to a matching stock application, then flashes
that application before dumping. It is a possible later route if protection
blocks ordinary reads. It is not a read-only preliminary backup and has
not been prepared or executed here.

### Software-only backup design for this release

The corresponding MD770 US 7.02 instruction span has been identified and
its proposed replacement disassembled in memory. No patched image was
created. At application offset `0x552c`, MCU address `0x872c`:

```text
original: 20 28 0e d3 01 46 1f 39 3c 22
candidate: ff 28 0e d1 68 68 3c 21 15 e0

0x872c  cmp  r0, #0xff
0x872e  bne  0x874e
0x8730  ldr  r0, [r5, #4]
0x8732  movs r1, #60
0x8734  b    0x8762
```

For command `12 ff`, this would take a read address from request bytes
4–7 and reuse the existing 60-byte HID reply routine. Other subcommands
would use the existing 0/1/2 checks; the normal version-page subcommands
would no longer work. The source image must match SHA-256
`8fafdca096756f23626802d5b586b270b0bd512fe5d1c0327db4eafcd4f689b2`.
These offsets do not apply to EU, JP or other firmware releases.

A later diagnostic session could use that reader for the installed stock
IAP, option/protection status and inherited clock/timer registers, then
restore the unmodified application. First verify independent physical
recovery, stock-IAP entry/return and the installed application's checksum
against the source image. Do not
assume that the related tool's checksum rules or write limits have been
verified on this MD770 merely because the container decodes correctly.

This route can avoid opening the case, but requires a temporary firmware
write before obtaining all the missing information. It is therefore
outside the current information-before-changes stage. It also cannot
demonstrate physical ROM-loader entry if both USB and the stock IAP fail.

The [prior-art investigation](mistel-md770-prior-art.md) found no published
MD770 bootloader dump or verified BOOT-pad map. The close TEX port's memory
reader also requires diagnostic firmware. It did expose a real reset-base
error in QMK's pinned platform dependency; record and address that during
any later port rather than mistaking the resulting USB failure for an
MD770 pin-map problem.

## Checks before a first flash

1. **Done:** verify BOOT and ground on this unit. SEL2 connects MCU lead
   35 to VSS lead 19; USB power-on provides the reset for ROM entry.
2. **Done:** enter ROM and read coherent identification/option data without
   programming. The observed option data enables read security and
   option-byte protection. Live FMC status registers remain unread.
3. **Done:** two fresh CRC-oracle passes produced byte-identical stock-IAP
   backups. The later stock-restore test completed mass erase, cold ROM
   re-entry, full image writing/readback and documented option restoration.
4. **Done:** stock-IAP entry/return and application sum/CRC comparison
   passed. The keyboard returned to normal USB operation and typing.
5. **Not required for this unit:** the owner uses defaults and accepts
   replacing the stock global-settings sector with QMK settings. A
   settings backup is unnecessary; see the [storage layout](mistel-md770-firmware.md#persistent-settings-in-external-spi-flash).

The right-half recovery prerequisite is now satisfied. The QMK port still
needs hardware validation. The implementation specification is in
[mistel-md770-firmware.md](mistel-md770-firmware.md).

## Right-half photographs and unpowered measurements

The owner opened the right half on 2026-11-12. Local JPEG evidence copies
preserve the supplied HEIC photographs outside their original temporary
location. The owner subsequently completed the BOOT/VSS continuity checks
and entered ROM mode, as recorded below.

| Evidence | Observed marking or feature | Original photo |
| --- | --- | --- |
| [Whole PCB](mistel-md770-photos/right-pcb.jpg) | `MD770BR-RIGHT`, revision `V06 1223BJ`; CN2 and SEL2 visible | `IMG20261112210534.heic` |
| [Controller](mistel-md770-photos/controller.jpg) | `HOLTEK HT50F52352`, ARM marking, 64 leads | `IMG20261112210731.heic` |
| [LED drivers](mistel-md770-photos/led-drivers.jpg) | Both packages marked `MBIA043GP` | `IMG20261112210735.heic` |
| [CN2 and SEL2](mistel-md770-photos/cn2-sel2.jpg) | Five CN2 pads, two SEL2 pads; square pad at the left end of each in this photograph | `IMG20261112211011.heic` |

The controller marking matches the OEM-marked part expected from related
HT32 research. It is not literally marked HT32F52352; the functional
equivalence is supported by the register map, firmware, related boards
and the later ROM model-slot value. The smaller eight-pin storage chip's
full marking remains unreadable in the overview.

Newly located primary [Tab75 notes](https://raw.githubusercontent.com/wiki/ephb/pok3r_re_firmware/Tab75-Notes.md)
describe another board with HT50F52352, GD25Q40 and MBIA043. They list
CN2 as 3.3 V, SWDIO, SWCLK, nRST and GND from pin 1 to 5. They list
SEL2 pin 1 as BOOT1 explicitly **unconfirmed**, and pin 2 as GND.
That PCB is `KA01E63122H010-AH0820 V05`, not this MD770. Shared names and
chips supply a continuity-test hypothesis, not a verified MD770 pinout.

Astra independently reviewed the photographs and initial measurement plan
at maximum reasoning effort. First disconnect the computer USB cable and
the inter-half cable; the Bluetooth hardware and batteries were already
removed. Note the meter's resistance with its probes touched together.
Then measure between CN2's far round end and SEL2's round pad: both are
the right-hand end in the close-up above. A steady reading near the probe
baseline establishes that they share a net. It does not alone prove GND.
A brief continuity beep through a capacitor is not the same evidence.

The owner reports continuity between CN2's far round end, SEL2's round
pad and the USB shell. Follow-up measurements give steady continuity
between SEL2's square pad and MCU lead 35 (PA9/BOOT), and between SEL2's
round pad and MCU lead 19 (VSS). These establish this unit's accessible
BOOT-to-ground jumper under the identified package pinout. No numeric
resistance was supplied. These measurements preceded powered ROM entry;
CN2's signal-pad assignments remain unmeasured.

For later continuity checks, the MCU photo and the Holtek 64-pin drawing
agree on orientation: with HOLTEK upright, the board's pin-1 dot is at
the lower-left and lead 1 is the leftmost lead of the bottom edge.
Conditional targets under the OEM-equivalence hypothesis are:

| Signal | MCU lead | Position with HOLTEK upright |
| --- | ---: | --- |
| VSS | 19 | Right edge, third from bottom |
| nRST | 20 | Right edge, fourth from bottom |
| PA9/BOOT | 35 | Top edge, third from right |
| PA12/SWCLK | 38 | Top edge, sixth from right |
| PA13/SWDIO | 39 | Top edge, seventh from right |

The owner has measured the SEL2 BOOT and VSS targets above. The other
targets still require measurements. The later ROM session establishes
entry and reads option data. The Tab75 map alone does not establish
CN2's pinout.

## Prepared ROM-entry check

`ht32-dfu-tool` 0.2.2, revision
`848fc071c8f2429bf41f3bd40c60ec9bc5433b72`, was built from its locked
dependencies. Its version/help and USB-list initialisation passed. At
that preparation stage no ROM device was present and no keyboard query,
reset or flash operation ran.

Astra reviewed the proposed entry and command at maximum reasoning effort.
The initial check uses the same computer-facing USB socket/cable as normal
operation, with the inter-half cable disconnected. With USB absent, bridge
only the two measured SEL2 pads. Connect USB while holding that bridge
across the power-on reset. BOOT is latched at reset, so remove the bridge
before querying; it need not remain attached. Expected ROM identity is
`04d9:8010`. If the normal application/IAP appears, or enumeration fails,
unplug before adjusting the bridge. PA9 also serves as stock SPI chip
select, so do not reapply the jumper to a running application.

Plain `ht32-dfu-tool info`, with no VID/PID override or reset flag, sends
only identification command `03 00` and a 64-byte option-area read
`01 02` from `0x1ff00000`. No write, erase, unlock, protection change or
reset path is reached. Interface claiming can temporarily detach the
kernel driver. Return to normal operation by unplugging USB, leaving SEL2
open, waiting a few seconds and reconnecting; verify `04d9:0419` and typing.

The unmodified client's printed protection flags require validation. It does not check
transfer lengths, reply status, the option checksum or live FMC CPSR.
All-zero replies can represent blocked or invalid reads. The manual's
option checksum is at alias offset `0x20`; when non-erased protection
words exist it must equal their five-word sum. Invalid option data can
force protection irrespective of the raw bits. A ROM query alone does
not establish a valid flash backup or complete stock restoration path.

## Observed ROM session

After the owner held the measured SEL2 BOOT pad to its measured VSS pad
at USB power-on, the Linux host enumerated **`04d9:8010`**, bus 3 device 14. The
bridge was removed before the queries. This establishes actual independent
ROM entry through this unit's normal host USB port.

[mistel-md770-rom-info.json](mistel-md770-rom-info.json) preserves both raw
64-byte replies and their interpretation. The unmodified client's `info`
command succeeded. A host-only [diagnostic patch](../scripts/md770-rom-info.patch)
then logged both replies and rejected short transfers; the repeated query
still sent only `03 00` and `01 02` to the option alias. Both transfers
sent and received exactly 64 bytes.

| Field | Observed value |
| --- | --- |
| ROM version | `0x0103` |
| Page size | 512 bytes |
| Usable main-flash pages | 255 |
| Usable main flash | 130,560 bytes, excluding the final 512-byte option page |
| Info model-slot word at offset `0x10` | `0x00052352` |
| `OB_PP[31:0]` | `0xfffff000` |
| Remaining three protection words | `0xffffffff` each |
| `OB_CP` | `0xfffffffc` |
| Stored option checksum at offset `0x20` | `0xffffeff9` |
| Sum of the first five option words modulo 2^32 | `0xffffeff9`, valid |

The original tool prints model `unknown` because it recognises only ROM
versions `0x0100` and `0x0101`. The observed `52352` model-slot value
supports the HT32F52352 interpretation of the photographed HT50F52352;
the v1.03 field layout has not been independently documented.

The validated option data enables flash read security and option-byte
protection. On this part each protection bit covers two 512-byte pages;
the first twelve cleared bits protect `0x0000`–`0x2fff`, matching the
stock IAP region. This is coherent option data, not an all-zero failed
read. Live CPSR/PPSR registers were not queried.

Holtek's [AN0628EN, pages 6–8](https://www.holtek.com.tw/webapi/116745/an0628en.pdf)
explicitly permits reading the first 80 option bytes through the ISP loader
under security protection, while denying main-flash reads. This supports
the observed option reply without implying that a stock-IAP dump is available.

The [Holtek manual, security table on page 50](https://www.holtek.com/webapi/187531/HT32F52342_52_UserManual_v160.pdf)
permits ordinary protected-mode main-flash access to software executing or
booted from main flash with SWD disconnected. It does not establish a
selective ROM-based application restore under active security. Clearing
security requires mass erase, which would remove the stock IAP. No erase,
unlock, write, application-flash dump, peripheral-register read or reset
command was attempted.

Astra independently checked the replies, checksum, two-pages-per-bit
interpretation and host diagnostic patch at maximum reasoning effort.
The meaning of ROM command `04 01` for this vendor's stock-IAP entry
was unresolved in this initial session; it was not sent then. The later
[stock restore](mistel-md770-stock-restore.json) records its actual reset
attempt, interrupted SEL2 contact and successful cold-entry continuation.

After unplugging USB and reconnecting with SEL2 unbridged, the device
returned as **`04d9:0419`**, product `MD770BT-M`, bus 3 device 15. This
verifies return to the normal USB identity. The owner confirmed typing
from the right half. No software reset command was used.

## Read-only CRC bootloader backup

Further primary-source research found a protected-flash
[demonstration by Hansem Ro](https://asciinema.org/a/9JlWn2M2NsOHoi5lTpsas8eWS)
on HT32F1654 ROM v1.00. The [author's explanation](https://github.com/pok3r-custom/pok3rtool/issues/12#issuecomment-1327965232)
says ordinary reads obey security while another ISP feature permits extraction.
The demonstration does not disclose the extraction algorithm or establish
that this unit's ROM v1.03 behaves the same way.

The author's [published protocol client](https://gist.githubusercontent.com/hansemro/76493b59cbade75309dde1fdbe1b103b/raw/4fd0bd3504054077251d8a2489f17261caf9680a/holtek_isp.py)
provides a read-only CRC request: `02 00`, start address and byte length.
A HID `GET_REPORT` returns the CRC16 in little-endian order followed by
status `4f`. The request packet uses CRC16-XMODEM. The flash CRC's
algorithm and accessibility under this unit's protection require calibration.
Drain status after every command; the author's
[transport notes](https://github.com/pok3r-custom/pok3rtool/issues/12#issuecomment-1315251695)
report a reboot when the finite status queue overflows.

[md770-rom-crc.rs](../tools/ht32-dfu-tool/src/bin/md770-rom-crc.rs) is a bounded calibration
probe. Build it as an additional binary in the pinned `ht32-dfu-tool`
checkout, using that project's existing locked dependencies. It sends
only `02 00` and `GET_REPORT`, accepts one matching ROM device and has
no firmware-write, erase, unlock or reset path. It rejects malformed or
unexpected status and aborts on the first CRC mismatch.

The nine samples start with known live information at `0x408` and version
bytes at `0x3000`, then compare application windows with the decoded US
7.02 image. The last sample, `0x3202` with length four, checks two-byte
address alignment. Actual reply lengths are preserved; empty replies
mean pending, while a CRC record requires at least three received bytes.

[The calibration record](mistel-md770-crc-calibration.json) shows that all
nine protected-flash CRCs matched the known bytes, including `0x3202`.
This ROM stalls an empty `GET_REPORT` with USB `PIPE`, then returns a
64-byte CRC status after each `02 00` request. The probe therefore treats
`PIPE` as empty only before a command and keeps post-command errors fatal.
No firmware write, erase, unlock, protection change or reset was performed.

Four-byte CRC windows recover two unknown bytes beside two known bytes.
An offline CRC16-XMODEM inversion check
uniquely recovered all 65,536 two-byte prefixes for four different known
suffixes. The live calibration and two complete reads establish this
method's behaviour on this unit's ROM v1.03.

The [IAP backup record](mistel-md770-iap-backup.json) records two complete
passes from fresh ROM sessions. Each reconstructed 12,288 bytes with 6,118
CRC queries. All 24 separately requested 512-byte page CRCs and the
whole-region CRC matched on each pass. The 52-byte information block was
seeded from the earlier direct live read, so comparing it with that seed
is a consistency check. All queried lengths contain an even number of
two-byte words. Astra independently showed that a propagated seed error
can cancel in these CRCs, so the correct separately read anchor remains
a prerequisite. Page and whole-region CRCs do not independently prove it.
The whole-region CRC is also redundant with the page CRCs. The recovered
vectors and code are plausible Cortex-M values. The
passes are byte-identical with SHA-256
`61e377ee21584a7bce42a2a9532a40b6682ba9d1a095cfe08708555ab7e5bd4e`.

The owner preserved the verified binary at
`red_right_MD770R_IAP_0419_stock_20261112.bin`.
Its backup hash and bytes match both reads. The initial copy remains inside
the supplied `MD770 RGB BT v1.07.02` package as
`Right(Master)/MD770R_IAP_0419_stock_20261112.bin`. No binary is stored
in this source repository. The full restoration procedure subsequently
passed the hardware test recorded below.

The later [read-only preflight](mistel-md770-rom-preflight.json) passed
all 37 checks, including 25 overlapping four-byte windows through the
anchor and three six-byte checks. These address the demonstrated seed
ambiguity. The corrected restore utility also successfully queried this
ROM's identity/protection data and consumed their acknowledgements.
The keyboard then returned to normal USB operation and typing.

The [prepared recovery package](right-recovery-package.md) contains a
130,560-byte reconstructed stock image. Its independent image hash is
`8d961215101b93760d20dfbc717f6cd6a2fa879fae26e71a478089df39095ffd`.
The option page is excluded. The subsequent [stock-restore test](mistel-md770-stock-restore.json)
verified the written image, documented protection words, cold boot,
typing and the restored updater's checksum/return operation.

The `red_right` name identifies the owner's red-switch keyboard and right
half. A second MD770 has brown switches. Switch type alone does not
establish identical PCB revisions or bootloader contents; the second unit
has not been backed up. This unit's left half was subsequently backed up
in [two fresh ROM sessions](mistel-md770-left-iap-backup.json).

Astra's final maximum-effort review found no blocking defect in the reader.
It independently reproduced the reconstruction, checked all backup copies
and confirmed the IAP's boot policy and application bounds. Correctness
depends on the separately read anchor and CRC replies. Full main-image
restoration is now verified; undocumented option metadata is not preserved
bit for bit.

## Left-half photographs

The left half was opened on 2026-11-13. The JPEG copies have source
metadata stripped. These photographs do not establish recovery-pad wiring
or a tested recovery procedure for the left half.

| Evidence | Original photo |
| --- | --- |
| [Whole PCB](mistel-md770-photos/left-pcb.jpg) | `IMG20261113092302.heic` |
| [Controller](mistel-md770-photos/left-controller.jpg) | `IMG20261113092235.heic` |
| [LED driver](mistel-md770-photos/left-led-driver.jpg) | `IMG20261113092246.heic` |

## Removed Bluetooth carrier

The owner supplied further photographs for completeness. Astra independently
checked the visible markings. The radio chip remains under its shield;
no radio-chip model or pad functions are established by these photos.

| Evidence | Observation | Original photo |
| --- | --- | --- |
| [Carrier front](mistel-md770-photos/bt-front.jpg) | `MD770 BT Module PCB V09 0926A1`, `KA01E80122H010` | `IMG20261112213142.heic` |
| [Carrier back](mistel-md770-photos/bt-back.jpg) | TP-labelled pads, `GF-01 94V-0`, `E246338`, RoHS | `IMG20261112213148.heic` |
| [Shielded module](mistel-md770-photos/bt-shield.jpg) | Exposed green PCB markings `2035`, `ND207`, `94V-0`; no visible radio IC marking | `IMG20261112213155.heic` |

Do not identify the radio or assign a confirmed date from those manufacturing
markings. These photographs do not change the wired-only implementation scope.
