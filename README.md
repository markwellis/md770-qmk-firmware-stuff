# Personal QMK userspace

The `markwellis` MD770 RGB BT keymap lives here. QMK keeps the hardware
drivers and upstream `default` keymap in its separate repository.

See the [keymap instructions](keyboards/mistel/md770rgb_bt/keymaps/markwellis/readme.md)
for setup, editing, building, flashing and updating.

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

The keymap is GPL-2.0-or-later; see `LICENSE` and the source notices.
