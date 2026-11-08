"""Causal invariant regressions, not claims about trading profitability."""
import unittest
from unittest.mock import patch
from research.alpha_v4.data import aggregate,month,V5_BLIND_SOL_MONTHS
from research.alpha_v4.strategy import MultiTimeframe
from research.alpha_v5.strategy import ConfirmedRegime,H4_WARMUP,H4_SLOPE_LAG
from research.alpha.run import BOTS
from research.alpha_v5.run import _monthly_summary

BASE=1735689600  # 2025-01-01 UTC
def historical(n):
    return [dict(time=BASE+60*i,open=100+i*.001,
       high=100.2+i*.001,low=99.8+i*.001,
       close=100+i*.001,volume=50) for i in range(n)]

class V5Tests(unittest.TestCase):
    def test_completed_h4_index(self):
        h=ConfirmedRegime("alpha02_breakout_retest",historical(240*15))
        self.assertEqual(h.last_closed_h4(47),-1)
        self.assertEqual(h.last_closed_h4(48),0)
        self.assertEqual(h.last_closed_h4(95),0)
        self.assertEqual(h.last_closed_h4(96),1)
        self.assertEqual(H4_SLOPE_LAG,12)
        self.assertEqual(H4_WARMUP,60)

    def test_partial_h4_never_used_for_signals(self):
        raw=historical(240*15+120)
        model=ConfirmedRegime("alpha02_breakout_retest",raw)
        self.assertEqual(len(model.h4),15)
        self.assertEqual(model.last_closed_h4(len(model.bars)-1),14)

    def test_future_append_invariance_in_h1_h4(self):
        source=historical(60*260)
        prefix=source[:60*254]
        earlier=ConfirmedRegime("alpha04_ema_atr_pullback",prefix)
        later=ConfirmedRegime("alpha04_ema_atr_pullback",source)
        for i in (60*249+7,60*250+59,60*253-1):
            self.assertEqual(earlier.filter(i),later.filter(i))

    def test_same_underlying_alphas_and_exit_engine(self):
        b=historical(60*252)
        for name in BOTS:
            old=MultiTimeframe(name,b)
            new=ConfirmedRegime(name,b)
            self.assertIs(old.original,new.original)
            self.assertEqual(old.minutes,new.minutes)
            self.assertEqual(old.h1_exiting(60*251-1),
                             new.h1_exiting(60*251-1))

    def test_no_synthetic_zero_on_no_trades(self):
        self.assertIsNone(_monthly_summary([dict(trades=0,net_usdt=None)]).get("net_usdt"))
        self.assertEqual(_monthly_summary([dict(trades=1,net_usdt=-10.,
           total_costs_usdt=1.8)])["net_usdt"],-10)

    def test_2025_loader_allowed_but_network_must_supply_source(self):
        self.assertEqual(len(V5_BLIND_SOL_MONTHS),12)
        with patch("research.alpha_v4.data.retrieve",
                   side_effect=RuntimeError("network-stub")):
            with self.assertRaisesRegex(RuntimeError,"network-stub"):
                month("SOLUSDT","2025-01")

if __name__=="__main__":
    unittest.main()
