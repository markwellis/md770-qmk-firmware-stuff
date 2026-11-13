#!/usr/bin/env python3
"""Prepare a recorded MD770 recovery package without accessing USB."""

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


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--updater", type=Path, required=True)
parser.add_argument("--iap", type=Path, required=True)
parser.add_argument("--binary", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--half", choices=("right", "left"), default="right")
parser.add_argument("--option-reply", type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
updater = args.updater
iap_path = args.iap
tool = repo / "tools/ht32-dfu-tool"
left = args.half == "left"
prefix = "mistel-md770-left" if left else "mistel-md770"
group = "g3e8" if left else "g4e8"
extractor = runpy.run_path(str(repo / "scripts/md770-extract.py"))
with tempfile.TemporaryDirectory(prefix="md770-package-extract-") as temporary:
    extraction = extractor["extract"](updater, Path(temporary))
    app = (Path(temporary) / f"{updater.stem}.{group}.firmware.bin").read_bytes()
    version = (Path(temporary) / f"{updater.stem}.{group}.version.bin").read_bytes()
iap = iap_path.read_bytes()
live = json.loads((repo / f"docs/{prefix}-live-info.json").read_text())
rom = json.loads((repo / f"docs/{prefix}-rom-info.json").read_text())
check = json.loads((repo / f"docs/{prefix}-updater-check.json").read_text())
restore = json.loads((repo / f"docs/{prefix}-stock-restore.json").read_text())
if left:
    backup = json.loads((repo / f"docs/{prefix}-iap-backup.json").read_text())
    _require(
        backup["passes_identical"]
        and backup["second_fresh_session_pass_obtained"]
        and backup["calibration_checks_passed"] == 37
        and all(
            backup[key]["all_24_page_crcs_matched"]
            and backup[key]["whole_region_crc_matched"]
            for key in ("pass_1", "pass_2")
        ),
        "Two verified left-IAP reads are required",
    )
    _require(
        rom["info_transfer_bytes"] == rom["option_transfer_bytes"] == 64
        and rom["option_checksum_valid"]
        and rom["normal_usb_return_verified"]
        and rom["model_word"] == "0x00052352"
        and rom["rom_version"] == "0x0103"
        and rom["page_size_bytes"] == 512
        and rom["usable_flash_pages"] == 255,
        "Left ROM preflight is incomplete",
    )
    expected_tool_sha256 = rom["tool_sha256"]
else:
    preflight = json.loads((repo / "docs/mistel-md770-rom-preflight.json").read_text())
    _require(
        restore["restoration_verified"]
        and restore["full_main_flash_readback_matched"]
        and restore["documented_protection_words_readback_matched"]
        and restore["post_restore_updater_entry_checksums_and_return_verified"],
        "Stock-restoration verification is incomplete",
    )
    _require(
        preflight["restore_client_info_preflight_passed"]
        and preflight["all_37_samples_matched"],
        "ROM preflight is incomplete",
    )
    expected_tool_sha256 = preflight["restore_client_sha256"]
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
    == (
        "29a4cb40d5b0a4c0280a39bbaa0c58d7f6b93969e8499b4597923b9482565614"
        if left
        else "61e377ee21584a7bce42a2a9532a40b6682ba9d1a095cfe08708555ab7e5bd4e"
    ),
    "Wrong stock-IAP backup",
)
_require(
    len(app) == (36404 if left else 49008)
    and hashlib.sha256(app).hexdigest()
    == (
        "febc84d9dc1fd23152218232839279ecb59f255615a6d6c5b4d951a848c85064"
        if left
        else "8fafdca096756f23626802d5b586b270b0bd512fe5d1c0327db4eafcd4f689b2"
    ),
    "Wrong stock US application for the selected half",
)
_require(len(version) == 180, "Wrong version-template length")
_require(
    iap[0x400:0x434] == bytes.fromhex(live["boot_info_hex"]),
    "IAP information differs from the live record",
)
version_page = version + b"\xff" * (512 - len(version))
_require(
    version_page[:480] == bytes.fromhex(live.get("version_page_hex", "")),
    "A matching 480-byte live version-page read is required",
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
    hashlib.sha256(main).hexdigest() == restore["image_sha256"],
    "Restoration evidence refers to a different image",
)
_require(
    hashlib.sha256(main).hexdigest()
    == (
        "eb6eb73f6d929958bb7c0d72d5f3d919c20cf96985284a3c55ea8717d5c85b28"
        if left
        else "8d961215101b93760d20dfbc717f6cd6a2fa879fae26e71a478089df39095ffd"
    ),
    "Reconstructed image differs from the independently reviewed hash",
)
protection = {
    key: rom["option_words"][key] for key in ("pp0", "pp1", "pp2", "pp3", "cp")
}
protection["checksum_stored"] = (
    rom["option_checksum"] if left else rom["option_words"]["checksum_stored"]
)
_require(
    sum(int(protection[key], 16) for key in ("pp0", "pp1", "pp2", "pp3", "cp"))
    & 0xFFFFFFFF
    == int(protection["checksum_stored"], 16),
    "Invalid original option checksum",
)
option_reply = (
    args.option_reply.read_bytes()
    if args.option_reply
    else bytes.fromhex(rom.get("option_reply_hex", ""))
)
_require(
    len(option_reply) == 64,
    "Supply the original 64-byte option reply for the left half",
)
_require(
    struct.unpack_from("<5I", option_reply)
    == tuple(int(protection[key], 16) for key in ("pp0", "pp1", "pp2", "pp3", "cp"))
    and struct.unpack_from("<I", option_reply, 32)[0]
    == int(protection["checksum_stored"], 16),
    "Option reply differs from the documented protection",
)
files = {
    "stock-iap.bin": iap,
    "stock-application.bin": app,
    "stock-version-page.bin": version_page,
    "stock-main-flash.bin": bytes(main),
    "observed-rom-option-reply.bin": option_reply,
    updater.name: updater.read_bytes(),
    "original-protection.json": (json.dumps(protection, indent=2) + "\n").encode(),
    "extractor-manifest.json": (json.dumps(extraction, indent=2) + "\n").encode(),
    "README.md": (repo / f"docs/{args.half}-recovery-package.md").read_bytes(),
    "nix-runtime.nar.zst": args.runtime.read_bytes(),
}
record_names = (
    "mistel-md770-live-info.json",
    "mistel-md770-rom-info.json",
    "mistel-md770-iap-backup.json",
    "mistel-md770-updater-check.json",
    "mistel-md770-rom-preflight.json",
    "mistel-md770-stock-restore.json",
    "mistel-md770-stock-restore-updater-check.json",
    "mistel-md770-stock-restore-preflight.txt",
    "mistel-md770-stock-restore-program.txt",
    "mistel-md770-stock-restore-cold-preflight.txt",
    "mistel-md770-stock-restore-continuation.txt",
)
if left:
    record_names = tuple(
        f"{prefix}-{suffix}.json"
        for suffix in (
            "live-info",
            "rom-info",
            "iap-backup",
            "updater-check",
            "stock-restore",
        )
    )
for name in record_names:
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
    == expected_tool_sha256
    == restore["utility_sha256"],
    "Use the ROM-preflighted binary or record a fresh preflight first",
)
manifest: dict[str, Any] = {
    "date": datetime.now(timezone.utc).date().isoformat(),
    "unit": "MD770 RGB BT left half, KB041A, US V1.04.01"
    if left
    else "red-switch MD770 RGB BT right half, KB0419, US V1.07.02",
    "image_kind": "Reconstructed restoration image; not an original full-flash dump",
    "layout": {
        "iap": "0x0000..0x2fff",
        "version": "0x3000..0x31ff",
        "app": f"0x3200..0x{0x3200 + len(app) - 1:04x}",
        "erased_padding": f"0x{0x3200 + len(app):04x}..0x1fdff",
        "option_page_excluded": "0x1fe00..0x1ffff",
    },
    "version_page_final_32_bytes": "ff padding from the canonical updater template, not directly read",
    "tool_upstream": "https://github.com/hansemro/ht32-dfu-tool",
    "tool_upstream_revision": "848fc071c8f2429bf41f3bd40c60ec9bc5433b72",
    "rom_writer_preflight_verified": True,
    "runtime_platform": "x86_64-linux with Nix; exact shared-library closure included",
    "restoration_hardware_tested": restore["restoration_verified"],
    "restoration_record": f"{prefix}-stock-restore.json",
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
