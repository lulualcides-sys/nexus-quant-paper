"""Causal comparison tests with frozen model, private inputs and no orders."""
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from research.win_flow_public_label_comparison import (
    compare,independent_signals,local_label_minute,POLICY
)

START=int(datetime(2026,11,3,12,10,tzinfo=timezone.utc).timestamp())
def bars():
    result=[]
    for i in range(21):
        stamp=START+i*60
        result.append({"time":stamp,"open":100050.,"high":100100.,
                       "low":100000.,"close":100050.,
                       "real_volume":100,"valid_flow":True,
                       "classified_trade_count":25,"classified_share":1.,
                       "buy_volume":50.,"sell_volume":50.,"delta":0.,
                       "reject_reasons":[]})
    result[-1].update({"open":100020.,"high":100090.,"low":99985.,
                       "close":100050.,"real_volume":150,
                       "buy_volume":25.,"sell_volume":125.,"delta":-100.})
    return result

class PrivateComparisonTests(unittest.TestCase):
    def test_signal_time_is_after_closed_bar(self):
        b=bars()
        signals,stats=independent_signals(b)
        self.assertEqual(len(signals),1)
        self.assertEqual(stats["price_candidates"],1)
        self.assertEqual(signals[0]["observed_after_closed_bar_utc"],b[-1]["time"]+60)
        self.assertEqual(signals[0]["reference_bar_open_utc"],b[-1]["time"])
        self.assertEqual(signals[0]["side"],1)
        self.assertEqual(signals[0]["minute"],9*60+31)
        self.assertEqual(signals[0]["source"],"NQ_INDEPENDENT_EXHAUSTION_NOT_TRACKER")
    def test_missing_real_tick_flow_rejects_signal(self):
        b=bars()
        b[-1]["valid_flow"]=False
        signs,s=independent_signals(b)
        self.assertEqual(signs,[])
        self.assertEqual(s["rejected_due_to_tick_quality"],1)
    def test_wrong_side_flow_rejects_signal(self):
        b=bars()
        b[-1].update(buy_volume=125.,sell_volume=25.,delta=100.)
        signs,s=independent_signals(b)
        self.assertEqual(signs,[])
        self.assertEqual(s["rejected_contra_delta"],1)
    def test_next_future_candle_never_changes_past_signal(self):
        b=bars()
        original,_=independent_signals(b)
        new=dict(b[-1])
        new.update(time=b[-1]["time"]+60,high=200000.,low=90000.,
                   close=190000.,real_volume=15000.)
        extra,_=independent_signals(b+[new])
        self.assertEqual(extra[0],original[0])
    def test_missing_one_minute_in_prior_20_refuses_causal_setup(self):
        b=bars()
        b[8]["time"]+=60
        signs,_=independent_signals(b)
        self.assertEqual(signs,[])
    def test_matches_exact_and_one_minute_unique_only(self):
        b=bars()
        signs,_=independent_signals(b)
        exact=[{"id":1,"date":"2026-11-03","minute":571,"side":1}]
        self.assertEqual(compare(signs,exact,0)["matched_unique_labels"],1)
        one_min=[{"id":2,"date":"2026-11-03","minute":570,"side":1}]
        self.assertEqual(compare(signs,one_min,0)["matched_unique_labels"],0)
        self.assertEqual(compare(signs,one_min,1)["matched_unique_labels"],1)
        self.assertEqual(compare(signs,exact+one_min,1)["matched_unique_labels"],1)
    def test_wrong_side_cannot_match_even_same_minute(self):
        b=bars()
        signals,_=independent_signals(b)
        others=[{"id":1,"date":"2026-11-03","minute":571,"side":-1}]
        self.assertEqual(compare(signals,others,1)["matched_unique_labels"],0)
    def test_explicit_model_parameters_are_frozen(self):
        self.assertEqual(POLICY.lookback,20)
        self.assertEqual(POLICY.contra_aggressor_share,.56)
        self.assertTrue(POLICY.verify_tick_coverage)
    def test_comparison_source_no_broker_order_or_credentials(self):
        code=Path("research/win_flow_public_label_comparison.py").read_text(encoding="utf-8")
        for x in ("order_send(", "account_info(", "login(", "requests.post("):
            self.assertNotIn(x,code)

if __name__=="__main__":unittest.main()
