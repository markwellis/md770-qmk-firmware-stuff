import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'md770_backlight', Path(__file__).parents[1] / 'scripts/md770-backlight.py'
)
backlight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backlight)


class FlashTimingTest(unittest.TestCase):
    def test_slow_usb_replies_do_not_shorten_visible_states(self):
        now = 0
        updates = []
        mode = bytes([0x41, 0, 0, 0])

        def request(_fd, payload):
            nonlocal now
            packet = bytes(payload)
            if packet[:2] == b'\xc0\x00':
                now += 0.8 if not updates else 0.002
                updates.append((packet[4], now))
            if packet[:2] == b'\x41\xff':
                return mode.ljust(64, b'\0')
            return packet.ljust(64, b'\0')

        def sleep(seconds):
            nonlocal now
            now += seconds

        with patch.object(backlight, 'request', request), patch.object(
            backlight.time, 'sleep', sleep
        ), patch.object(backlight.time, 'monotonic', lambda: now):
            backlight.flash(0, mode)

        phases = []
        for level, timestamp in updates:
            if not phases or phases[-1][0] != level:
                phases.append((level, [timestamp]))
            else:
                phases[-1][1].append(timestamp)
        self.assertEqual([level for level, _ in phases], [255, 0] * 5)
        for previous, following in zip(phases, phases[1:]):
            self.assertGreaterEqual(following[1][0] - previous[1][0], 0.5)
        for _, timestamps in phases:
            self.assertGreater(timestamps[-1] - timestamps[0], 0.48)
            for previous, following in zip(timestamps, timestamps[1:]):
                self.assertLessEqual(following - previous, 0.008)

    def test_interruption_restores_normal_mode(self):
        mode = bytes([0x41, 0, 0, 0])
        commands = []

        def request(_fd, payload):
            packet = bytes(payload)
            commands.append(packet)
            return packet.ljust(64, b'\0')

        with patch.object(backlight, 'request', request), patch.object(
            backlight, 'hold_colour', side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                backlight.flash(0, mode)

        self.assertEqual(commands[-1], mode)
        self.assertIn(bytes([0xC0, 0xF0, 0, 0, 0]), commands)


if __name__ == '__main__':
    unittest.main()
