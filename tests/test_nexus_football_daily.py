import json
from io import BytesIO
import os
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
from unittest.mock import patch

from src.nexus_football_daily import load_summary, format_football, deliver

SAMPLE = {"schema": 2, "day": "2026-10-25", "games": 28, "finished": 22,
          "quotes_verified": 12, "games_with_verified_odds": 3,
          "market_families_with_verified_prices": 2, "market_families_catalogued": 27,
          "market_families_quoted": {"match_odds": 9, "total_goals": 3},
          "bookmakers": {"Pinnacle": 6, "Bet365": 6},
          "results": {"1x2_home": 7, "1x2_draw": 4, "1x2_away": 11,
                      "over_2_5_yes": 13, "over_2_5_no": 9}}

class Response(BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()

class FootballTelegramTests(unittest.TestCase):
    def test_digest_is_aggregated_not_per_game(self):
        msg = format_football(SAMPLE)
        self.assertIn("12 em 3 jogos", msg)
        self.assertIn("Over 2.5: 13 sim / 9 não", msg)
        self.assertNotIn("lucro garantido", msg)

    def test_fetch_checks_schema_and_date(self):
        def open_fixture(request, timeout=0):
            return Response(json.dumps(SAMPLE).encode())
        self.assertEqual(load_summary("2026-10-25", opener=open_fixture)["games"], 28)
        with self.assertRaises(ValueError):
            load_summary("2026-10-24", opener=open_fixture)

    def test_one_message_only_and_marker_after_send(self):
        calls = []
        def mock_api(token, method, payload=None):
            calls.append(method)
            return {"username": "NexusQuantAlertasBot"} if method == "getMe" else {"message_id": 5}
        with TemporaryDirectory() as folder, patch.dict(os.environ,
            {"TELEGRAM_BOT_TOKEN": "fake-test-token", "TELEGRAM_CHAT_ID": "123"}):
            path = Path(folder)
            self.assertTrue(deliver("2026-10-25", path, fetch=lambda day: SAMPLE, messenger=mock_api))
            self.assertFalse(deliver("2026-10-25", path, fetch=lambda day: SAMPLE, messenger=mock_api))
            self.assertEqual(calls, ["getMe", "sendMessage"])

    def test_missing_report_reports_failure_not_zero(self):
        messages = []
        def mock_api(token, method, payload=None):
            if method == "getMe":
                return {"username": "NexusQuantAlertasBot"}
            messages.append(payload["text"])
            return {"message_id": 9}
        with TemporaryDirectory() as folder, patch.dict(os.environ,
            {"TELEGRAM_BOT_TOKEN": "fake-test-token", "TELEGRAM_CHAT_ID": "123"}):
            deliver("2026-10-25", Path(folder),
                    fetch=lambda d: (_ for _ in ()).throw(ValueError("missing")),
                    messenger=mock_api)
        self.assertIn("ainda não está disponível", messages[0])
        self.assertNotIn("0 jogos", messages[0])

if __name__ == "__main__":
    unittest.main()
