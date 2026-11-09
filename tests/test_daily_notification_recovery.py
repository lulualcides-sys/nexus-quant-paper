"""Fechamentos por data BRT e falhas isoladas; nenhuma rede nos testes."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.daily_notification_recovery import recover

TZ = ZoneInfo("America/Sao_Paulo")


def ts(year, month, day, hour, minute=0):
    return int(datetime(year, month, day, hour, minute, tzinfo=TZ).timestamp())


class RecoveryTests(unittest.TestCase):
    def test_monday_morning_recovers_sunday_football_not_sunday_market(self):
        calls = []
        recovered = recover(now=ts(2026, 11, 9, 7),
                            football=lambda day: calls.append(("foot", day)) or True,
                            financial=lambda: calls.append(("finance", "")) or True)
        self.assertEqual(calls, [("foot", "2026-11-08")])
        self.assertEqual(recovered, ["futebol 2026-11-08"])

    def test_monday_night_recovers_financial_only(self):
        calls = []
        recovered = recover(now=ts(2026, 11, 9, 20, 30),
                            football=lambda day: calls.append(("foot", day)) or True,
                            financial=lambda: calls.append(("finance", "")) or True)
        self.assertEqual(calls, [("finance", "")])
        self.assertEqual(recovered, ["financeiro 2026-11-09"])

    def test_saturday_morning_recovers_friday_market(self):
        calls = []
        recover(now=ts(2026, 11, 7, 6),
                football=lambda day: calls.append(("foot", day)) or False,
                financial=lambda: calls.append(("finance", "")) or False)
        self.assertEqual(calls, [("foot", "2026-11-06"), ("finance", "")])

    def test_error_does_not_suppress_other_recovery(self):
        calls = []
        def broken(day):
            raise ValueError("network failed")
        with self.assertRaisesRegex(RuntimeError, "futebol 2026-11-05"):
            recover(now=ts(2026, 11, 6, 7),
                    football=broken,
                    financial=lambda: calls.append("finance") or True)
        self.assertEqual(calls, ["finance"])

    def test_before_the_primary_window_does_not_send_early(self):
        self.assertEqual(recover(now=ts(2026, 11, 9, 0, 20),
                                 football=lambda d: self.fail("too early"),
                                 financial=lambda: self.fail("too early")), [])


if __name__ == "__main__":
    unittest.main()
