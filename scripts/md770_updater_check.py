#!/usr/bin/env python3
"""Check an MD770 stock updater and return to the application."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import struct
import time


APPLICATIONS = {
    "right": (
        0x0419,
        "8fafdca096756f23626802d5b586b270b0bd512fe5d1c0327db4eafcd4f689b2",
        0x040450C0,
        0x6785727C,
    ),
    "left": (
        0x041A,
        "febc84d9dc1fd23152218232839279ecb59f255615a6d6c5b4d951a848c85064",
        0x04046080,
        0x90309827,
    ),
}
XOR_KEY = struct.pack(
    "<13I",
    0xE7C29474,
    0x79084B10,
    0x53D54B0D,
    0xFC1E8F32,
    0x48E81A9B,
    0x773C808E,
    0xB7483552,
    0xD9CB8C76,
    0x2A8C8BC6,
    0x0967ADA8,
    0xD4520F5C,
    0xD0C3279D,
    0xEAC091C5,
)
ALLOWED = frozenset(
    [(0x11, 0), (0x11, 1), (0x12, 0), (0x12, 1), (0x12, 2), (0x1D, 1), (0x1D, 2)]
)


def packet(command: int, subcommand: int, data: bytes = b"") -> bytes:
    """Build an allowed query or software-reset report, including report ID."""
    if (command, subcommand) not in ALLOWED:
        raise ValueError("Operation is outside this diagnostic whitelist")
    if len(data) != (8 if command == 0x1D else 0):
        raise ValueError("Unexpected argument length")
    return b"\0" + (struct.pack("<BBH", command, subcommand, 0) + data).ljust(64, b"\0")


def reply_data(command: int, subcommand: int, reply: bytes) -> bytes:
    """Require a complete reply with the matching command and success status."""
    if len(reply) != 64 or reply[:4] != struct.pack("<BBH", command, subcommand, 0):
        raise RuntimeError(
            f"Unexpected reply to {command:02x}/{subcommand:02x}: {reply.hex()}"
        )
    return reply[4:]


def find_device(pid: int, physical: str | None = None) -> tuple[str, str]:
    """Find one vendor HID interface, optionally restricted to its USB port."""
    matches = []
    for device in Path("/sys/class/hidraw").glob("hidraw*"):
        try:
            properties = dict(
                line.split("=", 1)
                for line in (device / "device/uevent").read_text().splitlines()
                if "=" in line
            )
            descriptor = (device / "device/report_descriptor").read_bytes()
        except FileNotFoundError:
            continue
        location = properties.get("HID_PHYS", "").rsplit("/input", 1)[0]
        if (
            properties.get("HID_ID") == f"0003:000004D9:{pid:08X}"
            and descriptor.startswith(bytes.fromhex("06 00 ff"))
            and location
            and (physical is None or physical == location)
        ):
            matches.append(("/dev/" + device.name, location))
    if len(matches) > 1:
        raise RuntimeError(f"Multiple matching vendor interfaces for 04d9:{pid:04x}")
    if not matches:
        raise FileNotFoundError(f"No vendor interface for 04d9:{pid:04x}")
    return matches[0]


def wait_device(pid: int, physical: str) -> tuple[str, str]:
    """Wait at most ten seconds for the same physical keyboard to re-enumerate."""
    deadline = time.monotonic() + 10
    while True:
        try:
            return find_device(pid, physical)
        except FileNotFoundError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def open_device(path: str) -> int:
    """Open the vendor interface and discard pending reports."""
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        for _ in range(64):
            if not select.select([fd], [], [], 0)[0]:
                return fd
            if len(os.read(fd, 64)) != 64:
                raise RuntimeError("Incomplete pending report")
        raise RuntimeError("Vendor reports did not become idle")
    except BaseException:
        os.close(fd)
        raise


def send(fd: int, command: int, subcommand: int, data: bytes = b"") -> None:
    """Send a complete whitelisted report."""
    if os.write(fd, packet(command, subcommand, data)) != 65:
        raise RuntimeError("Incomplete HID request")


def request(fd: int, command: int, subcommand: int, data: bytes = b"") -> bytes:
    """Query and validate a response within ten seconds."""
    send(fd, command, subcommand, data)
    if not select.select([fd], [], [], 10)[0]:
        raise RuntimeError(f"Timeout for {command:02x}/{subcommand:02x}")
    return reply_data(command, subcommand, os.read(fd, 64))


def return_application(
    physical: str,
    expected_info: bytes,
    report: dict[str, object],
    app_pid: int = 0x0419,
) -> None:
    """Try to leave the IAP and verify the application on the same USB port."""
    try:
        app_path, _ = find_device(app_pid, physical)
    except FileNotFoundError:
        iap_path, _ = wait_device(app_pid | 0x1000, physical)
        fd = open_device(iap_path)
        try:
            send(fd, 0x11, 1)
            report["return_reset_sent"] = True
        finally:
            os.close(fd)
        app_path, _ = wait_device(app_pid, physical)
    app_fd = open_device(app_path)
    try:
        if request(app_fd, 0x12, 2)[0] != 1:
            raise RuntimeError("Application mode did not return")
        if request(app_fd, 0x12, 0)[:52] != expected_info:
            raise RuntimeError("Returned application has different boot information")
        report["normal_usb_return_verified"] = True
    finally:
        os.close(app_fd)


def check(
    image: bytes,
    expected_info: bytes,
    report: dict[str, object],
    app_pid: int = 0x0419,
    expected_crc: int = 0x6785727C,
) -> None:
    """Visit the stock IAP and attempt normal return even if its checks fail."""
    path, physical = find_device(app_pid)
    if not physical:
        raise RuntimeError("Cannot bind the check to a physical USB port")
    entry_attempted = False
    try:
        fd = open_device(path)
        try:
            if request(fd, 0x12, 2)[0] != 1:
                raise RuntimeError("Expected the stock application before entry")
            if request(fd, 0x12, 0)[:52] != expected_info:
                raise RuntimeError("Application boot information changed")
            if request(fd, 0x12, 1)[:4] != bytes.fromhex("04000200"):
                raise RuntimeError("Unexpected application header word")
            entry_attempted = True
            send(fd, 0x11, 0)
            report["entry_reset_sent"] = True
        finally:
            os.close(fd)
        iap_path, _ = wait_device(app_pid | 0x1000, physical)
        report["iap_enumeration_verified"] = True
        fd = open_device(iap_path)
        try:
            if request(fd, 0x12, 2)[0] != 0:
                raise RuntimeError("Expected stock updater mode")
            info = request(fd, 0x12, 0)[:52]
            report["iap_boot_info_hex"] = info.hex()
            if info != expected_info:
                raise RuntimeError(
                    "IAP information differs from the saved application read"
                )
            encoded = bytes(
                value ^ XOR_KEY[index % 52] for index, value in enumerate(image)
            )
            expected_sum = (
                sum(value[0] for value in struct.iter_unpack("<I", encoded))
                & 0xFFFFFFFF
            )
            arguments = struct.pack("<II", 0x200, len(image))
            actual_sum = struct.unpack_from("<I", request(fd, 0x1D, 1, arguments))[0]
            actual_crc = struct.unpack_from("<I", request(fd, 0x1D, 2, arguments))[0]
            report["encoded_sum"] = f"0x{actual_sum:08x}"
            report["encoded_crc32"] = f"0x{actual_crc:08x}"
            report["encoded_sum_matches"] = actual_sum == expected_sum
            report["encoded_crc_matches"] = actual_crc == expected_crc
            if not report["encoded_sum_matches"] or not report["encoded_crc_matches"]:
                raise RuntimeError(
                    "Installed application differs from the decoded vendor image"
                )
        finally:
            os.close(fd)
    except BaseException as error:
        report["check_error"] = str(error)
        raise
    finally:
        if entry_attempted:
            try:
                return_application(physical, expected_info, report, app_pid)
            except BaseException as error:
                report["return_error"] = str(error)
                raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("live_info", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--half", choices=APPLICATIONS, default="right")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to replace {args.output}")
    image = args.image.read_bytes()
    app_pid, app_sha256, signature, expected_crc = APPLICATIONS[args.half]
    if hashlib.sha256(image).hexdigest() != app_sha256:
        raise ValueError(f"Expected the recorded {args.half} US application")
    expected_info = bytes.fromhex(
        json.loads(args.live_info.read_text())["boot_info_hex"]
    )
    if len(expected_info) != 52 or expected_info[8:16] != struct.pack(
        "<HHI", 0x04D9, app_pid | 0x1000, signature
    ):
        raise ValueError(f"Expected the saved {args.half}-half boot information")
    report = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "half": args.half,
        "application_sha256": app_sha256,
        "iap_enumeration_verified": False,
        "normal_usb_return_verified": False,
        "flash_written_or_erased": False,
        "protection_changed": False,
        "success": False,
    }
    try:
        check(image, expected_info, report, app_pid, expected_crc)
        report["success"] = True
    finally:
        with args.output.open("x") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
