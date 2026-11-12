"""Safety regression tests for XAUUSD frozen-Runner risk gates."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from xau_entry_quality_batch7_2025plus import (
    GATES,ALLOWED_TF,ASSUMED_COST_FOR_SIGNAL,gate_signals,screen)


def sample(n=850):
    r=np.random.default_rng(91)
    c=2700+r.normal(0,1.4,n).cumsum()
    o=np.r_[c[0],c[:-1]]
    h=np.maximum(o,c)+r.uniform(.2,.8,n)
    l=np.minimum(o,c)-r.uniform(.2,.8,n)
    ix=pd.date_range("2025-04-01",periods=n,freq="1min",tz="UTC")
    return prepared(pd.DataFrame({"open":o,"high":h,"low":l,
        "close":c,"volume":np.full(n,30)},index=ix))


class TestGate7(unittest.TestCase):
    def test_only_approved_timeframes(self):
        self.assertEqual(ALLOWED_TF,(1,5,15,30))
        self.assertEqual(len(GATES),5)
        self.assertEqual(ASSUMED_COST_FOR_SIGNAL,1.2)

    def test_unfiltered_preserves_identical_event(self):
        df=sample()
        i=280
        op=float(df.open.iloc[i+1])
        arr=[(i,1,op-2.,.4)]
        self.assertEqual(gate_signals(df,arr,"UNFILTERED"),arr)

    def test_signal_stop_and_quality_are_never_mutated(self):
        df=sample()
        op=df.open.to_numpy(dtype=float)
        atr=df.atr.to_numpy(dtype=float)
        events=[
            (i,1,float(op[i+1]-1.5*atr[i]),float(q))
            for i,q in [(280,.2),(300,.4),(320,.8)]]
        for mode in GATES:
            retained=gate_signals(df,events,mode)
            self.assertTrue(all(x in events for x in retained))
            self.assertEqual(retained,sorted(retained,key=lambda e:e[0]))

    def test_quality_gate_threshold(self):
        df=sample()
        i=280
        opening=float(df.open.iloc[i+1])
        events=[(i,1,opening-5,.34),
                (i+10,1,float(df.open.iloc[i+11])-5,.35)]
        got=gate_signals(df,events,"QUALITY_GE_0P35")
        self.assertEqual(len(got),1)
        self.assertEqual(got[0],events[1])

    def test_only_next_open_affects_risk_gate(self):
        df=sample()
        i=280
        opening=float(df.open.iloc[i+1])
        ev=[(i,1,opening-20.,.7)]
        a=gate_signals(df,ev,"COST_TO_STOP_LE_10PCT")
        df2=df.copy()
        # Dramatic changes after NEXT OPEN may not affect a signal decision.
        df2.loc[df2.index[i+1:],"high"]+=200.
        df2.loc[df2.index[i+1:],"low"]-=200.
        df2.loc[df2.index[i+1:],"close"]+=100.
        b=gate_signals(df2,ev,"COST_TO_STOP_LE_10PCT")
        self.assertEqual(a,b)

    def test_high_cost_relative_to_risk_is_rejected(self):
        df=sample()
        i=280
        opening=float(df.open.iloc[i+1])
        events=[(i,1,opening-2.,.8),
                (i+20,1,float(df.open.iloc[i+21])-20.,.8)]
        got=gate_signals(df,events,"COST_TO_STOP_LE_10PCT")
        self.assertEqual(got,events[1:])

    def test_unknown_gate_rejected(self):
        with self.assertRaises(ValueError):
            gate_signals(sample(),[],"MONEY_PRINTER")

    def test_research_screen_cannot_pass_low_trade_counts(self):
        from xau_exit_risk_batch6_2025plus import CANDIDATES
        cases=[]
        for name,tf,model in CANDIDATES:
            for year in ("2025","2026"):
                summary={gate:{"1.2":dict(N=5,net_R=300,PF_R=2.3,MDD_R=2.),
                    "1.6":dict(N=5,net_R=250,PF_R=2.1,MDD_R=2.)} for gate in GATES}
                q=[{"gates":{gate:{"1.2":{"net_R":20}}
                    for gate in GATES}}]
                cases.append(dict(year=year,candidate=name,summary=summary,quarters=q))
        ranked=screen(cases)
        self.assertEqual(len(ranked),25)
        self.assertFalse(any(r["preliminary_screen"] for r in ranked))


if __name__=="__main__":
    unittest.main()
