# Mistel MD770 RGB BT prior-art search

Checked on 2026-11-12. This was web and source research only: no
keyboard commands, reset, bootloader entry or firmware writes.

**A close HT32 QMK port exists, but this search did not find a published
MD770 RGB BT port, its stock IAP dump, or a verified MD770 BOOT-pad map.**
The useful precedents reduce the software work; they do not establish
recovery on this unit. See [the local recovery investigation](mistel-md770-recovery.md)
and [the firmware specification](mistel-md770-firmware.md).

## Closest new lead: TEX Shinobi BLE5

[cyclistmass/tex-qmk](https://github.com/cyclistmass/tex-qmk) published
Shinobi v1.0 on 2026-11-04. Its author reports daily use on one US board.
The source targets the same HT32F52352 family, a Cheng Yong updater,
application base `0x3200`, retained stock IAP, and SRAM boot magic at
`0x20003ffc`. This is a separate keyboard, so its pin map and recovery
claims do not transfer directly.

Specific reusable work:

- [Board startup](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/qmk/boards/TEX_SHINOBI/board.c)
  contains HSI auto-trim setup and early watchdog reload, plus fault-to-IAP
  and temporary bring-up builds.
- [The linker script](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/qmk/ld/HT32F52352_TEX_SHINOBI.ld)
  aligns vectors to 256 bytes so an app at `0x3200` is not moved to `0x3400`,
  reserves the last 32 SRAM bytes, and preserves the stock application's
  12-byte compatibility record at `0x3bf8`.
- [The patch script](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/tools/patch_qmk_tree.sh)
  enables 64-byte raw HID reports and corrects `RSTCU_BASE` from
  `0x40088000` to `0x40088100`. The incorrect value also appears in the
  [current QMK ChibiOS-Contrib header](https://github.com/qmk/ChibiOS-Contrib/blob/master/os/common/ext/CMSIS/HT32/HT32F523xx/ht32f523x2.h)
  fetched during this search. It is also present in QMK
  `33292390974c75362ca30873c482d052e0bd7a63`'s pinned Contrib commit
  [`5a9ad82b6ba4f649cdb800e8c2bbc9be2d3ce767`](https://github.com/qmk/ChibiOS-Contrib/blob/5a9ad82b6ba4f649cdb800e8c2bbc9be2d3ce767/os/common/ext/CMSIS/HT32/HT32F523xx/ht32f523x2.h).
  Its [register structure](https://github.com/qmk/ChibiOS-Contrib/blob/5a9ad82b6ba4f649cdb800e8c2bbc9be2d3ce767/os/common/ext/CMSIS/HT32/HT32F523xx/ht32f523x2_reg.h)
  places `AHBPRSTR` at offset 4 without compensating padding, and
  [USB stop](https://github.com/qmk/ChibiOS-Contrib/blob/5a9ad82b6ba4f649cdb800e8c2bbc9be2d3ce767/os/hal/ports/HT32/LLD/USBv1/hal_usb_lld.c)
  writes that register. Thus it targets `0x40088004`, not `0x40088104`.
  TEX pins QMK commit `f5db962110615fd263c3ebf9f0402e7c2b08fbe4`.

[PORT_NOTES.md](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/PORT_NOTES.md)
describes stock IAP framing, image checks and observed bring-up failures.
The author reports that omitting the app compatibility record causes the
IAP checksum response to be zero. Its value is board-specific. MD770's
corresponding record must come from its own firmware, not this port.

This lead provides no stock backup shortcut. The notes explicitly say the
IAP is absent from both repository and updater and still needs a SWD dump.
[tex_iap_probe.py](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/tools/tex_iap_probe.py)
has arbitrary memory reads under `Peek`, but explicitly requires a
modified “v6 peek” application. Its register/matrix diagnostics likewise
require diagnostic firmware. These are not unmodified stock APIs.

## Protected-read lead: Holtek ROM CRC

Hansem Ro's [2022 demonstration](https://asciinema.org/a/9JlWn2M2NsOHoi5lTpsas8eWS)
extracts protected bytes on HT32F1654 ROM v1.00. His
[explanation](https://github.com/pok3r-custom/pok3rtool/issues/12#issuecomment-1327965232)
says an overlooked ISP feature permits extraction despite ordinary reads
returning zeros. The [published protocol client](https://gist.githubusercontent.com/hansemro/76493b59cbade75309dde1fdbe1b103b/raw/4fd0bd3504054077251d8a2489f17261caf9680a/holtek_isp.py)
exposes a read-only CRC request, but omits the demonstrated extraction code.
The later investigation recovered this MD770's right IAP through its
ROM v1.03 CRC command. Two fresh-session backups matched byte for byte.
The [recovery record](mistel-md770-recovery.md#read-only-crc-bootloader-backup)
describes the calibration, verified backup and remaining limits.

## Actual Mistel recovery precedent: MD600

[Mistel Barocco MD600 Support/Unbricking, issue 25](https://github.com/pok3r-custom/pok3r_re_firmware/issues/25)
documents a successful 2018 recovery using Raspberry Pi SWD, OpenOCD,
CN2 and shorted SEL2 pads. The owner replaced the original bootloader with
a POK3R RGB bootloader, then patched the stock app's compatibility record.
This restored the keyboard; the original bootloader had already been lost.

The [maintainer's explanation](https://github.com/pok3r-custom/pok3r_re_firmware/issues/25#issuecomment-432726716)
is particularly relevant: on that MD600, an intact version header could
make the IAP jump into a corrupted app indefinitely. Their bootloader-dump
method required downloading a patched application first. This is evidence
against assuming every related IAP automatically rescues a broken app.
It does not establish that the MD770 has the same policy, pin headers or
replacement-bootloader compatibility.

## Other useful HT32 precedents

| Source | Established work | Limit for this MD770 |
| --- | --- | --- |
| [MK Typist research](https://github.com/jpsutton/mk-typist-research) | HT32F52352, Cheng Yong IAP analysis and protection/recovery research | Another board; its watchdog threshold and bootloader are not the MD770's |
| [MK Typist tools](https://github.com/jpsutton/mk-typist-tools) | Related update-container and device tooling | Its older container template conversions must not be applied blindly to `maaV105` |
| [re-masterkeys](https://github.com/mateuszradomski/re-masterkeys) | HT32F52352 QMK and lighting work, including OEM marking `HT50F52352` | Different matrix, LED driver and firmware |
| [pok3rtool issue 6](https://github.com/pok3r-custom/pok3rtool/issues/6#issuecomment-589520836) | Maintainer describes patched-app full-flash dump; another owner confirms success | Requires writing modified firmware first; no read-only dump shortcut |
| [Masterkeys recovery confirmation](https://github.com/pok3r-custom/pok3rtool/issues/6#issuecomment-3097290350) | A second owner confirms ROM-loader restoration with `ht32-dfu-tool` in July 2025 | Uses a saved Masterkeys stock IAP; not an MD770 image |
| [ht32-dfu-tool](https://github.com/hansemro/ht32-dfu-tool) | Independent Holtek ROM-loader client | Requires entering ROM mode and checking this chip's protection |

The [Holtek marking discussion](https://github.com/pok3r-custom/pok3r_re_firmware/issues/32#issuecomment-644006845)
supports treating `HT50F52352` as a likely OEM marking for HT32F52352.
This unit's photographed controller is marked `HT50F52352`; its later
ROM model-slot value also matches `52352`, as recorded in the recovery notes.

## MD770 sources and misleading search hits

- [Geekboards' MD770 RGB BT teardown](https://wiki.geekboards.ru/disassembling/barocco-mistel-md770-rgb-bt/)
  provides actual PCB photographs. The exposed pad groups are not a
  verified BOOT/SWD pin map.
- [A Chinese MD770 teardown](https://post.smzdm.com/p/aqx98enk/)
  identifies HT50F52-family controllers in both halves, but is not
  reverse-engineering documentation and is not established as this BT revision.
- [Linux's MD770 HID fix](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=9bc089307e8dff7797233308372b4a90ce8f79be)
  fixes the NKRO report descriptor on the host. It is not replacement
  keyboard firmware or a recovery implementation.
- [Mistel's MD770 PRO update instructions](https://www.mistelkeyboard.com/whats-new/ec834031e69ebc0ee19705c1d27cac66)
  concern the newer PRO board. Its Home/Esc DFU sequence is not verified
  for the MD770 RGB BT.
- [The SonixQMK suggestion in this gist](https://gist.github.com/itod/ae27b30f7517dc18b8df110c1d98bccb)
  is in a comment about Cloud Nine ErgoFS/ErgoTKL, not MD770. It should not
  be cited as evidence of MD770 Sonix hardware or port work.
- [The MD600 firmware gist](https://gist.github.com/jdhom/9f160a2aa46102f987e0f31a697b20fc)
  is an onboard programming guide. Loaded comments include requests for
  custom firmware through August 2025, without a linked working port.

## Search scope and remaining gap

Searched GitHub repositories, files, issues and commits, indexed GitLab
pages, Reddit, Geekhack, owner blogs and English, Chinese, Japanese,
Russian and Korean queries. Terms included MD770/Mistel with QMK,
reverse engineering, custom firmware, HT32/HT50, bootloader, SWD, dump,
brick and recovery. Repository and issue searches were supplemented with
direct source inspection; ordinary search results frequently match an
unrelated keyboard mentioned elsewhere on the same page.

The four repositories returned by GitHub's `md770` repository search were
[tenting CAD](https://github.com/carstenorthbandt/barocco_md770),
[Karabiner mappings](https://github.com/omochi1224/md770-karabiner-setting),
[a manual](https://github.com/hoseroony/mistel-md770-manual) and
[an unrelated Angular app](https://github.com/BizTechoff/md770).
The checked POK3R project issue lists contain MD600 recovery work, but no
MD770-specific port or recovery report.

No checked source supplied the actual MD770 RGB BT bootloader, its flash
protection state, a confirmed physical BOOT-pad map, or a verified
stock-firmware key combination that forces IAP after an app failure.
This is a bounded search result, not proof that unpublished work does not
exist. The remaining recovery evidence must come from this unit or a
matching, verifiable hardware/firmware dump.

## Follow-up after inspecting the owner's board

The owner's photographs reveal CN2 and SEL2 next to an HT50F52352 and
two MBIA043GP drivers. A subsequent broader search located the primary
[Tab75 wiki notes](https://raw.githubusercontent.com/wiki/ephb/pok3r_re_firmware/Tab75-Notes.md).
They describe the same marked MCU and LED-driver type, a GD25Q40, and
those header names. The documented CN2 order is 3.3 V, SWDIO, SWCLK,
nRST, GND. SEL2 is BOOT1 (**unconfirmed**) and GND.

The Tab75 is a different board, marked `KA01E63122H010-AH0820 V05`.
Its notes provide a useful proposed measurement order, not an MD770 pad
map. The `ephb` raw wiki source was verified directly; the corresponding
`pok3r-custom` raw wiki path returns 404. The actual MD770 photographs and
unpowered continuity plan are recorded in the recovery investigation.
