# MD770 RGB BT VIA definition

Use this definition with the right-half QMK default keymap built with VIA:

```fish
make mistel/md770rgb_bt/right:default VIA_ENABLE=yes
make mistel/md770rgb_bt/left:default
```

Apply the dependency correction described in
[the build prerequisites](../docs/qmk-upstream-readiness.md#build-prerequisites)
first. Flash each half separately using the [USB updater](../docs/usb-flashing.md).
Clear QMK settings when installing this layer/storage layout for the first time.
The three programmable profiles increase external-flash use to `0x0000`–`0x1fff`.
This replaces the stock global-settings sector and its first profile sector.

In [VIA](https://usevia.app/), enable **Show Design tab** in Settings. Open
Design and load `md770rgb_bt.json` as a V3 definition. Connect the paired
keyboard through the right half, then authorise its QMK Raw HID interface.
VIA is not required for normal typing or lighting controls.

| VIA layer | Purpose |
| --- | --- |
| 0 | QWERTY base |
| 1 | Colemak base |
| 2 | Dvorak base |
| 3–5 | Programmable profiles 1–3 |
| 6 | DIP1 Mac function-key overlay |
| 7 | Fn shortcuts |
| 8 | DIP4 Caps/Fn overlay |
| 9 | Pn controls |

Profiles start transparent so the selected QWERTY, Colemak or Dvorak layout
still applies. Remap layers 3–5 and assign native VIA macros there. Pn+M,
Pn+comma, Pn+dot and Pn+slash select the default profile and profiles 1–3.
The layer indicator is off, red, green or blue respectively. Pn+Quote cycles
the base layout without changing the profile. Both selections persist.
Fn+R held for one second arms a reset of the selected profile's key assignments.
Release all keys to apply it.
VIA macro text is shared and is retained. Hold both physical Alt keys for
one second to reset all QMK settings, profiles, macros and saved colours.

Pn+F9 starts per-key colour editing. Select a colour with Pn+Escape or
Pn+F6/F7/F8, then tap ordinary keys to paint them. A second tap with the same colour
turns that key off. Ordinary key presses are suppressed while editing; Fn and Pn remain controls.
Press Pn+F9 again to save and exit. Pn+F10 shows the saved colours.
Pn+F5 selects native QMK effects, including the WASD/arrow-key effect.

The physical layout comes from the port's US 85-key `LAYOUT` data. Its custom
keycode order matches the enum in `md770rgb_bt.h`. The lighting options match
this default keymap's compiled effect order; update the definition if changing
that animation set. The format follows the official
[VIA specification](https://www.caniusevia.com/docs/specification/) and
[custom UI documentation](https://www.caniusevia.com/docs/custom_ui/).
Official VIA registration is separate from the QMK keyboard submission.
