#!/usr/bin/env python3
"""Query or briefly flash the Mistel MD770BT-M backlight over USB HID."""

import argparse
import os
from pathlib import Path
import select
import signal
import sys
import time


def find_device():
    for device in Path('/sys/class/hidraw').glob('hidraw*'):
        properties = dict(
            line.split('=', 1)
            for line in (device / 'device/uevent').read_text().splitlines()
            if '=' in line
        )
        if (
            properties.get('HID_ID') == '0003:000004D9:00000419'
            and properties.get('HID_PHYS', '').endswith('/input1')
            and (device / 'device/report_descriptor').read_bytes().startswith(
                bytes.fromhex('06 00 ff 09 01 a1 01')
            )
        ):
            return '/dev/' + device.name
    raise RuntimeError('No MD770BT-M vendor HID interface found')


def request(fd, payload):
    packet = bytes(payload).ljust(64, b'\0')
    if len(packet) != 64:
        raise ValueError('A report must contain at most 64 bytes')
    if os.write(fd, b'\0' + packet) != 65:
        raise RuntimeError('Incomplete HID write')
    if not select.select([fd], [], [], 2)[0]:
        raise RuntimeError('Keyboard reply timed out')
    reply = os.read(fd, 64)
    if len(reply) != 64 or reply[0] != packet[0]:
        raise RuntimeError('Unexpected keyboard reply: ' + reply.hex())
    if packet[0] != 0x41 and reply[:4] != packet[:4]:
        raise RuntimeError('Keyboard returned a different report header')
    return reply


def commit(fd):
    request(fd, [0xC0, 0xF0, 0, 0, 0])


def hold_colour(fd, level):
    packet = [0xC0, 0, 0, 0, level, level, level]
    request(fd, packet)
    deadline = time.monotonic() + 0.5
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.005, remaining))
        if time.monotonic() < deadline:
            # The stock renderer periodically overwrites the direct RGB buffer.
            request(fd, packet)


def flash(fd, mode):
    if mode[1] != 0:
        raise RuntimeError('Restore normal lighting mode before testing')
    colours = b''.join(
        request(fd, [0xC1, 0, page, 0])[4:] for page in range(5)
    )[:288]
    try:
        request(fd, [0x41, 2, 0, 0])
        request(fd, [0xC0, 0xF0, 0, 0, 1])
        for _ in range(5):
            for level in (255, 0):
                hold_colour(fd, level)
    finally:
        try:
            commit(fd)
            for start in range(0, 96, 20):
                count = min(20, 96 - start)
                request(
                    fd,
                    bytes([0xC0, 0xC0 + count - 1, start, 0])
                    + colours[start * 3 : (start + count) * 3],
                )
            commit(fd)
        finally:
            request(fd, mode)
    if request(fd, [0x41, 0xFF])[:4] != mode:
        raise RuntimeError('Lighting mode was not restored')


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['info', 'flash'])
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    device = find_device()
    fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    try:
        while select.select([fd], [], [], 0)[0]:
            os.read(fd, 64)
        mode = request(fd, [0x41, 0xFF])[:4]
        print(f'{device}: mode {mode[1]}, timeout {int.from_bytes(mode[2:4], "little")}', flush=True)
        if args.action == 'flash':
            flash(fd, mode)
            print('Five flashes completed; original lighting mode restored.')
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        sys.exit(str(error))
