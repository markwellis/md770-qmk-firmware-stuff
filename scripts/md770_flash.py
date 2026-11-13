#!/usr/bin/env python3
"""Install a US-layout MD770 RGB BT application through its stock USB updater."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import struct
import time
import zlib

import md770_updater_check as updater


UPDATE_SIZE = 0x1CE00
APP_OFFSET = 0x200
BLOCK_SIZE = 52
VERSION_COMMIT = 0xB0


def validate_inputs(image: bytes, saved: dict, half: str) -> tuple[bytes, bytes]:
    """Reject incompatible images and metadata before opening any device."""
    pid, _, signature, _ = updater.APPLICATIONS[half]
    info = bytes.fromhex(saved["boot_info_hex"])
    version = bytes.fromhex(saved["version_page_hex"])
    if len(info) != 52 or info[8:16] != struct.pack(
        "<HHI", 0x04D9, pid | 0x1000, signature
    ):
        raise ValueError("Saved boot information belongs to a different keyboard")
    if info[32:38] != struct.pack("<HHH", APP_OFFSET, 231, 512):
        raise ValueError("Unsupported update geometry")
    if len(image) % 4 or not 0x1000 <= len(image) <= UPDATE_SIZE - APP_OFFSET:
        raise ValueError(
            "Application must be word-aligned and fit below the option page"
        )
    sp, reset = struct.unpack_from("<II", image)
    if sp % 8 or not 0x20000000 < sp <= 0x20003FE0:
        raise ValueError("Invalid application stack pointer")
    if not reset & 1 or not 0x3200 <= (reset & ~1) < 0x3200 + len(image):
        raise ValueError("Invalid application reset vector")
    if struct.unpack_from("<III", image, 0x9F8) != (signature, 0x34000001, 0x00020004):
        raise ValueError("Application has no matching stock-IAP compatibility record")
    if len(version) != 480 or version[0xB4:] != b"\xff" * (480 - 0xB4):
        raise ValueError("Unsupported saved version page")
    marker = struct.unpack_from("<I", version, VERSION_COMMIT)[0]
    count = marker >> 18
    if marker & 0x3FFFF != 0x5AA5 or not 1 <= count <= 14:
        raise ValueError("Invalid version-page commit marker")
    if any(
        struct.unpack_from("<I", version, 0x78 + i * 4)[0] == 0xFFFFFFFF
        for i in range(count)
    ):
        raise ValueError("Incomplete version-page metadata")
    if version[0x90:0x94] != struct.pack("<HH", 0x04D9, pid):
        raise ValueError("Version page belongs to a different half")
    return info, version


def encode(image: bytes) -> bytes:
    return bytes(
        value ^ updater.XOR_KEY[i % BLOCK_SIZE] for i, value in enumerate(image)
    )


def write_request(fd: int, command: int, subcommand: int, data: bytes) -> bytes:
    """Keep modifying reports separate from the read-only diagnostic whitelist."""
    valid = False
    expected = (command, subcommand)
    if (command, subcommand) == (0x1D, 0) and len(data) == 8:
        valid = struct.unpack("<II", data) == (0, UPDATE_SIZE)
    elif command == 0x1E and subcommand in (0, 1) and len(data) == 4:
        pointer = struct.unpack("<I", data)[0]
        valid = (
            pointer == 0xFFFFFFFF
            if subcommand == 0
            else pointer < UPDATE_SIZE and pointer % 4 == 0
        )
    elif command == 0x1F and subcommand == len(data):
        valid = 0 < len(data) <= BLOCK_SIZE and len(data) % 4 == 0
        expected = (0x1E, 2)
    if not valid:
        raise ValueError("Invalid update report")
    report = b"\0" + (struct.pack("<BBH", command, subcommand, 0) + data).ljust(
        64, b"\0"
    )
    if os.write(fd, report) != 65:
        raise RuntimeError("Incomplete update report")
    if not select.select([fd], [], [], 15)[0]:
        raise RuntimeError(f"Timeout for update report {command:02x}/{subcommand:02x}")
    return updater.reply_data(*expected, os.read(fd, 64))


def write_region(fd: int, pointer: int, data: bytes) -> None:
    if pointer % 4 or len(data) % 4 or pointer < 0 or pointer + len(data) > UPDATE_SIZE:
        raise ValueError("Invalid update range")
    if pointer < APP_OFFSET < pointer + len(data):
        raise ValueError("Write crosses the version/application boundary")
    for subcommand, argument in [(1, pointer), (0, 0xFFFFFFFF)]:
        reply = write_request(fd, 0x1E, subcommand, struct.pack("<I", argument))
        if struct.unpack_from("<I", reply)[0] != pointer:
            raise RuntimeError("Update pointer did not match")
    for offset in range(0, len(data), BLOCK_SIZE):
        chunk = data[offset : offset + BLOCK_SIZE]
        reply = write_request(fd, 0x1F, len(chunk), chunk)
        if struct.unpack_from("<I", reply)[0] != pointer + offset + len(chunk):
            raise RuntimeError(
                f"Write acknowledgement failed at relative offset {pointer + offset:#x}"
            )


def program(fd: int, image: bytes, version: bytes, report: dict) -> None:
    encoded = encode(image)
    report["erase_attempted"] = True
    reply = write_request(fd, 0x1D, 0, struct.pack("<II", 0, UPDATE_SIZE))
    if struct.unpack_from("<II", reply) != (0, UPDATE_SIZE):
        raise RuntimeError(
            "Updater did not acknowledge erasing the complete update area"
        )
    report["erase_verified"] = True
    write_region(fd, APP_OFFSET, encoded)
    arguments = struct.pack("<II", APP_OFFSET, len(encoded))
    expected_sum = (
        sum(word[0] for word in struct.iter_unpack("<I", encoded)) & 0xFFFFFFFF
    )
    for subcommand, expected in [(1, expected_sum), (2, zlib.crc32(encoded))]:
        actual = struct.unpack_from(
            "<I", updater.request(fd, 0x1D, subcommand, arguments)
        )[0]
        if actual != expected:
            raise RuntimeError(
                f"Application checksum {subcommand} differs: {actual:08x} != {expected:08x}"
            )
    report["application_checksums_verified"] = True
    write_region(fd, 0, version[:VERSION_COMMIT])
    pending = version[:VERSION_COMMIT] + b"\xff" * (480 - VERSION_COMMIT)
    if updater.read_version_page(fd) != pending:
        raise RuntimeError("Version page differs before committing its validity marker")
    write_region(fd, VERSION_COMMIT, version[VERSION_COMMIT : VERSION_COMMIT + 4])
    if updater.read_version_page(fd) != version:
        raise RuntimeError("Committed version page differs from the saved page")
    report["version_page_verified"] = True


def usb_device(path: str) -> Path:
    for parent in (
        (Path("/sys/class/hidraw") / Path(path).name / "device").resolve().parents
    ):
        if (parent / "idVendor").exists():
            return parent
    raise RuntimeError("Cannot identify the physical USB device")


def run(image: bytes, info: bytes, version: bytes, half: str, report: dict) -> None:
    pid = updater.APPLICATIONS[half][0]
    try:
        path, physical = updater.find_device(pid)
        in_application = True
    except FileNotFoundError:
        path, physical = updater.find_device(pid | 0x1000)
        in_application = False
    node = usb_device(path)
    if in_application:
        fd = updater.open_device(path)
        try:
            if (
                updater.request(fd, 0x12, 2)[0] != 1
                or updater.request(fd, 0x12, 0)[:52] != info
            ):
                raise RuntimeError("Unexpected application identity")
            updater.send(fd, 0x11, 0)
        finally:
            os.close(fd)
        path, _ = updater.wait_device(pid | 0x1000, physical)
    fd = updater.open_device(path)
    try:
        if (
            updater.request(fd, 0x12, 2)[0] != 0
            or updater.request(fd, 0x12, 0)[:52] != info
        ):
            raise RuntimeError("Unexpected stock updater identity")
        current = updater.read_version_page(fd)
        if any(
            actual not in (expected, 0xFF) for actual, expected in zip(current, version)
        ):
            raise RuntimeError("Live version page differs from the supplied backup")
        report["iap_preflight_passed"] = True
        program(fd, image, version, report)
        updater.send(fd, 0x11, 1)
        report["application_boot_requested"] = True
    finally:
        os.close(fd)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            identity = {
                key: (node / key).read_text().strip()
                for key in ("idVendor", "idProduct", "product", "bcdDevice")
            }
            if identity["idVendor"] == "04d9" and identity["idProduct"] == f"{pid:04x}":
                report["normal_usb_identity"] = identity
                stock = (
                    hashlib.sha256(image).hexdigest() == updater.APPLICATIONS[half][1]
                )
                expected_product = (
                    ("MD770BT-M" if half == "right" else "MD770BT-S")
                    if stock
                    else "MD770 RGB BT (wired QMK)"
                )
                expected_revision = (
                    ("0710" if half == "right" else "0410") if stock else "0010"
                )
                if (
                    identity["product"] != expected_product
                    or identity["bcdDevice"] != expected_revision
                ):
                    raise RuntimeError("Returned application USB descriptors differ")
                report["normal_usb_return_verified"] = True
                return
        except FileNotFoundError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Application did not return on the original USB port")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "live_info", type=Path, help="Saved boot information and 480-byte version page"
    )
    parser.add_argument("--half", choices=updater.APPLICATIONS, default="right")
    parser.add_argument(
        "--flash",
        action="store_true",
        help="Erase and program the application/version area",
    )
    parser.add_argument(
        "--output", type=Path, help="New result JSON file; required with --flash"
    )
    args = parser.parse_args()
    image = args.image.read_bytes()
    info, version = validate_inputs(
        image, json.loads(args.live_info.read_text()), args.half
    )
    report = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "half": args.half,
        "application_bytes": len(image),
        "application_sha256": hashlib.sha256(image).hexdigest(),
        "version_page_sha256": hashlib.sha256(version).hexdigest(),
        "write_scope": "application and version pages only",
        "option_page_modified": False,
        "erase_attempted": False,
        "success": False,
    }
    if not args.flash:
        print(json.dumps(report, indent=2))
        print(
            "Offline validation passed; no USB device opened. Add --flash --output RESULT.json to program."
        )
        return
    if args.output is None:
        parser.error("--flash requires --output")
    with args.output.open("x") as output:
        try:
            run(image, info, version, args.half, report)
            report["success"] = True
        except BaseException as error:
            report["error"] = str(error)
            raise
        finally:
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
