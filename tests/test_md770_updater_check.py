import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "md770_updater_check", Path(__file__).parents[1] / "scripts/md770_updater_check.py"
)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class DiagnosticProtocolTest(unittest.TestCase):
    def test_version_page_reads_only_the_eight_exposed_slices(self):
        with patch.object(
            updater, "request", side_effect=lambda fd, cmd, sub: bytes([sub]) * 60
        ) as request:
            page = updater.read_version_page(7)
        self.assertEqual(page, b"".join(bytes([sub]) * 60 for sub in range(0x20, 0x28)))
        self.assertEqual(len(page), 480)
        self.assertEqual(
            [call.args for call in request.call_args_list],
            [(7, 0x12, sub) for sub in range(0x20, 0x28)],
        )
        with self.assertRaises(ValueError):
            updater.packet(0x12, 0x28)

    def test_left_updater_checksums_and_return_use_left_usb_ids(self):
        image = bytes(36404)
        info = bytes.fromhex("0400000000000000d9041a1480600404").ljust(52, b"\xff")
        encoded = bytes(
            value ^ updater.XOR_KEY[index % 52] for index, value in enumerate(image)
        )
        checksum = (
            sum(word[0] for word in struct.iter_unpack("<I", encoded)) & 0xFFFFFFFF
        )

        def request(fd, command, subcommand, data=b""):
            if command == 0x1D:
                self.assertEqual(data, struct.pack("<II", 0x200, len(image)))
                return struct.pack("<I", checksum if subcommand == 1 else 0x90309827)
            if subcommand == 2:
                return bytes([fd != 2]).ljust(60, b"\0")
            if subcommand == 1:
                return bytes.fromhex("04000200").ljust(60, b"\0")
            return info.ljust(60, b"\0")

        report = {}
        with (
            patch.object(
                updater,
                "find_device",
                side_effect=[("app", "port"), FileNotFoundError()],
            ) as find,
            patch.object(
                updater,
                "wait_device",
                side_effect=[("iap", "port"), ("iap", "port"), ("app", "port")],
            ) as wait,
            patch.object(updater, "open_device", side_effect=[1, 2, 2, 3]),
            patch.object(updater.os, "close"),
            patch.object(updater, "request", request),
            patch.object(updater, "send") as send,
        ):
            updater.check(image, info, report, 0x041A, 0x90309827)
        self.assertEqual(find.call_args_list[0].args, (0x041A,))
        self.assertEqual(find.call_args_list[1].args, (0x041A, "port"))
        self.assertEqual(
            [call.args for call in wait.call_args_list],
            [(0x141A, "port"), (0x141A, "port"), (0x041A, "port")],
        )
        self.assertEqual(
            [call.args for call in send.call_args_list], [(1, 0x11, 0), (2, 0x11, 1)]
        )
        self.assertTrue(report["encoded_sum_matches"])
        self.assertTrue(report["encoded_crc_matches"])
        self.assertTrue(report["normal_usb_return_verified"])

    def test_flash_modification_commands_are_rejected(self):
        for command, subcommand in [(0x1D, 0), (0x1E, 1), (0x1F, 4), (0xC0, 0xF0)]:
            with self.subTest(command=command, subcommand=subcommand):
                with self.assertRaises(ValueError):
                    updater.packet(command, subcommand)

    def test_checksum_request_has_exact_relative_range(self):
        packet = updater.packet(0x1D, 2, struct.pack("<II", 0x200, 49008))
        self.assertEqual(len(packet), 65)
        self.assertEqual(packet[:13], bytes.fromhex("001d0200000002000070bf0000"))
        with self.assertRaises(ValueError):
            updater.packet(0x1D, 2, b"")
        with self.assertRaises(ValueError):
            updater.packet(0x11, 0, b"\0")

    def test_error_and_stale_replies_are_rejected(self):
        for reply in [
            b"",
            b"\x12\x00",
            bytes.fromhex("1d02ffaaff").ljust(64, b"\0"),
            bytes.fromhex("1d010000").ljust(64, b"\0"),
        ]:
            with self.subTest(reply=reply):
                with self.assertRaises(RuntimeError):
                    updater.reply_data(0x1D, 2, reply)

    def test_checksum_failure_still_returns_to_application(self):
        info = bytes.fromhex("d9041914c0500404").ljust(52, b"\xff")
        image = bytes(49008)
        resets = []

        def request(fd, command, subcommand, data=b""):
            if (command, subcommand) == (0x12, 2):
                return bytes([fd != 2]).ljust(60, b"\0")
            if (command, subcommand) == (0x12, 0):
                return info.ljust(60, b"\0")
            if (command, subcommand) == (0x12, 1):
                return bytes.fromhex("04000200").ljust(60, b"\0")
            return bytes(60)

        report = {}
        with (
            patch.object(
                updater,
                "find_device",
                side_effect=[("app", "port"), FileNotFoundError()],
            ),
            patch.object(
                updater,
                "wait_device",
                side_effect=[("iap", "port"), ("iap", "port"), ("app", "port")],
            ),
            patch.object(updater, "open_device", side_effect=[1, 2, 2, 3]),
            patch.object(updater.os, "close"),
            patch.object(updater, "request", request),
            patch.object(
                updater,
                "send",
                side_effect=lambda fd, cmd, sub: resets.append((cmd, sub)),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Installed application differs"):
                updater.check(image, info, report)
        self.assertEqual(resets, [(0x11, 0), (0x11, 1)])
        self.assertTrue(report["normal_usb_return_verified"])

    def test_iap_open_failure_still_attempts_normal_return(self):
        info = bytes(52)
        resets = []

        def request(fd, command, subcommand, data=b""):
            if subcommand == 2:
                return b"\1".ljust(60, b"\0")
            if subcommand == 1:
                return bytes.fromhex("04000200").ljust(60, b"\0")
            return info.ljust(60, b"\0")

        report = {}
        with (
            patch.object(
                updater,
                "find_device",
                side_effect=[("app", "port"), FileNotFoundError()],
            ),
            patch.object(
                updater,
                "wait_device",
                side_effect=[("iap", "port"), ("iap", "port"), ("app", "port")],
            ),
            patch.object(
                updater,
                "open_device",
                side_effect=[1, PermissionError("opening IAP failed"), 2, 3],
            ),
            patch.object(updater.os, "close"),
            patch.object(updater, "request", request),
            patch.object(
                updater,
                "send",
                side_effect=lambda fd, cmd, sub: resets.append((cmd, sub)),
            ),
        ):
            with self.assertRaises(PermissionError):
                updater.check(bytes(49008), info, report)
        self.assertEqual(resets, [(0x11, 0), (0x11, 1)])
        self.assertTrue(report["normal_usb_return_verified"])
        self.assertEqual(report["check_error"], "opening IAP failed")

    def test_missing_physical_identity_does_not_reset(self):
        with (
            patch.object(updater, "find_device", return_value=("app", "")),
            patch.object(updater, "send") as send,
        ):
            with self.assertRaisesRegex(RuntimeError, "physical USB port"):
                updater.check(bytes(49008), bytes(52), {})
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
