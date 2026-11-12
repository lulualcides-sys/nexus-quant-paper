"""Test warm-up methodology and whole-day source audit.

Fixtures are synthetic *logic tests*, not simulated trading performance claims.
"""
import csv
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_warmup_study import (
    at_ms,one_day,MARCH,OCTOBER,DAYS,ARMS,COSTS
)
from research.xau_pa_warmup_scorecard import compare,report_markdown


def fake_source(day,path):
    start=at_ms(day,9)
    with path.open("w",newline="") as file:
        writer=csv.writer(file)
        writer.writerow(["timestamp","askPrice","bidPrice"])
        for minute in range(480):
            for k in range(5):
                bid=2600+2*math.sin(minute/22)+.02*k
                writer.writerow([start+minute*60000+k*10000,bid+.20,bid])


def fake_result(day):
    v={}
    for tf in ("M1","M5"):
        v[tf]={}
        for arm in ARMS:
            val=0 if arm=="warm_quality" else 1
            item={
                "signals":1 if arm!="warm_quality" else 0,
                "costs":{},
            }
            for cost in COSTS:
                pnl=-2. if val else 0.
                item["costs"][cost]={
                    "signals":item["signals"],
                    "filled":val,"net_usd_per_oz":pnl,
                    "trades":[{"net_usd_per_oz":pnl,"reason":"STOP",
                               "setup":"break_retest"}] if val else [],
                }
            v[tf][arm]=item
    return {
        "day":day,
        "price_action_parameters_unchanged":True,
        "same_execution_tape_for_all_arms":True,
        "approved_for_live":False,"broker_verified":False,
        "warmup_start_utc":"09:00",
        "execution_start_utc":"12:00",
        "source":{"sha256":"f"*64},
        "results":v
    }


class WarmupTests(unittest.TestCase):
    def test_utc_session_boundaries_precisely(self):
        a=at_ms(DAYS[0],9)
        b=at_ms(DAYS[0],12)
        c=at_ms(DAYS[0],17)
        self.assertEqual(b-a,3*60*60*1000)
        self.assertEqual(c-b,5*60*60*1000)

    def test_quotes_seen_before_noon_never_become_early_orders(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"prices.csv"
            fake_source(DAYS[0],f)
            report=one_day(f,DAYS[0])
            self.assertTrue(report["same_execution_tape_for_all_arms"])
            self.assertFalse(report["approved_for_live"])
            self.assertFalse(report["broker_verified"])
            for tf in ("M1","M5"):
                for arm in ARMS:
                    for cost in COSTS:
                        trades=report["results"][tf][arm]["costs"][cost]["trades"]
                        for trade in trades:
                            self.assertGreaterEqual(trade["entry_ms"],at_ms(DAYS[0],12))
                            self.assertLess(trade["entry_ms"],at_ms(DAYS[0],17))
            # The cold and warm source begin at different historical instants.
            self.assertTrue(report["price_action_parameters_unchanged"])

    def test_reject_nonprecommitted_date(self):
        with self.assertRaisesRegex(ValueError,"preregistered"):
            one_day("/does/not/exist.csv","20260719")

    def _fill(self):
        td=tempfile.TemporaryDirectory()
        folder=Path(td.name)
        for day in DAYS:
            (folder/f"warm_{day}.json").write_text(json.dumps(fake_result(day)))
        return td,folder

    def test_all_periods_and_costs_covered(self):
        td,folder=self._fill()
        with td:
            r=compare(folder)
            self.assertTrue(r["historical_experiment_not_forward_trading"])
            self.assertFalse(r["approved_for_live"])
            self.assertEqual(len(r["clean_dates"]["march"]),10)
            self.assertEqual(len(r["clean_dates"]["october"]),10)
            self.assertEqual(r["results"]["M1"]["cold_control"]["march"]["double"]["net_usd_per_oz"],-20)
            self.assertEqual(r["results"]["M5"]["warm_quality"]["march"]["double"]["filled"],0)
            self.assertIn("NÃO",report_markdown(r).upper() if False else
                          report_markdown(r).replace("Não","NÃO"))

    def test_absent_day_cannot_silently_disappear(self):
        td,folder=self._fill()
        with td:
            (folder/f"warm_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing/mixed"):
                compare(folder)

    def test_corrupted_day_excluded_before_scoring(self):
        td,folder=self._fill()
        with td:
            day=DAYS[0]
            (folder/f"warm_{day}.json").unlink()
            (folder/f"quarantine_{day}.json").write_text(json.dumps({
                "day":day,"fully_excluded":True,
                "reason":"crossed price","counted_operations":0
            }))
            r=compare(folder)
            self.assertEqual(len(r["clean_dates"]["march"]),9)
            self.assertEqual(len(r["quarantined_whole_days"]),1)

    def test_no_fabricated_broker_validation(self):
        td,folder=self._fill()
        with td:
            f=folder/f"warm_{DAYS[0]}.json"
            d=json.loads(f.read_text())
            d["approved_for_live"]=True
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Untrusted"):
                compare(folder)


if __name__=="__main__":
    unittest.main()
