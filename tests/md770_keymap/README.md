# MD770 keymap and indicator regression harnesses

These compile the actual QMK source with mocked host/hardware services.
They check colour-editor press/release pairing, held Fn, saved colours,
physical Alt reset timing, deferred profile rewrites, early indicator calls,
PWM limits, Caps/profile independence and suspend/resume. They do not prove
physical wiring, LED current or firmware timing on the keyboard.

Run from this repository with the QMK checkout beside it:

```fish
nix-shell -p gcc --run 'gcc -std=c11 -Wall -Wextra -Werror -Itests/md770_keymap -I../qmk_firmware -I../qmk_firmware/quantum -DQMK_KEYBOARD_H=\"keyboards/mistel/md770rgb_bt/md770rgb_bt.h\" -DRGB_MATRIX_ENABLE -DDYNAMIC_KEYMAP_ENABLE ../qmk_firmware/keyboards/mistel/md770rgb_bt/keymaps/default/keymap.c tests/md770_keymap/test.c -o /tmp/md770-keymap-test && /tmp/md770-keymap-test'
nix-shell -p gcc --run 'gcc -std=c11 -Wall -Wextra -Werror -Itests/md770_keymap -I../qmk_firmware ../qmk_firmware/keyboards/mistel/md770rgb_bt/indicators.c tests/md770_keymap/indicators.c -o /tmp/md770-indicators-test && /tmp/md770-indicators-test'
```
