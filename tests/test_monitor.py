import math,unittest
from src.feed import MARKETS,parse_yahoo
from src.monitor import empty_state,scan_market,report,date_local
from src.strategies import CONFIGS,signal,make_indicators
BASE=1780000000
def sample(n=380):
    bars=[];p=1.3
    for i in range(n):
        q=p+.001+math.sin(i/7)*.0003
        bars.append({"time":BASE+i*3600,"open":p,"high":max(p,q)+.0007,"low":min(p,q)-.0007,"close":q})
        p=q
    return bars
class QuantTests(unittest.TestCase):
    def test_five_assets_five_strategies(self):
        self.assertEqual(len(MARKETS),5)
        self.assertEqual(len(CONFIGS),5)
    def test_no_backfilled_signal_on_initialization(self):
        state=empty_state()
        self.assertEqual(scan_market(state,"EURUSD",sample()),0)
        self.assertEqual(state["markets"]["EURUSD"]["signals"],[])
    def test_no_lookahead(self):
        a=sample();i=300
        initial=[signal(k,a,make_indicators(a),i) for k in CONFIGS]
        b=sample();b[i+1]["close"]*=2
        b[i+1]["high"]*=2
        self.assertEqual(initial,[signal(k,b,make_indicators(b),i) for k in CONFIGS])
    def test_report_discloses_no_fbs_fills(self):
        s=empty_state();bars=sample()
        for k in MARKETS:scan_market(s,k,bars)
        msg=report(s,{k:bars for k in MARKETS},date_local(bars[-1]["time"]+3600))
        self.assertIn("sem ordens FBS",msg)
        self.assertIn("não há P&L comprovado",msg)
    def test_finished_candles_only(self):
        data={"chart":{"result":[{"timestamp":[BASE+i*3600 for i in range(305)],
              "indicators":{"quote":[{k:[1.2]*305 for k in ("open","high","low","close")}]}}]}}
        now=BASE+302*3600+120
        rows=parse_yahoo(data,now)
        self.assertTrue(all(b["time"]+3600+180<=now for b in rows))
if __name__=="__main__":unittest.main()
