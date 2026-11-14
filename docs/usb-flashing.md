# USB installation for MD770 RGB BT

Normal installation uses the retained stock USB updater. No PCB bridge is
required. SEL2 on the right and SEL4 on the left remain emergency ROM
recovery methods when neither application entry nor the stock updater works.

The owner selected this retained-bootloader route on 2026-11-14 for both
initial installation and every subsequent update. The secondary DFU
experiment is withdrawn. No replacement or secondary bootloader is required.

## Existing-tool integration

The upstream candidate now uses
[pok3rtool](https://github.com/pok3r-custom/pok3rtool), with the two MD770
application IDs added on the
[MD770 branch](https://github.com/markwellis/pok3rtool/tree/mistel-md770).
Its existing CYKB flashing implementation is unchanged. It derives the
updater IDs and geometry from the device. Install it using that project's
instructions, then use QMK's normal `make ...:flash` or `qmk flash -kb ...`
command for the selected half.

The equivalent standalone command is:

```fish
pok3rtool flash QMK /path/to/half-application.bin --no-boot
```

Connect only the target half. From QMK, enter the updater with Pn+Insert,
or hold Delete on the right / Escape on the left while connecting USB.
Stock application firmware permits automatic software entry. After the
tool succeeds, unplug and reconnect to start QMK. The tool's automatic
return discovery expects a stock vendor interface that QMK does not expose.
Linux needs USB-device access for libusb; the MD770 `qmk_udev` branch
provides that access without applying pok3rtool's broad vendor-wide rule.

This tool writes a generated `QMK` version page. It does not preserve the
original version page or require this repository's saved metadata. Both
recovered MD770 bootloaders accept its metadata format. Images must match
the connected half, have a size divisible by four, and fit within the
`0x1cc00` application limit. The existing tool does not enforce all of
these MD770-specific checks; use the correct per-half QMK build.

**The pok3rtool route has passed offline simulation with both current
images. It has not yet been flashed on this keyboard.** The
[result](mistel-md770-pok3rtool-compatibility.json) records the exact source
and image hashes. Reproduce it without USB access:

```fish
python3 -B tests/pok3rtool_compatibility.py /path/to/pok3rtool /path/to/qmk_firmware
```

## Recorded installation tool

The following procedure records the hardware-tested saved-metadata tool.
It remains available for recovery and investigation.

The USB flasher is prepared for the recorded US-layout RGB BT firmware.
Its protocol has been checked against the recovered right bootloader and
host failure-path tests. The recorded right half passed USB installation,
QMK enumeration, basic typing and cold reconnect with SEL2 open. The left
half passed the same tests with SEL4 open. Updater entry and return passed
using Pn+Insert on the right and Escape-on-connect on the left. See the
[right](mistel-md770-right-qmk-first-test.json) and
[left](mistel-md770-left-qmk-first-test.json) records. Hardware interruption
tests remain untested.

## Right-half first test

Connect only the recorded right half to the normal host USB port. Disconnect
the inter-half cable and battery power. Leave all pads open. DIP positions
affect the resulting mappings but not the update protocol.

From this repository, validate the QMK application offline:

```fish
python3 scripts/md770_flash.py /path/to/qmk-application.bin docs/mistel-md770-live-info.json
```

This opens no USB device. The input must be the application binary linked
at `0x3200`, not a full recovery image. For the actual update:

```fish
sudo -A python3 scripts/md770_flash.py /path/to/qmk-application.bin docs/mistel-md770-live-info.json --flash --output /path/to/new-result.json
```

The result file must not already exist. Keep the USB cable connected until
the tool finishes. It enters the updater from stock firmware automatically.
When QMK is already installed, use Pn+Insert to enter the stock updater first;
the QMK default build does not expose the stock vendor USB reset command.
The tool also accepts a matching updater that is already enumerated.

It checks the boot information against the supplied record and accepts
only a matching version page, or erased portions of that same page after
an interrupted update. Keep a saved boot/version record for the exact half
being updated. Do not substitute a different model's or layout's metadata.

## Left-half installation

Connect only the left half, with SEL4 open and the inter-half cable and battery
power disconnected. Use its own application image and saved metadata:

```fish
sudo -A python3 scripts/md770_flash.py /path/to/left-application.bin docs/mistel-md770-left-live-info.json --half left --flash --output /path/to/new-left-result.json
```

Stock firmware enters the updater automatically. From an installed QMK left
half, hold Escape while connecting USB, wait two seconds, then release it.
This uses Bootmagic and clears QMK settings. The tool then accepts the
left updater already present as `04d9:141a`.

## Transaction and bounds

The right IAP dispatcher at `0xac4` implements the following commands.
Pointers are relative to `0x3000`; addresses below that are outside the
update window.

| Command | Check |
| --- | --- |
| `1d 00` | Erase relative `0`, length `0x1ce00`; require both start and actual erased count in the reply |
| `1e 01`, `1e 00` | Set/read a word-aligned pointer; require the returned pointer |
| `1f len` | Send 52-byte encoded application blocks, then the remaining whole words; require the `1e 02` next-pointer acknowledgement |
| `1d 01`, `1d 02` | Compare the encoded application's wrapping word sum and CRC32 |
| `12 20`–`12 27` | Read the exposed 480 version-page bytes |
| `11 01` | Start the application only after all checks pass |

The erase spans `0x3000`–`0x1fdff`. It preserves the IAP at
`0x0000`–`0x2fff` and excludes the option page at `0x1fe00`.
The advertised 231 update pages include the version page. The maximum
application from `0x3200` is therefore `0x1cc00` bytes.

After application verification, the tool writes raw version bytes `0..0xaf`
and checks readback while the validity marker is still erased. It writes
the four-byte marker at `0xb0` last, then checks all 480 exposed bytes.
Version bytes from `0xb4` onwards must be erased in the supplied record.
The final 32 version-page bytes are not exposed by this interface and remain
erased by the update. Application verification uses both IAP checksums,
not an independent byte readback.

After an error, the tool stops without retrying a write or booting the
application. Inspect the result before a deliberate retry. An incomplete
version commit normally keeps the device in its resident updater; this
behaviour still needs a hardware interruption test. Physical ROM recovery
remains available if the updater cannot be reached.

## Protocol precedents

The MD770-specific command bounds and replies come from its recovered IAP.
Related public implementations describe the same protocol:
[pok3rtool CYKB client](https://github.com/pok3r-custom/pok3rtool/blob/master/pok3rtool/cykb.py)
and [TEX Shinobi USB flasher](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/tools/tex_flash.py).
Their keyboard-specific metadata and erase arguments must not be copied
without checking the target bootloader.
