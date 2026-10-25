import json
from datetime import datetime, timezone
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import unittest

from src.nexus_football_daily import format_football, load_priority_coverage, deliver

DAY = "2026-10-25"
BASE = {"schema":2, "day":DAY, "games":20, "finished":15, "quotes_verified":12,
        "games_with_verified_odds":7, "qualified_game_quotes_verified":0,
        "liquidity_qualified_games":0, "liquidity_below_games":0,
        "liquidity_unknown_games":20, "market_families_with_verified_prices":2,
        "market_families_catalogued":27, "market_families_quoted":{"match_odds":9},
        "bookmakers":{"Example":12},
        "results":{"1x2_home":5,"1x2_away":7,"1x2_draw":3},
        "qualified_results":{}}

class Response(BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.close()

class PriorityDigestTests(unittest.TestCase):
    def test_mixed_coverage_does_not_count_indicative_as_verified(self):
        priority = {"schema":1, "important_games":50,
                    "verified_bookmaker_games":7, "indicative_only_games":10,
                    "missing_bookmaker_price_games":33}
        message = format_football(BASE, priority)
        self.assertIn("JOGOS IMPORTANTES (próximas 48h)\nMonitorados: 50", message)
        self.assertIn("Resultados gerais (liquidez não comprovada)", message)
        self.assertIn("1X2: Casa 5 | Empate 3 | Fora 7", message)
        self.assertIn("Com odds verificadas: 7", message)
        self.assertIn("Somente indicativas: 10", message)
        self.assertIn("Sem cotação: 33", message)
        self.assertIn("não comprovam odds de entrada", message)

    def test_pinnacle_prices_are_shown_only_when_confirmed_by_radar(self):
        coverage = {"important_games": 12, "verified_bookmaker_games": 5,
                    "indicative_only_games": 1, "missing_bookmaker_price_games": 6,
                    "pinnacle_guest": {"status": "checked", "matched": 3,
                                       "offers": 28,
                                       "market_families": {"total_goals": 16,
                                                           "asian_handicap": 12}}}
        msg = format_football(BASE, coverage)
        self.assertIn("Pinnacle pública: 28 odds observadas em 3 jogos", msg)
        self.assertIn("total_goals 16", msg)
        coverage["pinnacle_guest"]["status"] = "stale"
        self.assertNotIn("Pinnacle pública:", format_football(BASE, coverage))

    def test_priority_report_rejects_stale_data(self):
        def open_doc(value):
            def opener(req, timeout=0):
                return Response(json.dumps(value).encode("utf-8"))
            return opener
        current = {"schema":1, "checked_at":datetime.now(timezone.utc).isoformat(),
                   "important_games":8, "verified_bookmaker_games":1,
                   "indicative_only_games":2,"missing_bookmaker_price_games":5}
        self.assertEqual(load_priority_coverage(open_doc(current))["important_games"],8)
        old = dict(current, checked_at="2025-01-01T12:00:00Z")
        with self.assertRaises(ValueError):
            load_priority_coverage(open_doc(old))

    def test_book_quality_and_missing_games_in_daily_telegram(self):
        data={"important_games":12,"verified_bookmaker_games":7,
              "indicative_only_games":1,"missing_bookmaker_price_games":4,
              "top_missing":[{"home":"Flamengo","away":"Atletico Mineiro"}],
              "book_quality":{"status":"fresh","complete_market_lines":145,
                              "families":{"match_odds":{"median_overround_pct":5.91}}}}
        message=format_football(BASE,data)
        self.assertIn("Linhas completas: 145",message)
        self.assertIn("Margem 1X2 mediana: 5.91%",message)
        self.assertIn("Flamengo x Atletico Mineiro",message)
        data["book_quality"]["status"]="stale"
        self.assertNotIn("Linhas completas:",format_football(BASE,data))

    def test_failed_radar_keeps_regular_daily_delivery(self):
        sent = []
        def fake_api(token, method, payload=None):
            if method == "getMe": return {"username":"NexusQuantAlertasBot"}
            sent.append(payload["text"])
            return {"message_id":321}
        with TemporaryDirectory() as folder, patch.dict(
                "os.environ", {"TELEGRAM_BOT_TOKEN":"dummy","TELEGRAM_CHAT_ID":"1"}):
            result = deliver(DAY, marker_folder=Path(folder),
                             fetch=lambda day:BASE, messenger=fake_api,
                             priority_fetch=lambda: (_ for _ in ()).throw(ValueError("stale")))
            self.assertTrue(result)
            self.assertEqual(len(sent),1)
            self.assertNotIn("JOGOS IMPORTANTES", sent[0])
            self.assertIn("NEXUS FUTEBOL", sent[0])


if __name__ == "__main__":
    unittest.main()
