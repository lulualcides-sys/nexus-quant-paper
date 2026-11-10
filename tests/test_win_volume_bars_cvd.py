"""Offline tests for deterministic volume bars, CVD, absorption and provenance.

Synthetic trades are not B3 market data. Nothing accesses a paid data provider,
opens a brokerage account, downloads licensed source, or places an order.
"""
from pathlib import Path
import tempfile
import unittest

from research.win_volume_bars_cvd import (
    Policy,build_closed_volume_bars,detect_absorption
)
from research.win_licensed_tape_csv import private_output

START=1793711400000

def tape_bar(k,*,direction="flat",sellers=5,unknown=0,n=10,qty=10):
    """10 actual synthetic prints, each with contract qty=10, ordered by ms."""
    start=START+k*60000
    result=[]
    for j in range(n):
        if direction=="buy_abs":
            px=100000 if j==0 else 100050 if j==1 else 99890 if j==2 else 100040 if j==n-1 else 100020
        elif direction=="sell_abs":
            px=100050 if j==0 else 100000 if j==1 else 100110 if j==2 else 100010 if j==n-1 else 100040
        else:
            px=100000 if j==0 else 100100 if j==1 else 99900 if j==2 else 100020 if j==n-1 else 100010
        side=0 if j<unknown else (-1 if j<sellers else 1)
        result.append({"time_msc":start+j*3000,
                       "price":px,"quantity":qty,"aggressor":side})
    return result

def fixture(direction="buy_abs",unknown=0):
    series=[]
    for k in range(8):
        series+=tape_bar(k,sellers=5)
    series+=tape_bar(8,direction=direction,sellers=8 if direction=="buy_abs" else 2,
                     unknown=unknown)
    return series

def pol(**kwargs):
    return Policy(target_contracts=100,reference_bars=8,min_trade_prints=6,**kwargs)

class VolumeBarsTest(unittest.TestCase):
    def test_total_contracts_preserved_without_split(self):
        sample=tape_bar(0)
        b,d=build_closed_volume_bars(sample,pol())
        self.assertEqual(len(b),1)
        self.assertEqual(b[0]["volume_contracts"],100)
        self.assertEqual(b[0]["trade_prints"],10)
        self.assertEqual(d["total_trade_prints_processed"],10)
        self.assertFalse(d["incomplete_tail_dropped"])
        self.assertTrue(b[0]["closed"])

    def test_one_oversized_print_does_not_fabricate_additional_events(self):
        b,d=build_closed_volume_bars([{"time_msc":START,"price":100000,
                                        "quantity":250,"aggressor":1}],
                                      pol())
        self.assertEqual(len(b),1)
        self.assertEqual(b[0]["volume_contracts"],250)
        self.assertEqual(b[0]["trade_prints"],1)
        self.assertFalse(b[0]["quality_ok"])

    def test_incomplete_tail_is_dropped_with_diagnostic(self):
        ticks=tape_bar(0) + tape_bar(1,n=4)
        bars,d=build_closed_volume_bars(ticks,pol())
        self.assertEqual(len(bars),1)
        self.assertTrue(d["incomplete_tail_dropped"])
        self.assertEqual(d["incomplete_tail_contracts"],40)

    def test_buyer_absorption_with_aggressive_sells_can_signal(self):
        bars,d=build_closed_volume_bars(fixture(),pol())
        self.assertEqual(d["completed_volume_bars"],9)
        self.assertEqual(d["quality_passed_bars"],9)
        signals=detect_absorption(bars,pol())
        self.assertEqual(len(signals),1)
        signal=signals[0]
        self.assertEqual(signal["direction"],"buy")
        self.assertEqual(signal["source_bar_index"],8)
        self.assertLess(signal["delta"],0)
        self.assertEqual(signal["first_available_after_last_print_msc"],
                         bars[-1]["end_time_msc"])
        self.assertTrue(signal["not_original_tracker"])

    def test_seller_absorption_requires_aggressive_buys(self):
        bars,_=build_closed_volume_bars(fixture(direction="sell_abs"),pol())
        signals=detect_absorption(bars,pol())
        self.assertEqual(len(signals),1)
        self.assertEqual(signals[0]["direction"],"sell")
        self.assertGreater(signals[0]["delta"],0)

    def test_buy_signal_refused_when_price_never_sweeps_prior_low(self):
        no_sweep=[]
        for k in range(9):
            no_sweep+=tape_bar(k,sellers=8 if k==8 else 5)
        bars,_=build_closed_volume_bars(no_sweep,pol())
        self.assertEqual(detect_absorption(bars,pol()),[])

    def test_no_repaint_after_future_trades(self):
        original=fixture()
        b,_=build_closed_volume_bars(original,pol())
        signal=detect_absorption(b,pol())
        future=tape_bar(9,direction="sell_abs",sellers=2)
        b2,_=build_closed_volume_bars(original+future,pol())
        self.assertEqual(detect_absorption(b2,pol())[0],signal[0])

    def test_unknown_aggressor_never_assumed_buy_or_sell(self):
        bars,_=build_closed_volume_bars(fixture(unknown=6),pol())
        self.assertFalse(bars[-1]["quality_ok"])
        self.assertEqual(bars[-1]["unknown_volume"],60)
        self.assertEqual(detect_absorption(bars,pol()),[])

    def test_cvd_is_cumulative_classified_contracts_only(self):
        bars,_=build_closed_volume_bars(tape_bar(0,unknown=3,sellers=7) +
                                          tape_bar(1,sellers=3),pol())
        self.assertEqual(bars[0]["buy_volume"],30)
        self.assertEqual(bars[0]["sell_volume"],40)
        self.assertEqual(bars[0]["unknown_volume"],30)
        self.assertEqual(bars[0]["delta"],-10)
        self.assertEqual(bars[1]["delta"],40)
        self.assertEqual(bars[1]["cvd"],30)

    def test_time_order_must_be_monotonic(self):
        rows=tape_bar(0)
        rows[5]["time_msc"]=rows[3]["time_msc"]-1
        with self.assertRaisesRegex(ValueError,"Out-of-order"):
            build_closed_volume_bars(rows,pol())

    def test_invalid_side_and_invalid_tick_grid_rejected(self):
        r=tape_bar(0)
        r[0]["aggressor"]=99
        with self.assertRaisesRegex(ValueError,"Unknown side"):
            build_closed_volume_bars(r,pol())
        r[0]["aggressor"]=1
        r[0]["price"]=100002
        with self.assertRaisesRegex(ValueError,"tick price"):
            build_closed_volume_bars(r,pol())

    def test_unusable_policy_rejected(self):
        for bad in (Policy(target_contracts=0), Policy(min_classified_fraction=0),
                    Policy(min_contra_fraction=.5), Policy(reference_bars=1)):
            with self.assertRaises(ValueError):
                build_closed_volume_bars([],bad)

    def test_only_private_directory_can_receive_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                private_output({"signals":[]},Path(td)/"not_private.json")
            path=Path(td)/"private_mt5"/"bar_report.json"
            digest=private_output({"signals":[]},path)
            self.assertEqual(len(digest),64)
            self.assertTrue(path.exists())

    def test_no_order_methods_or_vendor_binary_in_research_code(self):
        src=Path("research/win_volume_bars_cvd.py").read_text(encoding="utf-8")
        for forbidden in ("order_send(","OrderSend(","CTrade ","login(",
                          "account_info(","requests.post(","subprocess.","WinDLL("):
            self.assertNotIn(forbidden,src)

if __name__=="__main__":
    unittest.main()
