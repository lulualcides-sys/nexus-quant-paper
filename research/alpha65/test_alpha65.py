"""Structural and synthetic execution tests only, NOT a financial backtest."""
import importlib.util
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

PATH=Path(__file__).resolve().parent/"run.py"
spec=importlib.util.spec_from_file_location("alpha65_run",PATH)
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def fabricate(n=350):
    ts=pd.date_range("2026-04-02 12:00:00+00:00",periods=n,freq="min")
    close=2000.+np.sin(np.arange(n)/5.)*3
    o=np.r_[close[0],close[:-1]]
    high=np.maximum(o,close)+.6
    low=np.minimum(o,close)-.6
    return pd.DataFrame({"open":o,"high":high,"low":low,"close":close,
                         "volume":np.full(n,100.)},index=ts)

class Alpha65Safety(unittest.TestCase):
    def test_causal_closed_candle_events(self):
        x=r.enriched(fabricate())
        events=r.signals_for(x,1)
        for e in events:
            self.assertGreater(e["entry_time"],pd.Timestamp(e["signal_time"]))
            self.assertIn(e["direction"],(-1,1))
            self.assertTrue(0<=e["score"]<=1)
            self.assertIn(e["model"],{"SWEEP","EMA_PULLBACK","BOS_RETEST"})

    def test_no_repainting_of_historical_signal_when_future_appended(self):
        bars=r.enriched(fabricate(500))
        old=r.signals_for(bars.iloc[:400].copy(),1)
        new=r.signals_for(bars.copy(),1)
        old_keys={(e["signal_time"],e["direction"],e["model"]) for e in old}
        cutoff=bars.index[399]
        new_keys={(e["signal_time"],e["direction"],e["model"])
                  for e in new if pd.Timestamp(e["signal_time"])<cutoff}
        self.assertEqual(old_keys,new_keys)

    def test_stop_wins_same_bar_ambiguity(self):
        df=fabricate(260)
        j=230
        df.iloc[j,df.columns.get_loc("open")]=2000.
        df.iloc[j,df.columns.get_loc("high")]=2010.
        df.iloc[j,df.columns.get_loc("low")]=1990.
        df.iloc[j,df.columns.get_loc("close")]=2001.
        event={"entry_time":df.index[j],"signal_time":str(df.index[j-1]),
               "direction":1,"model":"SWEEP","timeframe":1,
               "score":0.75,"stop":1996.,"atr":3.}
        trades,dd,eq=r.trade_replay(df,[event],{"SWEEP"},{1},1.)
        self.assertEqual(len(trades),1)
        self.assertEqual(trades[0]["reason"],"SL")
        self.assertLess(trades[0]["pnl_usd"],0)
        self.assertLess(eq,r.START_CASH)
        self.assertLessEqual(trades[0]["risk_usd"],r.START_CASH*r.RISK)

    def test_one_position_cannot_overlap(self):
        df=fabricate(260)
        j=230
        df.iloc[j,df.columns.get_loc("open")]=2000.
        df.iloc[j,df.columns.get_loc("high")]=2010.
        df.iloc[j,df.columns.get_loc("low")]=1990.
        event={"entry_time":df.index[j],"signal_time":str(df.index[j-1]),
               "direction":1,"model":"SWEEP","timeframe":1,
               "score":0.75,"stop":1996.,"atr":3.}
        a=event.copy();a["model"]="EMA_PULLBACK";a["score"]=.7
        trades,_,_=r.trade_replay(df,[event,a],{"SWEEP","EMA_PULLBACK"},{1},1.)
        self.assertEqual(len(trades),1)

    def test_empty_not_approved(self):
        m=r.metrics([])
        self.assertEqual(m["trades"],0)
        self.assertTrue(all(not row["pass"] for row in m["monthly"]))
        self.assertEqual(len(m["monthly"]),len(r.MONTHS))

    def test_minimum_monthly_and_pf_gates_not_replaced_with_average(self):
        n=159
        sample=[]
        for k in range(n):
            sample.append({"month":r.MONTHS[0],"pnl_usd":10 if k<104 else -30,
                           "entry":str(k),"exit":str(k),"pnl_r":1.,
                           "equity_usd":10000.})
        m=r.metrics(sample)
        self.assertEqual(m["monthly"][0]["n"],159)
        self.assertGreaterEqual(m["monthly"][0]["win_pct"],65)
        self.assertFalse(m["monthly"][0]["pass"]) # PF too low, loss
        self.assertFalse(all(row["pass"] for row in m["monthly"]))

    def test_no_actual_broker_trading_or_martingale(self):
        source=PATH.read_text()
        for fragment in ("OrderSend(", "Martingale", "grid_orders", "WebRequest("):
            self.assertNotIn(fragment,source)
        self.assertIn("RISK=.0075",source)

if __name__=="__main__":
    unittest.main()
