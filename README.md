# Mistel MD770 QMK

Research for the US-layout Mistel MD770 RGB BT (`MD770BT-M`) and the
inspected right board `MD770BR-RIGHT V06 1223BJ`. This repository contains
the evidence, photographs, reverse-engineering notes, host utilities and
personal QMK userspace.

The QMK port remains in the separate
[qmk_firmware fork](https://github.com/markwellis/qmk_firmware), on the
branch `mistel-md770-support`. Hardware drivers remain in that repository;
this repository contains the personal `markwellis` keymap. Both halves have booted QMK after USB-only updates and
passed basic typing, cold reconnect and updater entry/return checks. Split
typing and cold reconnect now pass with clean firmware on both halves,
including both space bars and cross-half Shift. The diagnostic console has
been removed. RGB effects, indicators and settings persistence passed
hardware validation.

## Personal keymap

This repository is also standard QMK External Userspace. The `markwellis`
keymap starts from the port's default and enables VIA on the right half for
USB lighting control. Upstream QMK retains its own `default` keymap.

With a sibling `qmk_firmware` checkout containing the pending changes:

```fish
nix-shell --run 'qmk userspace-compile -j 4'
```

See the [personal keymap instructions](keyboards/mistel/md770rgb_bt/keymaps/markwellis/readme.md)
for setup, custom functions, building, flashing, VIA backups and updates.
The keymap is GPL-2.0-or-later; see its
[licence](keyboards/mistel/md770rgb_bt/keymaps/markwellis/LICENSE).
Other tools retain their own licences and provenance notices.

## Pending upstream changes

Status checked 2026-11-14. The current build setup includes these pending changes:

| Contribution | Status | Purpose |
| --- | --- | --- |
| [ChibiOS-Contrib #469](https://github.com/ChibiOS/ChibiOS-Contrib/pull/469) | Open | Correct the HT32 reset-controller address |
| [pok3rtool #19](https://github.com/pok3r-custom/pok3rtool/pull/19) | Open | Recognise both MD770 halves and declare missing CLI dependencies |
| [QMK keyboard port](https://github.com/qmk/qmk_firmware/compare/develop...markwellis:qmk_firmware:mistel-md770-support) | Branch prepared; PR not opened | Add the keyboard, default keymap and flashing command |
| [QMK udev rules](https://github.com/qmk/qmk_udev/compare/main...markwellis:mistel-md770-iap) | Branch prepared; PR not opened | Allow user-level USB access for flashing; not needed for compilation |

The ChibiOS fix must also reach QMK's ChibiOS-Contrib fork and dependency pin.
`shell.nix` builds pinned upstream `pok3rtool` with the #19 patch. The
[keymap dependency instructions](keyboards/mistel/md770rgb_bt/keymaps/markwellis/readme.md#pending-upstream-changes)
cover the current setup and switching to upstream once these changes merge.

## Selected flashing route

On 2026-11-14 the owner selected the retained Mistel bootloader with
`pok3rtool` for both initial installation and subsequent updates. QMK's
normal flash command invokes that external tool. See [USB installation](docs/usb-flashing.md).
Both halves passed hardware flashing, application checksum and metadata
verification, normal QMK return and typing on 2026-11-14. The rejoined
keyboard passed both space bars and cross-half Shift. See the
[right](docs/mistel-md770-pok3rtool-right-hardware-test.json) and
[left](docs/mistel-md770-pok3rtool-left-hardware-test.json) test records.

The `md770-secondary-dfu` information branch and
`mistel-md770-secondary-dfu` QMK branch are withdrawn experiments. Keep them
as research; do not merge or submit them. The secondary loader adds firmware,
packaging and recovery maintenance while still needing a CYKB tool for setup.
The custom saved-metadata flasher remains historical recovery tooling.

[pok3rtool PR #19](https://github.com/pok3r-custom/pok3rtool/pull/19) was
opened on 2026-11-14 after the both-half hardware tests. The QMK and udev
PRs remain unopened.

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
- Left-half USB installation, basic typing, Shift/Caps Lock, cold reconnect and Escape-on-connect updater entry/return passed with SEL4 open.
- Split typing and cold reconnect passed after restoring the stock right PB11 active state.
- Every standard key and modifier, Fn navigation/media, each DIP function and the DIP1+DIP3 and DIP2+DIP4 interactions passed.
- Held-key/modifier split-link loss, reconnect, KVM power cycling and USB selective suspend/wake passed.
- Full host sleep/wake and nine other DIP switch combinations remain untested physically.

The feature build includes dedicated Caps Lock/profile indicators, the
three programmable profiles and reset controls, saved per-key lighting,
USB lighting sleep and stale-link lighting recovery. See the
[implementation checkpoint](docs/qmk-upstream-readiness.md#complete-wired-feature-build)
and optional [VIA definition](via/README.md). Both feature images passed USB programming,
paired typing, Caps/profile indicators and RGB on/off across both halves.
The corrected right image also passed factory reset and saved profile/colour
persistence across cold reconnect.

The recorded unit has red switches. A second brown-switch keyboard has
not been checked. Switch colour alone does not establish identical PCB
revisions or IAP contents.

## Documentation

- [Mistel MD770 user manual](docs/mistel-md770-user-manual.pdf)
- [Current QMK implementation and upstream prerequisites](docs/qmk-upstream-readiness.md)
- [Final key, DIP, split-recovery and USB suspend checks](docs/mistel-md770-final-hardware-tests.json)
- [Normal USB installation procedure](docs/usb-flashing.md)
- [Secondary DFU build-only investigation](tests/secondary_dfu_size_probe/README.md) — not installable firmware
- [First right-half QMK hardware result](docs/mistel-md770-right-qmk-first-test.json)
- [First left-half QMK hardware result](docs/mistel-md770-left-qmk-first-test.json)
- [Split bring-up and current firmware checkpoint](docs/mistel-md770-qmk-split-test.json)
- [UART diagnostic evidence](docs/mistel-md770-qmk-split-diagnostics.json)
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

Normal QMK flashing now targets the existing
[pok3rtool MD770 branch](https://github.com/markwellis/pok3rtool/tree/mistel-md770).
The MD770-specific change is its device table; the branch also declares
three dependencies already imported by the tool. See [USB installation](docs/usb-flashing.md)
for the hardware results and remaining limits. The local saved-metadata
flasher below was used in earlier hardware tests and remains available for recovery.


- `scripts/md770-extract.py` extracts the supplied `maaV105` updater offline.
- `scripts/md770_updater_check.py` visits the stock IAP, queries checksums and attempts normal return.
- `scripts/md770_flash.py` installs a compatible application through the retained stock USB updater; offline validation is the default.
- `scripts/md770_prepare_recovery.py` assembles the recorded stock restoration packages offline.
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
[commit 2fae8dc](https://github.com/markwellis/mistel-md770-qmk/tree/2fae8dc/tools/ht32-dfu-tool).

The utility must match the executable hash in the recorded ROM preflight.
A different rebuild needs a fresh recorded read-only preflight first.
