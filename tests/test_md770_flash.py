import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import zlib


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "md770_flash", ROOT / "scripts/md770_flash.py"
)
flash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flash)


class USBFlashTest(unittest.TestCase):
    def setUp(self):
        self.saved = json.loads((ROOT / "docs/mistel-md770-live-info.json").read_text())
        self.version = bytes.fromhex(self.saved["version_page_hex"])
        image = bytearray(26824)
        struct.pack_into("<II", image, 0, 0x20000400, 0x3CE1)
        struct.pack_into("<III", image, 0x9F8, 0x040450C0, 0x34000001, 0x00020004)
        self.image = bytes(image)
        self.memory = bytearray(b"\xff" * flash.UPDATE_SIZE)
        self.pointer = 0
        self.operations = []

    def writer(self, fd, command, subcommand, data):
        self.operations.append((command, subcommand, data))
        if command == 0x1D:
            return struct.pack("<II", 0, flash.UPDATE_SIZE)
        if command == 0x1E:
            if subcommand == 1:
                self.pointer = struct.unpack("<I", data)[0]
            return struct.pack("<I", self.pointer)
        self.memory[self.pointer : self.pointer + len(data)] = data
        self.pointer += len(data)
        return struct.pack("<I", self.pointer)

    def checksum(self, fd, command, subcommand, arguments):
        start, length = struct.unpack("<II", arguments)
        data = self.memory[start : start + length]
        value = sum(word[0] for word in struct.iter_unpack("<I", data)) & 0xFFFFFFFF
        return struct.pack("<I", value if subcommand == 1 else zlib.crc32(data))

    def contexts(self):
        return (
            patch.object(flash, "write_request", self.writer),
            patch.object(flash.updater, "request", self.checksum),
            patch.object(
                flash.updater,
                "read_version_page",
                side_effect=lambda fd: bytes(self.memory[:480]),
            ),
        )

    def test_wrong_half_geometry_image_and_version_are_rejected(self):
        flash.validate_inputs(self.image, self.saved, "right")
        for half, offset, value in [
            ("left", None, None),
            ("right", 33, 0),
            ("right", 34, 0),
        ]:
            saved = copy.deepcopy(self.saved)
            if offset is not None:
                info = bytearray.fromhex(saved["boot_info_hex"])
                info[offset] = value
                saved["boot_info_hex"] = info.hex()
            with self.subTest(half=half, offset=offset), self.assertRaises(ValueError):
                flash.validate_inputs(self.image, saved, half)
        for image in [
            self.image[:-1],
            self.image + bytes(flash.UPDATE_SIZE),
            bytes(len(self.image)),
            self.image[:4092],
        ]:
            with self.assertRaises(ValueError):
                flash.validate_inputs(image, self.saved, "right")
        for offset in [0x90, 0xB0, 0xB4]:
            saved = copy.deepcopy(self.saved)
            version = bytearray(self.version)
            version[offset] ^= 1
            saved["version_page_hex"] = version.hex()
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                flash.validate_inputs(self.image, saved, "right")

    def test_golden_reports_and_acknowledgements(self):
        reply = bytes.fromhex("1e02000034020000").ljust(64, b"\0")
        with (
            patch.object(flash.os, "write", return_value=65) as write,
            patch.object(flash.select, "select", return_value=([7], [], [])),
            patch.object(flash.os, "read", return_value=reply),
        ):
            result = flash.write_request(7, 0x1F, 52, bytes(range(52)))
        self.assertEqual(struct.unpack_from("<I", result)[0], 0x234)
        self.assertEqual(
            write.call_args.args, (7, b"\0\x1f\x34\0\0" + bytes(range(52)) + bytes(8))
        )
        for command, subcommand, data in [
            (0x1D, 0, struct.pack("<II", 0, 0x20000)),
            (0x1F, 3, bytes(3)),
            (0x1E, 1, struct.pack("<I", 1)),
        ]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                flash.write_request(7, command, subcommand, data)
        with patch.object(flash, "write_request", return_value=bytes(60)):
            with self.assertRaisesRegex(RuntimeError, "pointer"):
                flash.write_region(7, 0x200, bytes(52))

    def test_app_verification_precedes_final_version_commit(self):
        a, b, c = self.contexts()
        with a, b, c:
            report = {}
            flash.program(7, self.image, self.version, report)
        self.assertEqual(
            self.memory[0x200 : 0x200 + len(self.image)], flash.encode(self.image)
        )
        self.assertEqual(self.memory[:480], self.version)
        blocks = [operation[1] for operation in self.operations if operation[0] == 0x1F]
        self.assertEqual(blocks[:516], [52] * 515 + [44])
        self.assertEqual(self.operations[-1], (0x1F, 4, self.version[0xB0:0xB4]))
        self.assertTrue(report["application_checksums_verified"])
        self.assertTrue(report["version_page_verified"])

    def test_partial_erase_never_writes(self):
        with patch.object(
            flash, "write_request", return_value=struct.pack("<II", 0, 512)
        ) as request:
            with self.assertRaisesRegex(RuntimeError, "erasing the complete"):
                flash.program(7, self.image, self.version, {})
        self.assertEqual(request.call_count, 1)

    def test_checksum_failure_leaves_version_invalid(self):
        a, _, c = self.contexts()
        with a, c, patch.object(flash.updater, "request", return_value=bytes(60)):
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                flash.program(7, self.image, self.version, {})
        self.assertEqual(self.memory[:512], b"\xff" * 512)

    def test_version_readback_failure_does_not_commit_marker(self):
        a, b, _ = self.contexts()
        with (
            a,
            b,
            patch.object(flash.updater, "read_version_page", return_value=bytes(480)),
        ):
            with self.assertRaisesRegex(RuntimeError, "before committing"):
                flash.program(7, self.image, self.version, {})
        self.assertEqual(self.memory[0xB0:0xB4], b"\xff" * 4)

    def test_failure_in_iap_never_reboots(self):
        info, version = flash.validate_inputs(self.image, self.saved, "right")
        with (
            patch.object(
                flash.updater,
                "find_device",
                side_effect=[FileNotFoundError(), ("/dev/hidraw7", "port")],
            ),
            patch.object(flash, "usb_device", return_value=Path("/unused")),
            patch.object(flash.updater, "open_device", return_value=7),
            patch.object(flash.updater, "request", side_effect=[b"\0", info]),
            patch.object(flash.updater, "read_version_page", return_value=version),
            patch.object(flash, "program", side_effect=RuntimeError("write failed")),
            patch.object(flash.updater.os, "close"),
            patch.object(flash.updater, "send") as send,
        ):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                flash.run(self.image, info, version, "right", {})
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
