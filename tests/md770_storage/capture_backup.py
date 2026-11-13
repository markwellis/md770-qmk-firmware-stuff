import hashlib
import json
import os
from pathlib import Path
import select
import sys
import time

output = Path(sys.argv[1])
if output.exists():
    raise SystemExit('Backup destination exists')
nodes = []
for node in Path('/sys/class/hidraw').glob('hidraw*'):
    try:
        info = (node / 'device/uevent').read_text()
        descriptor = (node / 'device/report_descriptor').read_bytes()
    except FileNotFoundError:
        continue
    if 'HID_ID=0003:000004D9:00000419' in info and descriptor.startswith(bytes.fromhex('0660ff0961')):
        nodes.append(Path('/dev') / node.name)
if len(nodes) != 1:
    raise SystemExit(f'Expected one right MD770 VIA interface, found {len(nodes)}')
fd = os.open(nodes[0], os.O_RDWR | os.O_NONBLOCK)
try:
    while select.select([fd], [], [], 0)[0]:
        os.read(fd, 32)
    passes = []
    for _ in range(2):
        data = bytearray()
        for offset in range(0, 65600, 24):
            count = min(24, 65600 - offset)
            header = bytes([8, 127, 0]) + offset.to_bytes(3, 'big') + bytes([count])
            packet = header.ljust(32, b'\0')
            if os.write(fd, b'\0' + packet) != 33:
                raise SystemExit('Short VIA request write')
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if not select.select([fd], [], [], max(0, deadline - time.monotonic()))[0]:
                    break
                reply = os.read(fd, 32)
                if len(reply) == 32 and reply[:7] == header:
                    if reply[7] != 0:
                        raise SystemExit(f'Flash read rejected at {offset:#x}')
                    data.extend(reply[8:8 + count])
                    break
            else:
                raise SystemExit(f'Flash read timed out at {offset:#x}')
            if len(data) != offset + count:
                raise SystemExit(f'Incomplete flash response at {offset:#x}')
        passes.append(bytes(data))
    if passes[0] != passes[1]:
        raise SystemExit('The two complete flash reads differ')
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(passes[0])
        file.flush()
        os.fsync(file.fileno())
    directory = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    print(json.dumps({'bytes': len(passes[0]), 'sha256': hashlib.sha256(passes[0]).hexdigest(), 'matching_complete_reads': 2, 'external_flash_write_commands_sent': False}))
finally:
    os.close(fd)
