"""Prospective paper-only candidate tests, no network and no brokerage."""
import json
import unittest
from copy import deepcopy
from math import sin
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from research.screen_v2 import aggregate_hourly_to_h4
from src.momentum60_shadow import CAPITAL, RISK, daily_line, process, update

T0 = 1791000000 // 14400 * 14400

def candles(n=1032):
    rows=[]
    for i in range(n):
        v=2500+i*.07 + sin(i/13)*1.4
        rows.append({"time": T0+i*3600, "open":v, "close":v+.15,
                     "high":v+.5, "low":v-.5})
    return rows

class ShadowMomentum60Tests(unittest.TestCase):
    def setUp(self):
        self.old=candles()
        self.new=candles(1036)
        self.mark=aggregate_hourly_to_h4(self.old)[-1]["time"]

    def test_bootstrap_and_idempotent_replay(self):
        book=update(None,self.old)
        self.assertEqual(book["h4_watermark"],self.mark)
        self.assertTrue(book["paper_only"] and book["experimental_only"])
        self.assertFalse(book["entries"] or book["closed"])
        self.assertIsNone(book["position"])
        before=deepcopy(book)
        self.assertEqual(update(book,self.old),before)

    def test_next_open_entry_and_risk_are_capped(self):
        book=update(None,self.old)
        latest_idx=len(aggregate_hourly_to_h4(self.new))-1
        def momentum(rule,bars,ind,i):
            return 1 if i==latest_idx-1 else 0
        with patch("src.momentum60_shadow.candidate_signal",side_effect=momentum):
            update(book,self.new)
        self.assertEqual(len(book["entries"]),1)
        self.assertIsNotNone(book["position"])
        p=book["position"]
        self.assertEqual(p["start"],aggregate_hourly_to_h4(self.new)[-1]["time"])
        self.assertLessEqual(p["qty"]*p["entry"],CAPITAL+1e-6)
        self.assertLessEqual(p["qty"]*(p["entry"]-p["stop"]),CAPITAL*RISK+1e-6)
        count_before=len(book["entries"])
        update(book,self.new)
        self.assertEqual(len(book["entries"]),count_before)

    def test_stop_gap_worse_open_and_no_same_bar_reentry(self):
        book=update(None,self.old)
        last_idx=len(aggregate_hourly_to_h4(self.new))-1
        with patch("src.momentum60_shadow.candidate_signal",
                   side_effect=lambda rule,bars,ind,i: 1 if i==last_idx-1 else 0):
            update(book,self.new)
        stop=book["position"]["stop"]
        next_rows=candles(1040)
        for i in range(1036,1040):
            next_rows[i]["open"]=stop-10
            next_rows[i]["close"]=stop-11
            next_rows[i]["high"]=stop-9
            next_rows[i]["low"]=stop-12
        with patch("src.momentum60_shadow.candidate_signal",return_value=1):
            update(book,next_rows)
        self.assertEqual(len(book["closed"]),1)
        self.assertEqual(book["closed"][0]["exit_type"],"STOP")
        self.assertEqual(book["closed"][0]["exit"],stop-10)
        self.assertLess(book["closed"][0]["net_usd"],0)
        self.assertEqual(len(book["entries"]),1)
        self.assertIsNone(book["position"])

    def test_old_watermark_fail_closed(self):
        book=update(None,self.old)
        book["h4_watermark"]-=100000
        with self.assertRaisesRegex(ValueError,"watermark lost"):
            update(book,self.new)

    def test_untrusted_state_never_resets(self):
        book=update(None,self.old)
        book["paper_only"]=False
        with self.assertRaisesRegex(ValueError,"incompatible"):
            update(book,self.new)

    def test_persist_is_independent_and_daily_only(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"shadow.json"
            book=process(self.old,path=path)
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["h4_watermark"],self.mark)
            message=daily_line(book,"2026-11-01")
            self.assertIn("EXTRA Momentum60",message)
            self.assertIn("NÃO VALIDADO",message)
            self.assertIn("0 entradas",message)


if __name__=="__main__":
    unittest.main()
