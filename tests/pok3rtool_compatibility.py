import argparse
import hashlib
import json
import struct
import sys
import types
import zlib
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Run pok3rtool against an offline MD770 transport model"
)
parser.add_argument("tool", type=Path, help="pok3rtool checkout with the MD770 IDs")
parser.add_argument(
    "firmware_directory",
    type=Path,
    help="Directory containing both QMK default binaries",
)
args = parser.parse_args()
source = (args.tool / "pok3rtool/cykb.py").read_text()
usb = types.ModuleType("usb")
usb.core = types.ModuleType("usb.core")
usb.core.USBTimeoutError = TimeoutError
sys.modules["usb"] = usb
sys.modules["usb.core"] = usb.core
progress = types.ModuleType("tqdm")
progress.tqdm = lambda x: x
sys.modules["tqdm"] = progress
package = types.ModuleType("pok3rtool")
package.__path__ = []
sys.modules["pok3rtool"] = package
device = types.ModuleType("pok3rtool.device")
device.Device = object
device.find_hid_devices = lambda *a, **kw: []
sys.modules[device.__name__] = device
cykb = types.ModuleType("pok3rtool.cykb")
cykb.__package__ = "pok3rtool"
exec(compile(source, "cykb.py", "exec"), cykb.__dict__)
assert (0x04D9, 0x0419) in cykb.known_devices and (0x04D9, 0x041A) in cykb.known_devices
cykb.time.sleep = lambda _: None


class SimulatedMD770(cykb.CYKB_Device):
    def __init__(self, info, version):
        self.info = info
        self.memory = bytearray(b"\xff" * 0x1CE00)
        self.memory[:480] = version
        self.offset = 0
        self.commands = []
        self.erases = []
        self.reboots = 0

    def send(self, packet):
        assert len(packet) == 64
        cmd, subcmd, status = struct.unpack_from("<BBH", packet)
        assert status == 0
        data = packet[4:]
        self.commands.append((cmd, subcmd))
        self.expected = (cmd, subcmd)
        self.response = b""
        if cmd == 0x12:
            if subcmd == 0:
                self.response = self.info
            elif subcmd == 1:
                self.response = self.memory[0xC00:0xC04]
            elif subcmd == 2:
                self.response = b"\0"
            elif 0x20 <= subcmd < 0x28:
                self.response = self.memory[
                    (subcmd - 0x20) * 60 : (subcmd - 0x20 + 1) * 60
                ]
            else:
                raise AssertionError((cmd, subcmd))
        elif cmd == 0x1D:
            off, length = struct.unpack_from("<II", data)
            assert (
                off % 4 == 0
                and length % 4 == 0
                and length > 0
                and off + length <= len(self.memory)
            ), (off, length)
            if subcmd == 0:
                assert off % 512 == 0
                end = (off + length + 511) // 512 * 512
                assert end <= len(self.memory)
                self.memory[off:end] = b"\xff" * (end - off)
                self.erases.append((off, length, end))
                self.response = struct.pack("<II", off, end - off)
            else:
                encoded = cykb.xor_encode_decode(self.memory[off : off + length])
                self.response = struct.pack(
                    "<I", cykb.checksum(encoded) if subcmd == 1 else zlib.crc32(encoded)
                )
        elif cmd == 0x1E:
            if subcmd == 1:
                self.offset = struct.unpack_from("<I", data)[0]
            elif subcmd != 0:
                raise AssertionError(subcmd)
            self.response = struct.pack("<I", self.offset)
        elif cmd == 0x1F:
            data = data[:subcmd]
            assert subcmd == len(data) and 0 < len(data) <= 52 and len(data) % 4 == 0
            assert self.offset + len(data) <= len(self.memory)
            decoded = cykb.xor_encode_decode(data) if self.offset >= 0x200 else data
            self.memory[self.offset : self.offset + len(data)] = decoded
            self.offset += len(data)
            self.expected = (0x1E, 2)
            self.response = struct.pack("<I", self.offset)
        else:
            raise AssertionError((cmd, subcmd))

    def recv(self, size):
        assert size == 64
        return struct.pack("<BBH", *self.expected, 0) + bytes(self.response).ljust(
            60, b"\0"
        )

    def reboot(self, bootloader=False):
        self.reboots += 1
        raise AssertionError("Simulation must never request hardware reboot")


root = Path(__file__).resolve().parents[1]
results = []
for half, pid, sig in [("right", 0x0419, 0x040450C0), ("left", 0x041A, 0x04046080)]:
    d = json.loads(
        (
            root
            / "docs"
            / (
                "mistel-md770-live-info.json"
                if half == "right"
                else "mistel-md770-left-live-info.json"
            )
        ).read_text()
    )
    image = (
        args.firmware_directory / f"mistel_md770rgb_bt_{half}_default.bin"
    ).read_bytes()
    sim = SimulatedMD770(
        bytes.fromhex(d["boot_info_hex"]), bytes.fromhex(d["version_page_hex"])
    )
    sim.flash("QMK", image, boot=False)
    assert bytes(sim.memory[0x200 : 0x200 + len(image)]) == image
    sp, reset = struct.unpack_from("<II", image)
    assert 0x20000000 <= sp <= 0x20004000 and 0x3200 <= reset < 0x1FE00
    assert struct.unpack_from("<I", image, 0x9F8)[0] == sig
    marker = struct.unpack_from("<I", sim.memory, 0xB0)[0]
    count = marker >> 18
    assert marker & 0x3FFFF == 0x5AA5 and count <= 14
    words = struct.unpack_from("<" + "I" * count, sim.memory, 0x78)
    assert all(word != 0xFFFFFFFF for word in words)
    assert sim.version() == "QMK"
    assert sim.erases == [(0, 0x1CE00, 0x1CE00), (0, 0xB4, 0x200)]
    assert sim.reboots == 0
    results.append(
        {
            "half": half,
            "image_bytes": len(image),
            "image_sha256": hashlib.sha256(image).hexdigest(),
            "boot_validation": "passes recovered right/left-IAP marker/non-FF semantics",
            "application_preserved_after_version_erase": True,
            "metadata_words": [hex(w) for w in words],
            "erase_ranges": sim.erases,
            "reboot_requested": False,
        }
    )
print(
    json.dumps(
        {
            "tool_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "simulation_only": True,
            "results": results,
        },
        indent=2,
    )
)
