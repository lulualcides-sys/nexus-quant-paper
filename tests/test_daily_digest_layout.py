"""Focused regressions for Telegram report presentation only."""
import io
import json
import os
import unittest
from unittest.mock import patch

from src import daily_digest as report
from src.runner import telegram


class DailyLayoutTests(unittest.TestCase):
    def test_27_bot_report_is_readable_and_safe_html(self):
        old = {f"c{i}": {"closed": [], "position": None, "pnl": float(i),
                         "wins": 0, "losses": 0} for i in range(5)}
        lev = {f"l{i}": {"closed": [], "position": None, "pnl": float(i),
                         "wins": 0, "losses": 0} for i in range(5)}
        lev_config = {key: (None, f"Alavancado {key}") for key in lev}

        def scorecard(book):
            return {"pnl": book["pnl"], "wins": book["wins"], "losses": book["losses"]}

        def lev_stats(book):
            return {"pnl_usd": book["pnl"], "wins": book["wins"],
                    "losses": book["losses"], "frozen": False,
                    "effective_leverage": 0.0}

        with patch.object(report, "STUDY", list(old)), \
             patch.object(report, "DISPLAY", {k: f"Convencional {k}" for k in old}), \
             patch.object(report, "LEV_CONFIG", lev_config), \
             patch.object(report, "scorecard", side_effect=scorecard), \
             patch.object(report, "lev_stats", side_effect=lev_stats):
            msg = report.digest(
                "2026-11-02", {"books": old}, {"books": lev},
                mtf_error="Falha <fornecedor>", unavailable=["ouro & H1"],
                planned_robots=27,
            )
        self.assertTrue(msg.startswith("<b>📊 NEXUS QUANT"))
        self.assertIn("27 robôs previstos", msg)
        self.assertIn("📌 RESUMO DO DIA", msg)
        self.assertIn("5 CONVENCIONAIS", msg)
        self.assertIn("5 ALAVANCADOS", msg)
        self.assertIn("🟨 11º ROBÔ", msg)
        self.assertIn("&lt;fornecedor&gt;", msg)
        self.assertIn("ouro &amp; H1", msg)
        self.assertEqual(msg.count("0 entradas / 0 fech."), 10)
        self.assertIn("Sem operações reais", msg)
        self.assertIn("Entradas virtuais abertas hoje: 0", msg)
        self.assertLessEqual(len(msg), 4000)

    def test_html_only_on_daily_quant_digest(self):
        def capture(message):
            with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test",
                                         "TELEGRAM_CHAT_ID": "12345"}), \
                 patch("src.runner.urllib.request.urlopen",
                       return_value=io.BytesIO(b'{"ok": true}')) as urlopen, \
                 patch("src.runner.save_chat"):
                self.assertTrue(telegram(message))
                request = urlopen.call_args.args[0]
                return json.loads(request.data.decode("utf-8"))

        formatted = capture("<b>📊 NEXUS QUANT — hoje</b>")
        self.assertEqual(formatted["parse_mode"], "HTML")
        self.assertNotIn("parse_mode", capture("Mensagem comum"))


if __name__ == "__main__":
    unittest.main()
