# Verified stock restoration for the left half

This procedure targets the recorded MD770BT-S left half, KB041A, US 4.01.
Stock restoration passed on this unit on 2026-11-13. QMK was not involved.

The initial mass-erase/write attempt stopped with a generic write error
after successful ROM return. Its readback matched stock through `0x31ff`,
with the application region erased; this does not establish whether the
prefix was retained or rewritten. The exact initial failure remains unknown.
Cold ROM entry followed by the deliberate page-erase continuation below
completed restoration. Do not blindly repeat programming after an error.

All 130,560 bytes and six documented protection/checksum words matched
readback. Cold boot, typing, stock-updater entry/checksums/return, a cold
ROM protection query and final normal return passed. The successful writer
has SHA-256 `3df4b1fdd66618e0cbda9e60f6ec724d61c83b1bac8d54bda9a4fe8f7692f392`;
it adds error diagnostics without changing transfers or acknowledgement rules.

The reconstructed 130,560-byte stock-main-flash.bin has SHA-256
`eb6eb73f6d929958bb7c0d72d5f3d919c20cf96985284a3c55ea8717d5c85b28`.

| Region | Source |
| --- | --- |
| `0x0000`–`0x2fff` | Twice-read left IAP, SHA-256 `29a4cb40d5b0a4c0280a39bbaa0c58d7f6b93969e8499b4597923b9482565614` |
| `0x3000`–`0x31ff` | Official 180-byte version template, padded with `ff` |
| `0x3200`–`0xc033` | Official decoded US 4.01 application |
| `0xc034`–`0x1fdff` | Erased `ff` padding |
| `0x1fe00`–`0x1ffff` | Option page, excluded from the image |

The version template matches all 480 bytes read from the stock application. Its last 32 bytes are canonical padding,
not a direct read. The stock updater's sum and CRC32 already match the
supplied application. The IAP boot policy independently accepts this layout.

The mass erase clears internal flash, including the option page. The tool
restores and verifies the six documented protection/checksum words. It does
not guarantee bit-for-bit restoration of undocumented factory option data.
The original opaque option reply is included as evidence only and must not
be replayed as programming data. No external SPI-flash erase is requested.

Before any erase, keep a verified copy of this complete package in safe
storage separate from the working checkout. It includes the writer source,
locked dependencies, executable and exact x86_64 Linux Nix runtime closure.

Verify the package from its directory:

```fish
sha256sum -c SHA256SUMS
zstd -t nix-runtime.nar.zst
./ht32-dfu-tool --version
```

If the recorded Nix runtime paths are missing, restore the archive first:

```fish
zstd -dc nix-runtime.nar.zst | sudo -A nix-store --import
```

For a future destructive restoration, after explicit approval:

1. Disconnect USB, the inter-half cable and all other power.
2. Securely bridge only the measured SEL4 BOOT/GND pair. Connect normal host USB.
3. Keep SEL4 bridged through the erase/reset, programming and verification.
4. Confirm exactly one `04d9:8010` device. Run the read-only preflight:

   ```fish
   sudo -A ./ht32-dfu-tool info
   ```

   Require model HT32F52352, ROM v103, 512-byte pages, 130,560 usable bytes,
   PP0 `fffff000`, PP1–3 `ffffffff`, CP `fffffffc`, checksum `ffffeff9`.
   Compare the actual option words and this image's hash before programming.

5. Run the reviewed destructive command once:

   ```fish
   sudo -A ./ht32-dfu-tool write 0x0 stock-main-flash.bin true true 0xfffff000 0xffffffff 0xffffffff 0xffffffff --mass-erase --verify
   ```

   It mass-erases, resets into ROM, validates erased protection and geometry,
   writes the immutable input, compares
   every byte, then restores and verifies the documented option words.

6. On any error, stop. Do not blindly retry a word or rerun mass erase.
   Unplug, wait two seconds, secure SEL4, reconnect and query `info`.
   An unprotected device with all six documented option words `ffffffff`
   can use a separately reviewed continuation that deliberately page-erases
   the full input range before writing, without another mass-erase/reset:

   ```fish
   sudo -A ./ht32-dfu-tool write 0x0 stock-main-flash.bin true true 0xfffff000 0xffffffff 0xffffffff 0xffffffff --verify
   ```

7. After programming succeeds, unplug USB, remove SEL4's bridge and reconnect
   normally. Require `04d9:041a`, normal left-half typing and unchanged boot info.
8. Repeat the stock-updater checksum/return check against US 4.01. Re-enter ROM
   read-only if needed to confirm the final documented protection state, then
   unplug and reconnect with SEL4 open to finish in normal typing mode.

The source record is [mistel-md770-left-stock-restore.json](mistel-md770-left-stock-restore.json).
The recorded success used the cold-ROM page-erase continuation; the direct
write immediately following mass erase has not been shown to succeed here.
