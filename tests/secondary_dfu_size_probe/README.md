# Secondary DFU offline build proof

DO NOT FLASH. This prototype always stays in DFU. It has no application
handoff, independent recovery-key check, watchdog handling, hardened request
bounds, image validation or verified completion/commit procedure.

This recipe measures whether existing USB DFU code and the existing
HT32F52352 board/startup fit within the MD770 application window. It does
not establish functional USB or flash-controller behaviour on hardware.

The protocol source is from OpenKemove/kemove_lpc_dfu at the revision in
result.json (GPL-3.0). The unchanged HT32 FMC backend is fetched from
hansemro/ht32_usb_dfu for private evaluation. Its licensing remains
unresolved. The patch does not redistribute that backend or firmware.
Do not publish a derived implementation until its provenance is resolved.

With the required GNU Arm compiler, GNU make, patch, Git and Python 3:

```sh
./build.sh /path/to/qmk_firmware /path/to/new-build-directory
```

On NixOS an optional build environment is:

```sh
nix-shell -p gcc-arm-embedded gnumake git patch python3 --run './build.sh /path/to/qmk_firmware /path/to/new-build-directory'
```

The supplied checkout must match the recorded QMK and submodule revisions.
The recipe writes only to the new build directory, and has no flash or USB
command. It retrieves the existing projects, substitutes the licensed
protocol files, reuses the checked QMK ChibiOS configuration and linker
layout, applies adapt.patch, then compiles and checks the resulting image.

result.json records section sizes, geometry, toolchain and the original
prototype hashes. Executable debug paths can change the ELF hash across
build directories; the binary hash is the useful reproducibility check.
The available heap is included in GNU size's BSS total. Static RAM plus
two 1 KiB stacks occupies 5,032 bytes; the remaining 11,320 bytes is heap.

The compatibility record contains the documented right-half updater ABI.
The left half needs its own signature 0x04046080 at the same address.
A QMK application would need vectors relocated to 0x6000 or 0x8000 and its
bootloader-entry request routed to this secondary loader. The original
protected factory IAP at 0x0000..0x2fff would remain unchanged.

The 0x6000 boundary leaves 1,160 bytes for missing loader behaviour.
A 0x8000 boundary leaves more development space while still allowing
95.5 KiB of QMK application code below the option page. Neither boundary
is a final design decision.

A second build from clean checkouts using this exact recipe produced the
same 10,616-byte binary and SHA-256 as the original experiment.
