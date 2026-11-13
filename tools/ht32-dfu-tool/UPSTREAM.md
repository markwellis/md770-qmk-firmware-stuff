# Host utility provenance

Upstream: <https://github.com/hansemro/ht32-dfu-tool>

Version: 0.2.2. Base revision: `848fc071c8f2429bf41f3bd40c60ec9bc5433b72`.
The upstream GPL-2.0-or-later licence is preserved in `LICENSE`.

The local source adds exact transfer checks, strict acknowledgement
accounting, paired-page protection for HT32F52342/52352, v1.03 model
decoding, immutable write/verify input, full byte readback, same-port
reconnection and documented option-word programming with checksum last.
It validates option checksums and the erased protection state after reset.
Programming failures stop instead of automatically retrying a flash word.

The MD770 v1.03 information/protection preflight passed. Six host regression
tests and strict Clippy passed. Stock restoration passed on the recorded
right half, including full byte and option-word readback, cold boot,
typing and updater checks. Its interrupted SEL2 contact required cold
ROM re-entry and a continuation without `--mass-erase`.
The separate CRC-only reader has four host tests covering both recorded
information anchors. Its default targets right US 7.02; `--left` selects
left US 4.01. Both halves have passed 37 live calibration checks. The
reader cannot erase or program flash.

The known full recovery image is 130,560 bytes. It uses 2,511 write
requests, including a final batch of 21 and a final payload of 40 bytes.
Full byte readback requires 2,040 64-byte reads before protection is enabled.
