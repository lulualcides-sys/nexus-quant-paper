"""V6 midday veto has no lookahead, ignores unverified backtest success."""
from __future__ import annotations

import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

from research.atlas_v6_noon_probe import (
    PROBES,MINUTE_START,MINUTE_END,probe_signal,
)
from research.win_price_data import TZ


def fake_bars(n=135):
    start=datetime(2026,5,18,0,0,tzinfo=TZ)
    return [{
        "time":int((start+timedelta(minutes=5*i)).astimezone(timezone.utc).timestamp()),
        "open":200000,"high":200100,"low":199900,"close":200010,"volume":500,
    } for i in range(n)]


class AtlasMiddayHypothesisTests(unittest.TestCase):
    def test_exact_midday_window_and_no_after_hours_artifact(self):
        rows=fake_bars()
        tests=[
            (11,55,1),(12,0,0),(14,55,0),(15,0,1),
        ]
        with patch("research.atlas_v6_noon_probe.v5_candidate",return_value=1):
            for hour,minute,expected in tests:
                stamp=int(datetime(2026,5,18,hour,minute,tzinfo=TZ).timestamp())
                rows[125]["time"]=stamp
                self.assertEqual(probe_signal(rows,125,"v6_v1_skip_12_15"),
                                 expected,(hour,minute))
                self.assertEqual(probe_signal(rows,125,"v6_v3_skip_12_15"),
                                 expected,(hour,minute))
                self.assertEqual(probe_signal(rows,125,"v1_reference"),1)
                self.assertEqual(probe_signal(rows,125,"v3_reference"),1)

    def test_negative_sells_are_vetoed_only_during_noon(self):
        rows=fake_bars()
        with patch("research.atlas_v6_noon_probe.v5_candidate",return_value=-1):
            rows[125]["time"]=int(datetime(2026,5,18,12,30,tzinfo=TZ).timestamp())
            self.assertEqual(probe_signal(rows,125,"v6_v1_skip_12_15"),0)
            rows[125]["time"]=int(datetime(2026,5,18,11,0,tzinfo=TZ).timestamp())
            self.assertEqual(probe_signal(rows,125,"v6_v1_skip_12_15"),-1)

    def test_unknown_variant_rejected_and_not_enough_history(self):
        rows=fake_bars()
        self.assertEqual(len(PROBES),4)
        self.assertEqual((MINUTE_START,MINUTE_END),(720,900))
        with self.assertRaisesRegex(ValueError,"Unknown"):
            probe_signal(rows,125,"v6_optimized_for_winners")
        with patch("research.atlas_v6_noon_probe.v5_candidate",return_value=1):
            self.assertEqual(probe_signal(rows,25,"v6_v1_skip_12_15"),0)
            self.assertEqual(probe_signal(rows,len(rows),"v6_v1_skip_12_15"),0)

    def test_future_mutation_does_not_change_signal(self):
        rows=fake_bars()
        rows[125]["time"]=int(datetime(2026,5,18,11,55,tzinfo=TZ).timestamp())
        with patch("research.atlas_v6_noon_probe.v5_candidate",return_value=1):
            prior=probe_signal(rows,125,"v6_v1_skip_12_15")
            rows[126]={**rows[126],"high":800000,"low":10000,"close":300000}
            self.assertEqual(prior,probe_signal(rows,125,"v6_v1_skip_12_15"))

    def test_reference_probes_retain_base_model_identity(self):
        rows=fake_bars()
        calls=[]
        def reference(bars,i,model):
            calls.append(model)
            return 1
        with patch("research.atlas_v6_noon_probe.v5_candidate",side_effect=reference):
            probe_signal(rows,125,"v1_reference")
            probe_signal(rows,125,"v6_v1_skip_12_15")
            probe_signal(rows,125,"v3_reference")
            probe_signal(rows,125,"v6_v3_skip_12_15")
        self.assertEqual(calls,["v1_reference","v1_reference",
                                "v3_reference","v3_reference"])

if __name__=="__main__":
    unittest.main()
