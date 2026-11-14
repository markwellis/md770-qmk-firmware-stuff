# Mark's MD770 RGB BT keymap

This is a personal copy of the upstream-candidate `default` keymap from
QMK commit `bec2a0bc17321f4773feae9af4ba5a1b0d0ab4e6`. Its key assignments
and behaviour start unchanged, including Fn/Pn controls, DIP switches,
profiles and lighting. The right-half build enables VIA to retain the
USB lighting-control interface used by the installed firmware. The left
half builds without VIA. One keymap is shared by both half-specific builds.
The upstream keyboard submission retains its own `default` keymap.

QMK discovers this repository through its standard
[External Userspace](https://docs.qmk.fm/newbs_external_userspace) mechanism.
`qmk.json` lists the two personal build targets.

## Setup on NixOS

Keep these three repositories beside one another:

```text
qmk_userspace/
qmk_firmware/
pok3rtool/
```

`shell.nix` provides QMK, its compiler toolchain and the existing `pok3rtool`
CLI. It builds that tool from the sibling checkout and uses its declared
Python dependencies. It sets `QMK_HOME` and `QMK_USERSPACE` inside the shell;
it does not write a global QMK configuration or install a service.

Until the dependencies merge, use QMK branch `mistel-md770-bt-upstream`,
which includes the provisional HT32 reset fix, and `pok3rtool` branch
`mistel-md770`. The QMK submission branch omits that provisional dependency
pin and is waiting for its upstream replacement. See
[ChibiOS-Contrib #469](https://github.com/ChibiOS/ChibiOS-Contrib/pull/469)
and [pok3rtool #19](https://github.com/pok3r-custom/pok3rtool/pull/19).

Run commands from the root of `qmk_userspace`. For an interactive fish shell:

```fish
nix-shell --command fish
qmk userspace-doctor
```

## Edit your setup

Your files are in `keyboards/mistel/md770rgb_bt/keymaps/markwellis/`:

| File | Purpose |
| --- | --- |
| `keymap.json` | Key assignments and layers for both halves |
| `keymap.c` | Fn/Pn behaviour, profiles, DIP handling and custom actions |
| `keymap.h` | Layer names used by the JSON and C code |
| `config.h` | Compile-time options and saved per-key colour storage |
| `rules.mk` | Features enabled for this keymap |
| `rgb_matrix_user.inc` | The saved per-key lighting effect |
| `via.json` | VIA V3 design definition for this keymap |

For a simple remap, change the relevant keycode in `keymap.json` and rebuild.
Keep its layer order consistent with `enum layer_names` in `keymap.h`.

For a custom action, declare a keycode starting at `QK_USER` in `keymap.c`,
assign its name to a key in the JSON, and add its handling to the existing
`process_record_user()` function. That function already implements the
default controls, so extend it rather than defining it twice. Keep the other
existing `_user` hooks when adding behaviour. See QMK's
[custom functions](https://docs.qmk.fm/custom_quantum_functions) and
[keycode reference](https://docs.qmk.fm/keycodes).

No personal functions or remaps have been added yet. `rules.mk` enables
VIA only for the right half; that is the sole build-option change from the
copied default.

For live VIA remapping, open [VIA](https://usevia.app/), enable Show Design
tab in Settings, load this directory's `via.json` as a V3 definition, and
authorise the paired keyboard through the right-half USB interface.
Layers 3–5 are the three programmable profiles. Export VIA changes and keep
the backup in Git if they form part of your setup: EEPROM is not your source
backup. Stored VIA remaps can override changed compiled key assignments.
Hold both physical Alt keys for one second to reset all QMK settings when
needed; this also clears saved profiles, macros and colours.

## Build

From the repository root, this builds both configured halves without flashing:

```fish
nix-shell --run 'qmk userspace-compile -j 4'
```

Or, inside the interactive Nix shell, build one half:

```fish
qmk compile -kb mistel/md770rgb_bt/right -km markwellis
qmk compile -kb mistel/md770rgb_bt/left -km markwellis
```

The build-all command places these ignored outputs in the userspace root:

```text
mistel_md770rgb_bt_right_markwellis.bin
mistel_md770rgb_bt_left_markwellis.bin
```

Commit your source changes, not the generated firmware files.

## Flash

Use the interactive Nix shell above. Flashing uses the retained Mistel
bootloader and `pok3rtool`; there is no secondary DFU loader.
Linux needs the MD770 USB-device access rules from
[qmk_udev's MD770 contribution](https://github.com/qmk/qmk_udev/compare/main...markwellis:mistel-md770-iap).
The rules must be installed before ordinary user-level flashing can work.

Flash one half at a time, with the inter-half cable disconnected and the
recovery pads open. Connect the selected half through its normal host USB
port. Keep power connected until the tool finishes.

For the right half, press Pn+Insert, wait for the three indicator blinks to
finish, then run:

```fish
qmk flash -kb mistel/md770rgb_bt/right -km markwellis
```

For the left half, connect while holding Escape for two seconds, release it,
then run:

```fish
qmk flash -kb mistel/md770rgb_bt/left -km markwellis
```

After each successful flash, unplug host USB at the keyboard for ten seconds,
then reconnect without holding any keys. The tool deliberately leaves the
half in its updater; the power disconnect starts QMK. Rejoin the halves
after both updates, with host USB connected only to the right.

If USB access rules are not installed, build first as your own user, then
run the matching existing flasher with sudo. For the right half, inside the
same shell and after entering its updater:

```fish
sudo -A (command -v pok3rtool) flash QMK ./mistel_md770rgb_bt_right_markwellis.bin --no-boot
```

Use the left filename for the left half. Do not compile QMK with sudo.

Internal flashing does not erase the external settings chip. However, this
QMK revision uses the firmware build date to validate VIA settings:
`quantum/via.c` resets VIA keymaps, macros and layout options when that date
changes. Export your VIA configuration before updating and import it again
when needed. Do not rely on VIA remaps surviving a rebuild on another day.
Other saved settings can also require a reset after storage-format changes.
Pn+Insert itself preserves settings;
holding Delete on the right or Escape on the left during connection clears
that half's QMK settings and enters its updater. The right half stores the
persistent settings; standalone left-half settings are transient.

## Update later

Export any VIA changes before updating. Keep the export with your personal
source files in Git. Keep this userspace repository separate from the QMK
hardware source.
Until the port and dependency fix reach upstream, retain the integration
branch described above. Once they reach upstream `master`, update from the
userspace root with:

```fish
git -C ../qmk_firmware fetch upstream
git -C ../qmk_firmware switch master
git -C ../qmk_firmware merge --ff-only upstream/master
git -C ../qmk_firmware submodule update --init --recursive
```

Update the sibling `pok3rtool` checkout to its upstream version once MD770
support merges. Rebuild and flash your personal targets with the commands
above. Keep the last working QMK revision recorded in your own commit notes
before taking a larger update.

Hardware fixes come from QMK. This copied keymap does not automatically
inherit later edits to QMK's `default` keymap: review changes under
`keyboards/mistel/md770rgb_bt/keymaps/default/` when updating. QMK API
changes can also require adjusting your personal code.

## Initial verification

On 2026-11-14, both personal targets compiled against QMK integration commit
`ab06dea4ecd97a7a688674b325494a2b0ffae248` with the existing ChibiOS reset
correction. Both passed strict QMK lint. The right image is 38,376 bytes and
the left is 30,936 bytes. The left binary matches the hardware-tested image;
the right differs only in the two compiled VIA build-date values.
Userspace detection and the packaged `pok3rtool flash --help` also passed.
No personal firmware image was flashed during setup.
