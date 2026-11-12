#!/usr/bin/env python3
"""Prepare the recorded right-half recovery package without accessing USB."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
from typing import Any


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


parser = argparse.ArgumentParser(
    description="Prepare the known US 7.02 right-half recovery package offline"
)
parser.add_argument("output", type=Path)
parser.add_argument("--updater", type=Path, required=True)
parser.add_argument("--iap", type=Path, required=True)
parser.add_argument("--binary", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
updater = args.updater
iap_path = args.iap
tool = repo / "tools/ht32-dfu-tool"
extractor = runpy.run_path(str(repo / "scripts/md770-extract.py"))
with tempfile.TemporaryDirectory(prefix="md770-package-extract-") as temporary:
    extraction = extractor["extract"](updater, Path(temporary))
    app = (Path(temporary) / f"{updater.stem}.g4e8.firmware.bin").read_bytes()
    version = (Path(temporary) / f"{updater.stem}.g4e8.version.bin").read_bytes()
iap = iap_path.read_bytes()
live = json.loads((repo / "docs/mistel-md770-live-info.json").read_text())
rom = json.loads((repo / "docs/mistel-md770-rom-info.json").read_text())
check = json.loads((repo / "docs/mistel-md770-updater-check.json").read_text())
preflight = json.loads((repo / "docs/mistel-md770-rom-preflight.json").read_text())
_require(
    preflight["restore_client_info_preflight_passed"]
    and preflight["all_37_samples_matched"],
    "ROM preflight is incomplete",
)
_require(
    check["success"] and check["normal_usb_return_verified"],
    "Stock-updater check is incomplete",
)
_require(
    check["encoded_sum_matches"] and check["encoded_crc_matches"],
    "Installed application does not match the updater",
)
_require(
    not check["flash_written_or_erased"] and not check["protection_changed"],
    "Unexpected programming during the diagnostic",
)
_require(
    len(iap) == 0x3000
    and hashlib.sha256(iap).hexdigest()
    == "61e377ee21584a7bce42a2a9532a40b6682ba9d1a095cfe08708555ab7e5bd4e",
    "Wrong stock-IAP backup",
)
_require(
    len(app) == 49008
    and hashlib.sha256(app).hexdigest()
    == "8fafdca096756f23626802d5b586b270b0bd512fe5d1c0327db4eafcd4f689b2",
    "Wrong US 7.02 application",
)
_require(len(version) == 180, "Wrong version-template length")
_require(
    iap[0x400:0x434] == bytes.fromhex(live["boot_info_hex"]),
    "IAP information differs from the live record",
)
version_page = version + b"\xff" * (512 - len(version))
_require(
    version_page[:480] == bytes.fromhex(live["version_page_hex"]),
    "Version page differs from its live read",
)
_require(
    struct.unpack_from("<I", version_page, 0xB0)[0] == 0x001C5AA5,
    "Wrong version-page boot marker",
)
main = bytearray(b"\xff" * 0x1FE00)
main[:0x3000] = iap
main[0x3000:0x3200] = version_page
main[0x3200 : 0x3200 + len(app)] = app
_require(
    hashlib.sha256(main).hexdigest()
    == "8d961215101b93760d20dfbc717f6cd6a2fa879fae26e71a478089df39095ffd",
    "Reconstructed image differs from the independently reviewed hash",
)
protection = {
    key: rom["option_words"][key]
    for key in ("pp0", "pp1", "pp2", "pp3", "cp", "checksum_stored")
}
_require(
    sum(int(protection[key], 16) for key in ("pp0", "pp1", "pp2", "pp3", "cp"))
    & 0xFFFFFFFF
    == int(protection["checksum_stored"], 16),
    "Invalid original option checksum",
)
files = {
    "stock-iap.bin": iap,
    "stock-application.bin": app,
    "stock-version-page.bin": version_page,
    "stock-main-flash.bin": bytes(main),
    "observed-rom-option-reply.bin": bytes.fromhex(rom["option_reply_hex"]),
    updater.name: updater.read_bytes(),
    "original-protection.json": (json.dumps(protection, indent=2) + "\n").encode(),
    "extractor-manifest.json": (json.dumps(extraction, indent=2) + "\n").encode(),
    "README.md": (repo / "docs/right-recovery-package.md").read_bytes(),
    "nix-runtime.nar.zst": args.runtime.read_bytes(),
}
for name in (
    "mistel-md770-live-info.json",
    "mistel-md770-rom-info.json",
    "mistel-md770-iap-backup.json",
    "mistel-md770-updater-check.json",
    "mistel-md770-rom-preflight.json",
):
    files[name] = (repo / "docs" / name).read_bytes()
for name in (
    "Cargo.toml",
    "Cargo.lock",
    "LICENSE",
    "UPSTREAM.md",
    "src/main.rs",
    "src/device.rs",
    "src/command.rs",
    "src/bin/md770-rom-crc.rs",
):
    files["tool-source/" + name] = (tool / name).read_bytes()
files["ht32-dfu-tool"] = args.binary.read_bytes()
_require(
    hashlib.sha256(files["ht32-dfu-tool"]).hexdigest()
    == preflight["restore_client_sha256"],
    "Use the ROM-preflighted binary or record a fresh preflight first",
)
manifest: dict[str, Any] = {
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "unit": "red-switch MD770 RGB BT right half, KB0419, US V1.07.02",
    "image_kind": "Reconstructed restoration image; not an original full-flash dump",
    "layout": {
        "iap": "0x0000..0x2fff",
        "version": "0x3000..0x31ff",
        "app": "0x3200..0xf16f",
        "erased_padding": "0xf170..0x1fdff",
        "option_page_excluded": "0x1fe00..0x1ffff",
    },
    "version_page_final_32_bytes": "ff padding from the canonical updater template, not directly read",
    "tool_upstream": "https://github.com/hansemro/ht32-dfu-tool",
    "tool_upstream_revision": "848fc071c8f2429bf41f3bd40c60ec9bc5433b72",
    "rom_writer_preflight_verified": True,
    "runtime_platform": "x86_64-linux with Nix; exact shared-library closure included",
    "restoration_hardware_tested": False,
    "stock_settings_preservation_required": False,
    "files": {
        name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in files.items()
    },
}
args.output.mkdir(parents=True, exist_ok=False)
for name, data in files.items():
    destination = args.output / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(data)
    if name == "ht32-dfu-tool":
        destination.chmod(0o755)
    _require(destination.read_bytes() == data, f"Written file differs: {name}")
with (args.output / "manifest.json").open("x") as output:
    json.dump(manifest, output, indent=2)
    output.write("\n")
hash_lines = [
    f"{hashlib.sha256((args.output / name).read_bytes()).hexdigest()}  {name}"
    for name in sorted([*files, "manifest.json"])
]
with (args.output / "SHA256SUMS").open("x") as output:
    output.write("\n".join(hash_lines) + "\n")
print(
    json.dumps(
        {
            "output": str(args.output),
            "main_sha256": manifest["files"]["stock-main-flash.bin"]["sha256"],
            "files": len(files),
        },
        indent=2,
    )
)
