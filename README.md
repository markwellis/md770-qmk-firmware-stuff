# Mistel MD770 RGB BT research and tools

Research for the US-layout Mistel MD770 RGB BT (`MD770BT-M`) and the
inspected right board `MD770BR-RIGHT V06 1223BJ`. This repository contains
the evidence, photographs, reverse-engineering notes and host utilities.

The QMK port remains in the separate
[qmk_firmware fork](https://github.com/markwellis/qmk_firmware), on the
local development branch `mistel-md770-bt`. QMK source and patches are not
duplicated here. The right half has booted QMK after a USB-only update and
passed basic typing and cold reconnect checks. Left-half QMK, the split link
and RGB remain untested.

## Current evidence

- The right controller is marked `HT50F52352`; its ROM reports model value `52352`.
- Measured SEL2 BOOT/GND connections enter the independent Holtek ROM loader.
- Two fresh-session reads produced identical 12 KiB right-IAP backups.
- All 37 later CRC checks, including internal anchor and six-byte checks, passed.
- Stock-updater entry, application checksum comparison and normal return passed.
- Stock restoration passed on the recorded right half, including full byte readback and protection-word verification.
- Cold boot, right-half typing and the restored stock updater's checksum/return checks passed.
- Both halves have verified ROM entry, two matching stock-IAP backups and successful stock restoration.
- Right-half QMK USB installation, basic typing and cold reconnect passed with SEL2 open.
- A one-line DIP polarity correction passed DIP1 OFF/ON/OFF and cold reconnect testing.
- Left-half QMK, split operation, complete key coverage, remaining DIP functions/combinations, RGB and settings persistence remain untested.

The recorded unit has red switches. A second brown-switch keyboard has
not been checked. Switch colour alone does not establish identical PCB
revisions or IAP contents.

## Documentation

- [Mistel MD770 user manual](docs/mistel-md770-user-manual.pdf)
- [Current QMK implementation and upstream prerequisites](docs/qmk-upstream-readiness.md)
- [Normal USB installation procedure](docs/usb-flashing.md)
- [First right-half QMK hardware result](docs/mistel-md770-right-qmk-first-test.json)
- [Recovery and bootloader investigation](docs/mistel-md770-recovery.md)
- [Left-half recovery investigation](docs/left-recovery-investigation.md)
- [Firmware reconstruction, wiring and protocols](docs/mistel-md770-firmware.md)
- [Initial QMK feasibility assessment](docs/mistel-md770-qmk-feasibility.md)
- [Prior research and primary sources](docs/mistel-md770-prior-art.md)
- [Stock lighting experiments](docs/mistel-md770.md)
- [Prepared right-half recovery procedure](docs/right-recovery-package.md)
- [Verified left-half recovery procedure](docs/left-recovery-package.md)
- [Verified right-half stock restore and its logs](docs/mistel-md770-stock-restore.json)

The photographs under `docs/mistel-md770-photos/` are JPEGs with EXIF,
XMP and IPTC removed. Their compressed image data was preserved.

## Host tools

- `scripts/md770-extract.py` extracts the supplied `maaV105` updater offline.
- `scripts/md770_updater_check.py` visits the stock IAP, queries checksums and attempts normal return.
- `scripts/md770_flash.py` installs a compatible application through the retained stock USB updater; offline validation is the default.
- `scripts/md770_prepare_recovery.py` assembles the known right-half restoration package offline.
- `scripts/md770-backlight.py` contains the stock-lighting experiment.
- `scripts/md770-ghidra/` reproduces the decompilation setup and exports.
- `tools/ht32-dfu-tool/` contains the pinned and corrected Holtek host utility.
- `tools/ht32-dfu-tool/src/bin/md770-rom-crc.rs` contains the CRC-only backup reader.

The diagnostic and backup reader cannot program firmware. The
`ht32-dfu-tool write` command can erase/program it; its presence does not
mean a restoration has been tested.

Build the Rust tools on NixOS:

```fish
cd tools/ht32-dfu-tool
nix-shell -p cargo rustc pkg-config libusb1 gcc --run 'cargo test --locked --bins && cargo build --release --locked --bins'
```

Run the Python host tests from this repository's root:

```fish
python3 -B -m unittest discover -s tests -p 'test_md770*.py' -v
```

See [the host utility provenance](tools/ht32-dfu-tool/UPSTREAM.md) for the
pinned upstream revision, local corrections and upstream licence.

## Firmware and recovery artefacts

Firmware executables, decoded images, device backups, compiled tools and
Nix runtime archives stay outside Git. Evidence records contain their
hashes. The recorded unit's recovery bundle is kept outside this repository as
`red_right_recovery_20261112/`.
All 25 `SHA256SUMS` entries and the runtime archive passed verification after
copying. Its `manifest.json` SHA-256 is
`dc166f3da075d475406940e5e22de0833396e6cf8d2491063c4aea614e314050`.

Recreate the known package with the original updater, the verified
IAP backup, the saved preflighted host utility and its runtime archive:

```fish
python3 scripts/md770_prepare_recovery.py /path/to/new-package \
    --updater /path/to/MD770R_FW_0419_7.02_20230421.exe \
    --iap /path/to/red_right_MD770R_IAP_0419_stock_20261112.bin \
    --binary /path/to/preflighted/ht32-dfu-tool \
    --tool-source /path/to/preflighted/tool-source \
    --runtime /path/to/nix-runtime.nar.zst
```

This builder targets the recorded right US 7.02 image and checks the
known input and final-image hashes. It does not execute the Windows
updater or send USB commands.

The binary and its corresponding source snapshot must match the recorded
fingerprints. The frozen right-hand writer needs its original `tool-source`
directory; the maintained source now includes additional diagnostics.
The corresponding original writer source is available at
[commit 2fae8dc](https://github.com/markwellis/md770-qmk-firmware-stuff/tree/2fae8dc/tools/ht32-dfu-tool).

The utility must match the executable hash in the recorded ROM preflight.
A different rebuild needs a fresh recorded read-only preflight first.
