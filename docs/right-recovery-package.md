# Prepared recovery for the red-switch right half

This package targets the recorded US-layout MD770 RGB BT right half,
model `KB0419`, application `04d9:0419`, stock IAP `04d9:1419`, and
Holtek ROM `04d9:8010`. The left half uses a different image.

The image and host utility have passed offline checks and static review.
The corrected utility's read-only ROM preflight passed on this unit.
The erase/program procedure below has not been executed or verified on
hardware. It is prepared for recovery, not an instruction to run now.

## Contents and image layout

`stock-main-flash.bin` is a reconstructed restoration image, not a full
original-flash dump. Its SHA-256 is
`8d961215101b93760d20dfbc717f6cd6a2fa879fae26e71a478089df39095ffd`.

| Region | Source |
| --- | --- |
| `0x0000`–`0x2fff` | Twice-read stock IAP, SHA-256 `61e377ee21584a7bce42a2a9532a40b6682ba9d1a095cfe08708555ab7e5bd4e` |
| `0x3000`–`0x31ff` | Canonical 180-byte US version template, padded with `ff` |
| `0x3200`–`0xf16f` | Official decoded US 7.02 application |
| `0xf170`–`0x1fdff` | Erased `ff` padding |
| `0x1fe00`–`0x1ffff` | Option page; excluded from the image |

All 480 previously read version-page bytes match the reconstructed page.
Its final 32 bytes are canonical padding, not bytes read from this unit.
The installed application sum and CRC32 match the supplied updater.

`observed-rom-option-reply.bin` is evidence only. Its unexplained tail
must not be replayed as programming data. `original-protection.json`
records the six documented protection/checksum words used below.

The external SPI-flash settings are not included. The owner uses defaults
and accepts replacing the stock global-settings sector with QMK settings.

## Host environment

The supplied executable is for x86_64 Linux with Nix. Its exact shared
library closure is included so garbage collection does not remove the
only copy needed for recovery. Verify all package hashes first:

```fish
sha256sum -c SHA256SUMS
zstd -t nix-runtime.nar.zst
```

If required, import the runtime paths on a Nix host:

```fish
zstd -dc nix-runtime.nar.zst | sudo -A nix-store --import
./ht32-dfu-tool --version
```

The complete utility source, lock file and licence are under `tool-source/`.
It can be rebuilt with Cargo and libusb. A rebuild needs its locked crates
in the Cargo cache or network access; the supplied binary/runtime pair
does not need a rebuild.

## Prepared restoration procedure

1. Confirm this is the recorded right unit and verify `SHA256SUMS`.
2. Disconnect host USB, the inter-half cable and all battery/wireless power.
3. Bridge only the measured SEL2 BOOT/GND pads, then connect normal host USB.
4. Keep SEL2 bridged through the erase/reset/reconnection below. The host
   must re-enter ROM after clearing security. Do not run the stock application
   while its PA9/SPI chip-select pin is bridged to ground.
5. Query ROM information:

   ```fish
   sudo -A ./ht32-dfu-tool info
   ```

   Require model `HT32F52352`, ROM `v103`, 512-byte pages and 130,560 usable
   bytes. Match the saved unit's protection values before proceeding.

6. The prepared destructive command is:

   ```fish
   sudo -A ./ht32-dfu-tool write 0x0 stock-main-flash.bin true true 0xfffff000 0xffffffff 0xffffffff 0xffffffff --mass-erase --verify
   ```

   The corrected utility mass-erases and resets, rechecks geometry and
   erased option words, writes the immutable input, accounts for every
   acknowledgement, and compares a full unprotected byte readback. Only
   then does it restore the four protection words, control word and
   wrapping checksum. It verifies those words before reset loads them.

7. If any operation fails, stop. Do not blindly retry programming a word;
   a deliberate erase is needed before another programming attempt.
8. After success, unplug USB, remove the SEL2 bridge and reconnect normally.
   Verify `04d9:0419`, typing and stock operation.

The restored documented words are `PP0=fffff000`, `PP1..3=ffffffff`,
`CP=fffffffc` and `CK=ffffeff9`. This restores documented protection
semantics. Bit-for-bit restoration of undocumented option metadata has
not been established.
