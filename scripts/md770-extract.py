#!/usr/bin/env python3
"""Extract MD770 application images from a Cheng Yong maaV105 updater offline."""

import argparse
import hashlib
import json
from pathlib import Path
import struct


TRAILER_SIZE = 0x2B58
XOR_KEY = struct.pack(
    '<13I',
    0xE7C29474, 0x79084B10, 0x53D54B0D, 0xFC1E8F32, 0x48E81A9B,
    0x773C808E, 0xB7483552, 0xD9CB8C76, 0x2A8C8BC6, 0x0967ADA8,
    0xD4520F5C, 0xD0C3279D, 0xEAC091C5,
)


def decode(data):
    block = bytearray(data)
    for offset in range(0, len(block) - 5, 5):
        block[offset], block[offset + 4] = block[offset + 4], block[offset]
    for offset in range(0, len(block) - 1, 2):
        block[offset], block[offset + 1] = block[offset + 1], block[offset]
    return bytes((((value - 7) << 4) + (value >> 4)) & 255 for value in block)


def extract(source, output):
    data = source.read_bytes()
    if len(data) < TRAILER_SIZE:
        raise ValueError('File is shorter than the updater trailer')
    trailer = decode(data[-TRAILER_SIZE:])
    if b'.maaV105\0' not in trailer[-24:]:
        raise ValueError('Not a supported maaV105 updater')
    cursor = len(data) - TRAILER_SIZE
    entries = []
    for group in range(5):
        for entry in range(9):
            offset = 0x22D8 - group * 0x6E0 - entry * 0x50
            firmware_size, version_size = struct.unpack_from('<II', trailer, offset)
            label = trailer[offset + 8 : offset + 68].decode('utf-16-le').split('\0')[0]
            for kind, size in [('version', version_size), ('firmware', firmware_size)]:
                if not size:
                    continue
                if size > cursor or cursor - size < 2:
                    raise ValueError('Payload extends beyond the updater')
                cursor -= size
                payload = decode(data[cursor : cursor + size])
                if kind == 'firmware':
                    payload = bytes(
                        value ^ XOR_KEY[index % len(XOR_KEY)]
                        for index, value in enumerate(payload)
                    )
                    if len(payload) < 8:
                        raise ValueError('Firmware has no vector table')
                    stack, reset = struct.unpack_from('<II', payload)
                    if stack != 0x20003FE0 or reset != 0x32C1:
                        raise ValueError('Unexpected firmware vector table')
                name = f'{source.stem}.g{group}e{entry}.{kind}.bin'
                entries.append((name, payload, label))
    if not entries:
        raise ValueError('Updater contains no payloads')
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        'source': source.name,
        'source_sha256': hashlib.sha256(data).hexdigest(),
        'images': [],
    }
    for name, payload, label in entries:
        target = output / name
        if target.exists() and target.read_bytes() != payload:
            raise FileExistsError(f'Refusing to replace different contents: {target}')
        target.write_bytes(payload)
        manifest['images'].append({
            'file': name,
            'layout': label,
            'length': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest(),
        })
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('updater', type=Path)
    parser.add_argument('output_directory', type=Path)
    args = parser.parse_args()
    manifest = extract(args.updater, args.output_directory)
    text = json.dumps(manifest, indent=2) + '\n'
    (args.output_directory / f'{args.updater.stem}.manifest.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
