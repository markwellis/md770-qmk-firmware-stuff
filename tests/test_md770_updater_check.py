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
