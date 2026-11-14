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

Keep these two repositories beside one another:

```text
qmk_userspace/
qmk_firmware/
```

`shell.nix` provides QMK, its compiler toolchain and `pok3rtool`. The flasher
is built from upstream `pok3r-custom/pok3rtool` commit
`7da3d5169bd5d7218464d302024e97c0d109999a` with the five-line patch from
[pok3rtool #19](https://github.com/pok3r-custom/pok3rtool/pull/19).
There is no dependency on a local `pok3rtool` checkout. The source hash is
fixed, so changes to an upstream branch or PR cannot silently change the tool.

The shell sets `QMK_HOME` and `QMK_USERSPACE` for the session. It does not
write global configuration or install a service.

### Pending upstream changes

| Component | Use before merging | Switch after merging |
| --- | --- | --- |
| QMK keyboard port | Published `markwellis/qmk_firmware` branch `mistel-md770-support` (`bec2a0bc17`); its PR is not open yet | Upstream QMK containing the MD770 port |
| HT32 reset address | Fix commit `410d3636` in the QMK-compatible ChibiOS-Contrib branch below; the existing local integration checkout already includes it | QMK must update its ChibiOS-Contrib dependency to include [ChibiOS-Contrib #469](https://github.com/ChibiOS/ChibiOS-Contrib/pull/469) |
| `pok3rtool` | Pinned upstream source plus `patches/pok3rtool-md770.patch`, applied by `shell.nix` | Update the source pin/hash to a revision containing #19, then remove the patch entry and file |
| USB permissions | [MD770 qmk_udev branch](https://github.com/qmk/qmk_udev/compare/main...markwellis:mistel-md770-iap), or the sudo flashing command below | Install QMK udev rules containing those device IDs |

The first three supply the firmware source, controller reset fix and flasher.
The udev rules affect USB access; they are not required to compile firmware.
Merging #469 into canonical ChibiOS alone is insufficient: the fix must also
reach QMK's ChibiOS-Contrib fork and QMK's selected dependency revision.

The existing local `mistel-md770-bt-upstream` checkout is ready to build.
To reproduce the pending configuration with a fresh sibling checkout, run
these commands from the userspace root. Do not clone over an existing repo:

```fish
git clone --branch mistel-md770-support https://github.com/markwellis/qmk_firmware.git ../qmk_firmware
git -C ../qmk_firmware remote add upstream https://github.com/qmk/qmk_firmware.git
git -C ../qmk_firmware submodule update --init --recursive
git -C ../qmk_firmware/lib/chibios-contrib fetch https://github.com/markwellis/ChibiOS-Contrib.git qmk-ht32f523x2-reset-register
git -C ../qmk_firmware/lib/chibios-contrib checkout --detach 410d3636a15485aefc74559a52e38c8a642b8ad9
```

The final checkout supplies only the reviewed reset-address correction over
QMK's current dependency. QMK reports that submodule as modified until its
upstream dependency catches up; keep that local dependency selection out
of the keyboard submission. Running `git submodule update` on this temporary
setup restores the older pinned dependency, so reselect the fix afterwards.

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
Until the port and dependency fix reach upstream, retain the pending setup
described above. Once both reach upstream `master`, update from the userspace
root with:

```fish
git -C ../qmk_firmware fetch upstream
git -C ../qmk_firmware switch master
git -C ../qmk_firmware merge --ff-only upstream/master
git -C ../qmk_firmware submodule update --init --recursive
```

For the flasher, update `src.rev` and `src.hash` in `shell.nix` to a tested
upstream commit containing #19, then remove `patches/pok3rtool-md770.patch`
and its `patches` entry. Until then, the existing pinned source and patch
continue to work even after the PR merges. Neither source moves automatically.

Re-enter the Nix shell after changing dependencies. Rebuild and flash with
the same personal commands above. Keep the last working QMK revision
recorded in your own commit notes before taking a larger update.

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
