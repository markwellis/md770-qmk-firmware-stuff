# Left-half recovery investigation

QMK has not been flashed. This investigation concerns the photographed
left half; right-half recovery results do not establish left-half recovery.

## Identification

The [controller photograph](mistel-md770-photos/left-controller.jpg) shows
the OEM marking `HOLTEK HT50F52352`. The overview shows revision
`V06 1223BJ`, a five-pad header labelled CN4 and two pairs labelled SEL3
and SEL4. Their signal assignments have not been measured.

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
64-pin package. These are chip-pin assignments, not confirmed SEL3/SEL4
functions on this PCB.

Before bridging anything, disconnect all USB and inter-half cables.
Measure which selector pads have steady continuity to ground and which,
if any, connect to PA9/BOOT. The CN4 pinout is also unverified. Photographic
similarity to the right half is insufficient to select a bridge.

After confirming a BOOT-to-ground route, test ROM enumeration, read its
identity and protection options, and obtain a separately verified left-IAP
backup before planning any erase or restoration test. The existing CRC
backup reader is right-specific and must not be used unchanged on the left.
