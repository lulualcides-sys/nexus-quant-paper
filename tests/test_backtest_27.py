"""Synthetic offline tests for all-27 historical replay: no Yahoo API or broker."""
import math
import unittest
from copy import deepcopy
from unittest.mock import patch

from research import backtest_27 as bt
from research.screen_v2 import aggregate_hourly_to_h4

T0 = 1791000000//14400*14400
START = T0+280*14400
END = T0+630*14400

def hourly(n=640*4,shift=0):
    out=[]
    for i in range(n):
        p=2600+shift+i*.1+2*math.sin(i/23)
        out.append({"time":T0+i*3600,"open":p,"high":p+1.8,
                    "low":p-1.5,"close":p+.2})
    return out

def quarter(n=440):
    base=T0+300*14400
    return [{"time":base+i*900,"open":1.38+i*.000001,
             "high":1.3805+i*.000001,"low":1.3795+i*.000001,
             "close":1.3801+i*.000001} for i in range(n)]


class Backtest27Tests(unittest.TestCase):
    def test_all_ids_exact_census(self):
        ids=bt.all_ids()
        self.assertEqual(len(ids),27)
        self.assertEqual(sum(k.startswith("gold_h4:") for k in ids),5)
        self.assertEqual(sum(k.startswith("leveraged_h4:") for k in ids),5)
        self.assertEqual(sum(k.startswith("experimental_h1:") for k in ids),15)
        self.assertEqual(sum(k.startswith("usdcad_m15:") for k in ids),1)
        self.assertEqual(sum(k.startswith("momentum60_h4:") for k in ids),1)

    def test_missing_data_explicitly_unknown_not_fake_zero(self):
        data={"EURUSD":hourly()}
        with patch.object(bt,"HIST_START",START),patch.object(bt,"HIST_END",END):
            result=bt.run(datasets=data,m15rows=None,obtain=False,stress=False)
        self.assertEqual(result["planned"],27)
        self.assertEqual(result["analyzed"],3)
        self.assertEqual(result["unavailable"],24)
        self.assertIsNone(result["robots"]["gold_h4:channel20"]["net_realized_usd"])
        self.assertIsNone(result["robots"]["usdcad_m15:bb20"]["net_realized_usd"])
        self.assertEqual(len(result["robots"]),27)

    def test_replay_all_with_synthetic_prices_never_touch_state(self):
        data={market:hourly(shift=100*j)
              for j,market in enumerate(bt.MARKETS)}
        m15=quarter()
        original=deepcopy(data),deepcopy(m15)
        with patch.object(bt,"HIST_START",START),patch.object(bt,"HIST_END",END):
            result=bt.run(datasets=data,m15rows=m15,obtain=False,stress=True)
        self.assertEqual(data,original[0])
        self.assertEqual(m15,original[1])
        self.assertEqual(result["analyzed"],27)
        self.assertEqual(result["unavailable"],0)
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["broker_orders"])
        self.assertEqual(len(result["robots"]),27)
        for v in result["robots"].values():
            self.assertIsNotNone(v["double_cost_net_usd"])
            self.assertGreaterEqual(v["closed_trades"],0)
            self.assertIn("P&L realizado",v["note"])
        doc=bt.markdown(result)
        self.assertIn("backtest dos 27",doc)
        self.assertIn("Momentum60",doc)
        self.assertIn("BB20",doc)

    def test_entries_after_prior_closed_bar_no_live_orders(self):
        data=hourly()
        with patch.object(bt,"HIST_START",START),patch.object(bt,"HIST_END",END):
            results=bt._h4_replay(data,stress=1.)
        self.assertIn("gold_h4:rsi_trend",results)
        self.assertIn("leveraged_h4:lev_channel20",results)
        self.assertIn("momentum60_h4:momentum60",results)
        self.assertEqual(results["gold_h4:rsi_trend"]["interval"],"H4")

    def test_invalid_ohlc_rejected(self):
        rows=hourly()
        rows[6]["low"]=-20
        with self.assertRaisesRegex(ValueError,"preco invalido"):
            bt._validate(rows,3600,500)


if __name__=="__main__":
    unittest.main()
