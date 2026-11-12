# Mistel MD770 backlight

Confirmed on 2026-11-12: the MD770BT-M (`04d9:0419`, USB
`bcdDevice 0710`) supports host-controlled RGB through its stock firmware.
The keyboard accepts RGB commands and restores its original off state, but
stable timed flashing remains unresolved: the stock renderer overwrites the
requested colours. Streaming frames produces visible flicker within each
on phase, as confirmed by the user. The script remains experimental.

The owner subsequently supplied the V1.07.02 updater, and a read-only query
confirmed that version on the connected right half. Current-version
decompilation, split transport and RGB driver findings are recorded in
[the firmware reconstruction](mistel-md770-firmware.md). The older-image
addresses below are retained as the original investigation record.

From the repository root, using fish:

```fish
sudo -A (command -v python3) scripts/md770-backlight.py info
sudo -A (command -v python3) scripts/md770-backlight.py flash
```

The script detects the keyboard's vendor HID interface, saves its RGB RAM,
streams white/off frames for five half-second on/off cycles and restores
the RGB RAM and previous mode. Neither changing the Python sleeps nor
streaming frames has produced clean pulses on the connected keyboard.
It accepts normal mode 0 only; preserving an existing direct-control session's
automatic-update setting has not been established. Root access is currently
required for the HID device. No udev rule or notification integration is installed.

## USB protocol

Interface 1 is vendor-defined HID (usage page `FF00`), with 64-byte input
and output reports. Linux hidraw writes need a leading zero report ID,
making each write 65 bytes. Responses contain 64 bytes. Arguments and
indices are little-endian. Unused bytes are zero-padded.

| Packet prefix | Behaviour |
| --- | --- |
| `41 FF 00 00` | Query mode and timeout; response begins `41 mode timeoutLo timeoutHi`. |
| `C1 00 pageLo pageHi` | Read up to 60 RGB bytes after the four-byte header; pages 0–4 cover 96 RGB slots. |
| `41 02 00 00` | Enter direct mode and clear RGB RAM. |
| `C0 00 00 00 R G B` | Fill all RGB slots in RAM. |
| `C0 F0 00 00 00` | Commit RGB RAM once with automatic updates disabled. |
| `C0 D3 indexLo indexHi` followed by 60 RGB bytes | Write 20 RGB slots; subcommand is `C0 + count - 1`. |
| `41 mode timeoutLo timeoutHi` | Restore the original mode; mode 0 resumes normal effects. |

Unknown commands return `FF AA 00 00` followed by the original four-byte
header. The commands above manipulate lighting RAM and do not program flash.

## Stock renderer interference

Live RGB readback found all 288 colour bytes zero 0.112 seconds after a
white fill and commit, with direct mode still active. Modes 2 and 3 both
showed this behaviour. The user confirmed the brief flashes and the rapid
flicker during the later streaming test.

In the decoded firmware, `0x7f44` unconditionally schedules stock rendering.
The main loop calls `0x7cf8`, which composes effects and applies saved
brightness; zero brightness clears RGB RAM. The direct-mode bits do not
suspend this complete pipeline. A firmware change could provide exclusive
lighting control, but the exact installed firmware and recovery path must
be established before preparing an image for flashing.

## Reverse engineering evidence

The [official distributor updater](https://archisite.co.jp/question/md770us-rgbbt-fwpd/)
was inspected statically; its Windows executables were never run.
The public ZIP is `MD770-RGB-BT-Firmware-20200917-1.zip`, SHA-256
`39458714f79bc9d6630f922ea8175eb0f510c1d3a4ac2a4a4cba4b922d9f6bf7`.

The updater uses Cheng Yong's `maaV105` packaging. Decode the final
`0x2b58` bytes using the wrapper transform in x86 function `0x401000`:
swap bytes `i` and `i+4` for `i = 0,5,...` while `i < length-5`, swap adjacent
byte pairs, then transform each original byte `x` to
`(((x-7)<<4)+(x>>4)) & 255`. The metadata lists firmware/version lengths
at `0x22d8 - group*0x6e0 - entry*0x50` (five groups, nine entries).
Walk backwards from the metadata, decoding each version then firmware block.
Firmware also needs the 52-byte repeating XOR transform implemented by
[`mk-typist-tools`](https://github.com/jpsutton/mk-typist-tools).

The right-hand updater's group 2, entry 7 contains the RGB application:
62,444 decoded bytes, SHA-256
`4cd53a095ef4992387923b2ed823e3534cc99adbb45b0e4009cf99c806f1dddd`.
It is ARM Thumb firmware linked at `0x3200`, with initial stack pointer
`0x20003fe0` and reset vector `0x32c1`.

| Firmware address | Behaviour |
| --- | --- |
| `0x9f5c` | USB command dispatch using RAM buffer `0x2000062c`. |
| `0xa778` | Dispatch commands at or above `0x40`. |
| `0xa8c2` | Mode query/set handler. |
| `0xa5f4` | RGB RAM read handler. |
| `0xaf0a` | RGB command handler. |
| `0x52ec` | Fill all 96 RGB slots. |
| `0xb55c` | Write consecutive RGB slots. |
| `0xa318` | Convert and commit RGB RAM to hardware. |

These addresses describe the old updater image, not a dump of the currently
installed firmware. Live mode queries, RGB reads, writes and restoration
worked on the connected version. The precise MCU has not been confirmed.

Related [MK Typist research](https://github.com/jpsutton/mk-typist-research)
provided the encoding and bootloader leads. Its QMK port uses the Holtek
HT32F52352 platform, but its firmware image is not compatible evidence for
the MD770. In particular, the MD770 image's application header begins
`040450c0 34000001`, differing from the Typist's `04040000 34000001`.
