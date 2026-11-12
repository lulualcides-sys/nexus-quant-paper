"""Synthetic quote tests of ONE shared M1/M5 XAUUSD position."""
import unittest

from research.xau_pa_shared_execution import simulate_shared_quotes
from research.xau_price_action_m1m5 import simulate_ticks,Settings


BASE=1793610000000


def sig(ms=BASE,tf=60,side=1):
    return {
        "setup":"break_retest","side":side,"atr":1.,
        "stop":99.5 if side==1 else 100.7,
        "signal_ms":ms-tf*1000,
        "eligible_ms":ms,"timeframe_seconds":tf,
    }


class SharedSymbolTests(unittest.TestCase):
    def test_shared_matches_original_engine_for_single_m1_trade(self):
        tape=[
            (BASE,100.,100.2),
            (BASE+5000,100.5,100.7),
            (BASE+10000,101.95,102.1),
        ]
        old=simulate_ticks(tape,[sig()],60,Settings())
        new=simulate_shared_quotes(tape,[sig()],Settings())
        self.assertEqual(old["filled"],new["filled"])
        self.assertEqual(old["net_usd_per_oz"],new["net_usd_per_oz"])
        self.assertEqual(old["trades"][0]["reason"],new["trades"][0]["reason"])

    def test_no_new_m5_position_while_m1_still_open(self):
        tape=[
            (BASE,100.,100.2),
            (BASE+5*60*1000,100.1,100.3),
            (BASE+6*60*1000,102.,102.2),
        ]
        outcome=simulate_shared_quotes(tape,[sig(),sig(BASE+5*60*1000,300)])
        self.assertEqual(outcome["filled"],1)
        self.assertEqual(outcome["rejected"]["already_in_position"],1)
        self.assertTrue(outcome["one_global_position_per_symbol"])

    def test_same_time_m1_m5_ambiguous_signal_is_not_cherry_picked(self):
        tape=[(BASE,100.,100.2),(BASE+5000,102.,102.2)]
        result=simulate_shared_quotes(tape,[sig(),sig(BASE,300)])
        self.assertEqual(result["filled"],0)
        self.assertEqual(result["rejected"]["simultaneous_m1_m5_ambiguous"],2)

    def test_m5_holding_period_is_100_minutes_not_20_minutes(self):
        tape=[
            (BASE,100.,100.2),
            (BASE+30*60000,100.,100.2),
            (BASE+101*60000,100.,100.2),
        ]
        s=sig(tf=300)
        outcome=simulate_shared_quotes(tape,[s])
        self.assertEqual(outcome["filled"],1)
        self.assertEqual(outcome["trades"][0]["exit_ms"],BASE+101*60000)
        self.assertEqual(outcome["trades"][0]["reason"],"TIME")

    def test_stop_gap_slippage_applies_correct_trade_side(self):
        tape=[(BASE,100.,100.2),(BASE+60000,99.1,99.4)]
        x=simulate_shared_quotes(tape,[sig()])
        self.assertEqual(x["trades"][0]["reason"],"STOP")
        self.assertAlmostEqual(x["trades"][0]["exit"],99.0)
        self.assertAlmostEqual(x["net_usd_per_oz"],-1.6)

    def test_rejects_invalid_tf_and_side(self):
        with self.assertRaisesRegex(ValueError,"M1/M5"):
            simulate_shared_quotes([], [sig(tf=15)])
        s=sig();s["side"]=0
        with self.assertRaisesRegex(ValueError,"side"):
            simulate_shared_quotes([], [s])

    def test_concurrent_positions_never_overlap(self):
        tape=[
            (BASE,100.,100.2),
            (BASE+60000,102.,102.2),
            (BASE+120000,100.,100.2),
            (BASE+180000,102.,102.2),
        ]
        result=simulate_shared_quotes(tape,
            [sig(),sig(BASE+120000,300)])
        self.assertEqual(result["filled"],2)
        self.assertLess(
            result["trades"][0]["exit_ms"],
            result["trades"][1]["entry_ms"],
        )


if __name__=="__main__":
    unittest.main()
