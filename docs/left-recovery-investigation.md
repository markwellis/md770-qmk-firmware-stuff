# Left-half recovery investigation

QMK has not been flashed. This investigation concerns the photographed
left half; right-half recovery results do not establish left-half recovery.

## Identification

The [controller photograph](mistel-md770-photos/left-controller.jpg) shows
the OEM marking `HOLTEK HT50F52352`. The overview shows revision
`V06 1223BJ`, a five-pad header labelled CN4 and two pairs labelled SEL3
and SEL4. SEL4's BOOT connection is measured below; SEL3's signal remains
unassigned.

With only the left half connected and no pads bridged, the stock
application enumerates as `04d9:041a`, product `MD770BT-S`, USB revision
`0410`. The [live identification](mistel-md770-left-live-info.json) records
the directly read 52-byte information block, application header and mode.

| Field | Value |
| --- | --- |
| Stock IAP identity reported by the application | `04d9:141a` |
| Application signature | `0x04046080` |
| Model text | `KB041A` |
| Application header | `0x00020004` |
| Update-area application offset | `0x200` |
| Update pages and page size | `0xe7` pages of `0x200` bytes |

## Software entry

The supplied left US 4.01 application is 36,404 bytes, SHA-256
`febc84d9dc1fd23152218232839279ecb59f255615a6d6c5b4d951a848c85064`.
Its command dispatcher at `0x68f4` passes `11` commands to `0x69d4`.
Subcommand 0 writes `0x55aafaf5` to `0x20003ffc`; subcommand 1 writes
`0x55aafaf0`. Both shut down USB and request a system reset through AIRCR.
This establishes the application's updater request, not the IAP's policy
or an independent recovery route.

For the encoded supplied image, the offline word sum is `0x2a82d590` and
CRC32 is `0x90309827`. The diagnostic checker accepts `--half left`, checks
the exact image hash and left information-block identity before entry,
and attempts return to the same physical USB port even after check failures.
Its allowed commands exclude flash erase, programming and protection changes.

The [live updater check](mistel-md770-left-updater-check.json) passed on
2026-11-13. It entered `04d9:141a`, matched the information block and both
application checksums, then returned to `04d9:041a` application mode on
the same physical USB port. No flash erase, write or protection change
was sent. This confirms the installed US 4.01 application and software
updater entry/return; it does not establish independent ROM recovery.

## Independent recovery still to establish

The [Holtek datasheet](https://www.holtek.com.tw/webapi/11842/HT32F52342_52_Datasheetv160.pdf)
identifies PA9/BOOT as lead 35 and VSS as lead 19 for the equivalent
64-pin package. The subsequent continuity measurements establish the
SEL4 connections on this PCB.

The owner reports steady continuity from both round SEL3/SEL4 pads to
the USB shell and to each other. These are the pads nearest the USB ports.
The square pads are farther from the ports. No resistance value was
reported. The owner retracted the subsequent MCU-pin readings after
finding that the chip had been viewed upside down. Those readings do not
establish connections to PA9/BOOT, VSS or PA2. Chip-pin continuity checks
were repeated with the HOLTEK lettering upright as recorded below.

After restarting with HOLTEK upright and all cables unplugged, the owner
confirmed steady continuity from SEL3's round pad to MCU lead 19, VSS
(right edge, third lead from the bottom). Together with the previously
reported continuity between both round pads, this establishes their
common MCU-ground connection.

With the same corrected orientation, the owner reports no continuity
from SEL3's square pad to lead 35, but steady continuity from SEL4's
square pad to lead 35, PA9/BOOT. SEL4 therefore provides the measured
BOOT-to-ground pair. Its round pad is nearer the USB ports and its square
pad farther away. This establishes pad wiring, not successful ROM entry.

With HOLTEK upright in the controller photograph, lead 35 is the third
lead from the right along the top edge; lead 19 is the third from the
bottom along the right edge. SEL3's square-pad function and the CN4
pinout remain unverified.

For the initial ROM-entry test, disconnect all USB and inter-half cables.
Bridge only SEL4's measured BOOT/GND pair, then connect the same host
USB cable used for normal left-half operation. After power-on, remove
the bridge before queries. Expected ROM identity is `04d9:8010`; confirm
it before invoking the read-only `ht32-dfu-tool info` command, without a
reset flag. If enumeration fails or the application appears instead,
unplug before changing the bridge. No erase, write or protection change
is part of this test.

The SEL4 entry test passed on 2026-11-13: the left half enumerated as
`04d9:8010` with the bridge removed. The [ROM information record](mistel-md770-left-rom-info.json)
reports model `52352`, ROM v1.03 and 255 usable pages of 512 bytes.
The documented option checksum is valid. Read security and option-byte
protection are enabled; the first 12 KiB are write-protected (`PP0 =
0xfffff000`). No erase, programming, protection change or reset command
was sent. Opaque reply bytes are retained privately with the updater;
the public record contains documented fields only.

After confirming a BOOT-to-ground route, test ROM enumeration, read its
identity and protection options, and obtain a separately verified left-IAP
backup before planning any erase or restoration test. The existing CRC
backup reader now has an explicit `--left` mode using this half's directly
read information anchor and supplied US 4.01 application. It must pass
live CRC calibration before any left-IAP backup is accepted. The default
mode retains the right-half anchor and US 7.02 image checks.

The [backup record](mistel-md770-left-iap-backup.json) now contains two
fresh-session passes. Each passed the 37 calibration checks, reproduced
the directly read information block, and matched all 24 page CRCs and
the whole-region CRC. The 12,288-byte results are byte-identical, SHA-256
`29a4cb40d5b0a4c0280a39bbaa0c58d7f6b93969e8499b4597923b9482565614`.
The canonical private backup is `MD770L_IAP_041A_stock_20261113.bin`.
No flash or protection changes were made. Left stock restoration remains
untested; matching read-only backups do not establish successful restoration.

The [prepared stock-restore test](left-recovery-package.md) now has a
verified package and an independently verified backup copy. The
[planned test record](mistel-md770-left-stock-restore.json) distinguishes
preparation from authorisation and execution. No erase or programming
has been authorised or attempted.

After unplugging USB and reconnecting with SEL4 open, the left half
returned to `04d9:041a` application mode with unchanged boot information.
The owner confirmed normal typing. Both backup passes and the ROM checks
therefore completed without changing the stock application or protection.

## Stock IAP boot decision

The first verified backup has initial SP `0x20001fe0` and reset vector
`0x000000b9`. Its main boot decision at `0x1adc` reads the request word
at `0x20003ffc`, normalises values outside `0x55aafaf0`–`0x55aafaf5`,
and increments a lower valid value when watchdog-reset bit 2 is set.
At `0x55aafaf5` it stays in the stock updater. This establishes the
counter policy in the left image independently of the right IAP.

Otherwise it checks application SP `0x20000000`–`0x20004000`, reset-vector
range `0x3200`–`0x1fdff`, signature `0x04046080` at `0x3bf8`, and the
version-page record before the jump through `0x24`. These are static
findings; watchdog fallback has not been exercised on hardware. Ordinary
power cycles are not the five-watchdog-reset sequence.
