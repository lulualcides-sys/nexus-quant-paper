"""V5 closed H4 veto, no cost cheating, preserved V4, historical integrity."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from research.nexus_m1m5.data import Bar, month_range
from research.nexus_m1m5.engine import SCENARIOS
from research.nexus_m1m5.strategies import build_features
from research.nexus_m1m5.v3_policy import aggregate_closed_h1
from research.nexus_m1m5.v4_system import POLICIES, replay_v4
from research.nexus_m1m5.v5_policy import (
    H4_POLICIES, H4_MS, aggregate_closed_h4,
    h4_rejection_reason, last_closed_h4_index,
)
from research.nexus_m1m5.v5_run import FOLDS, MONTHS, variants, financial_status


def hourly(n=1080):
    return [Bar(i * 3600000, 100 + i*.1, 101+i*.1,
                99+i*.1, 100+i*.1, 50, 25)
            for i in range(n)]


def bullish_features(n):
    return SimpleNamespace(
        atr=[2.]*n,
        ema20=[100+i*.2 - 3 for i in range(n)],
        ema50=[100+i*.2 - 9 for i in range(n)],
        ema200=[100+i*.2 - 20 for i in range(n)],
    )


def bullish_bars(n=280):
    return [
        Bar(i*H4_MS, 99 + i*.2, 100.5+i*.2, 98.5+i*.2,
            100+i*.2, 100., 50.) for i in range(n)
    ]


class V5Regression(unittest.TestCase):
    def test_h4_uses_only_four_complete_contiguous_h1(self):
        x=hourly(12)
        h=aggregate_closed_h4(x)
        self.assertEqual(len(h),3)
        self.assertEqual([b.t for b in h],[0, H4_MS, 2*H4_MS])
        self.assertEqual(h[0].v,200)

    def test_h4_rejects_gap_and_incomplete_hour(self):
        x=hourly(9)
        self.assertEqual(len(aggregate_closed_h4(x)),2)
        x[1]=replace(x[1],t=x[1].t+1000)
        h=aggregate_closed_h4(x)
        self.assertEqual(len(h),1)
        self.assertEqual(h[0].t,H4_MS)

    def test_next_h4_not_visible_until_closed(self):
        clocks=[H4_MS,2*H4_MS,3*H4_MS]
        self.assertEqual(last_closed_h4_index(H4_MS-1,clocks),-1)
        self.assertEqual(last_closed_h4_index(H4_MS,clocks),0)
        self.assertEqual(last_closed_h4_index(2*H4_MS-1,clocks),0)
        self.assertEqual(last_closed_h4_index(2*H4_MS,clocks),1)

    def test_bullish_h4_signal_accepted(self):
        bars=bullish_bars()
        f=bullish_features(len(bars))
        ends=[x.t+H4_MS for x in bars]
        i=260
        decision=h4_rejection_reason(
            entry_open_ms=ends[i],
            entry_ref_price=bars[i].c,
            h4=bars,features=f,h4_closes=ends,
            policy=H4_POLICIES[0])
        self.assertIsNone(decision)

    def test_flat_h4_does_not_prove_predictive_long_edge(self):
        bars=[Bar(i*H4_MS,100,101,99,100,1,.5) for i in range(280)]
        f=build_features(bars)
        ends=[x.t+H4_MS for x in bars]
        reason=h4_rejection_reason(entry_open_ms=ends[260],entry_ref_price=100,
            h4=bars,features=f,h4_closes=ends,policy=H4_POLICIES[0])
        self.assertIsNotNone(reason)

    def test_no_future_H4_can_change_earlier_veto(self):
        bars=bullish_bars()
        f=bullish_features(len(bars))
        ends=[x.t+H4_MS for x in bars]
        i=260
        def reject(hist, feats):
            return h4_rejection_reason(entry_open_ms=ends[i],
                entry_ref_price=bars[i].c,h4=hist,features=feats,
                h4_closes=ends,policy=H4_POLICIES[1])
        base=reject(bars,f)
        edited=bars[:i+1]+[replace(x,h=10000,l=0.1,c=9000)
                         for x in bars[i+1:]]
        self.assertEqual(base,reject(edited,f))

    def test_h4_signal_veto_no_m5_future_access(self):
        bars=bullish_bars()
        f=bullish_features(len(bars))
        ends=[x.t+H4_MS for x in bars]
        # A signal inside the H4 window may see only h=259.
        self.assertEqual(last_closed_h4_index(ends[260]-1, ends), 259)
        # Exactly at close the h=260 candle becomes available.
        self.assertEqual(last_closed_h4_index(ends[260], ends), 260)

    def test_no_data_fails_closed(self):
        self.assertEqual(h4_rejection_reason(entry_open_ms=H4_MS,
            entry_ref_price=100, h4=[],features=None,h4_closes=[],
            policy=H4_POLICIES[0]),"missing_closed_h4")

    def test_frozen_policy_parameters_unaffected_by_cost_scenario(self):
        self.assertEqual(len(H4_POLICIES),2)
        self.assertLess(H4_POLICIES[0].min_trend_efficiency,
                        H4_POLICIES[1].min_trend_efficiency)
        self.assertEqual(set(SCENARIOS),{"base","double_cost","adverse"})
        self.assertEqual(len(variants()),6)
        self.assertTrue(all(e.exit_mode=="fixed" for e,_ in variants()))

    def test_previously_seen_years_never_declared_apt(self):
        vals={y:{"trades":100,"scenario_net_usd":{
            sc:100 for sc in SCENARIOS}} for y in ("2024","2025","2026")}
        self.assertEqual(financial_status(vals)[0],"INCONCLUSIVO")
        vals["2025"]["scenario_net_usd"]["adverse"]=-10
        self.assertEqual(financial_status(vals)[0],"REPROVADO")

    def test_low_N_is_not_positive_edge(self):
        vals={y:{"trades":7,"scenario_net_usd":{
            sc:100 for sc in SCENARIOS}} for y in ("2024","2025","2026")}
        self.assertEqual(financial_status(vals)[0],"INCONCLUSIVO")

    def test_three_years_frozen_and_no_exposed_2026_holdout(self):
        self.assertEqual(MONTHS[0],"2024-01")
        self.assertEqual(MONTHS[-1],"2026-06")
        self.assertEqual(len(MONTHS),30)
        self.assertEqual(len(FOLDS),10)
        self.assertEqual(sum(b-a for _,a,b in FOLDS),30)

    def test_v4_unchanged_without_optional_H4(self):
        m5=[Bar(i*300000,100,101,99,100,1,.5) for i in range(3120)]
        h1=aggregate_closed_h1(m5)
        features=build_features(h1)
        a,ledger_a=replay_v4(m5,h1,features,POLICIES[2],
                             start=241*12,stop=242*12)
        b,ledger_b=replay_v4(m5,h1,features,POLICIES[2],
                             start=241*12,stop=242*12,
                             h4=None,h4_features=None,h4_closes=None,
                             entry_gate=None)
        self.assertEqual(a,b)
        self.assertEqual(ledger_a,ledger_b)

    def test_opt_in_requires_real_H4_context(self):
        m5=[Bar(i*300000,100,101,99,100,1,.5) for i in range(3120)]
        h1=aggregate_closed_h1(m5)
        f=build_features(h1)
        with self.assertRaisesRegex(ValueError,"requires complete H4"):
            replay_v4(m5,h1,f,POLICIES[2],entry_gate=H4_POLICIES[0])

    def test_invalid_policy_denied(self):
        bars=bullish_bars()
        f=bullish_features(len(bars))
        ends=[x.t+H4_MS for x in bars]
        with self.assertRaisesRegex(ValueError,"frozen H4Policy"):
            h4_rejection_reason(entry_open_ms=ends[260],entry_ref_price=152,
                h4=bars,features=f,h4_closes=ends,policy="optimizer")

    def test_h4_veto_cannot_be_changed_by_fee_stress(self):
        bars=bullish_bars()
        f=bullish_features(len(bars))
        ends=[x.t+H4_MS for x in bars]
        verdicts=[
            h4_rejection_reason(entry_open_ms=ends[260],
                entry_ref_price=bars[260].c,h4=bars,features=f,
                h4_closes=ends,policy=H4_POLICIES[0])
            for _ in SCENARIOS
        ]
        self.assertEqual(verdicts,[None,None,None])


if __name__ == "__main__":
    unittest.main()
