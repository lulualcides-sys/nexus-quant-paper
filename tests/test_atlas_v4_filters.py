"""Deterministic ATLAS V4 research safety regressions. NO market fixtures."""
import unittest
from datetime import datetime,timedelta,timezone
from research.atlas_v4_filters import candidate,CANDIDATES
from research.atlas_v4_study import selected_month,coverage,PERIODS,approval_gate
from research.win_price_data import TZ

def bars(n=150,start=None):
    t=start or datetime(2026,5,18,9,10,tzinfo=TZ)
    out=[]
    for k in range(n):
        out.append({"time":int((t+timedelta(minutes=k)).astimezone(timezone.utc).timestamp()),
                    "open":200000,"high":200020,"low":199980,
                    "close":200000,"volume":300})
    return out

class AtlasV4Tests(unittest.TestCase):
    def test_independent_sweep_quality_detects_direction(self):
        a=bars()
        a[125]={**a[125],"open":199995,"high":200030,
                "low":199970,"close":200020,"volume":500}
        self.assertEqual(candidate(a,125,"v4_sweep_quality"),1)
        self.assertEqual(candidate(a,125,"v4_sweep_vwap"),1)
        self.assertEqual(candidate(a,125,"v4_sweep_trend"),0)

    def test_breakout_retest_is_not_the_old_sweep(self):
        a=bars()
        a[125]={**a[125],"open":200000,"high":200055,
                "low":199980,"close":200045,"volume":500}
        self.assertEqual(candidate(a,125,"v4_breakout_retest"),1)
        self.assertEqual(candidate(a,125,"v4_sweep_quality"),0)

    def test_no_future_candle_leakage(self):
        a=bars(160)
        a[125]={**a[125],"open":199995,"high":200030,
                "low":199970,"close":200020,"volume":500}
        r=[candidate(a,125,v) for v in CANDIDATES]
        a[126]={**a[126],"open":190000,"high":350000,"low":100000,
                "close":200000,"volume":9999999}
        self.assertEqual(r,[candidate(a,125,v) for v in CANDIDATES])

    def test_zero_or_insufficient_liquidity_rejected(self):
        a=bars()
        a[125]={**a[125],"open":199995,"high":200030,
                "low":199970,"close":200020,"volume":500}
        for b in a:
            b["volume"]=10
        self.assertEqual(candidate(a,125,"v4_sweep_quality"),0)

    def test_opening_first_25_minutes_excluded(self):
        a=bars()
        a[120]={**a[120],"open":199995,"high":200030,
                "low":199970,"close":200020,"volume":500}
        self.assertEqual(candidate(a,120,"v4_sweep_quality"),1)
        b=bars(n=151,start=datetime(2026,5,18,7,20,tzinfo=TZ))
        b[120]={**b[120],"open":199995,"high":200030,
                "low":199970,"close":200020,"volume":500}
        self.assertEqual(candidate(b,120,"v4_sweep_quality"),0)

    def test_evaluation_periods_predeclared(self):
        self.assertEqual([x[0] for x in PERIODS],
                         ["development_2026_05","audit_2026_06","audit_2026_07"])
        self.assertEqual(len(CANDIDATES),6)
        a=bars()
        self.assertEqual(selected_month(a,"2026-05-01","2026-06-01")[0],None)
        self.assertEqual(coverage(a,"2026-05-01","2026-06-01")["session_days"],1)

    def test_v4_gate_rejects_few_trades_and_never_autopromotes(self):
        little={"closed":7,"net_brl":100,"profit_factor":1.5,
                "open_at_end":False,"pending_at_end":False}
        plenty={**little,"closed":35}
        def record(d):
            return {"status":"BACKTESTED","variants":{
                var:{"1":d,"2":d} for var in CANDIDATES}}
        result={"periods":{name:record(little) for name,_,_ in PERIODS}}
        fail=approval_gate(result)
        self.assertEqual(fail["passed"],0)
        self.assertFalse(fail["auto_promote"])
        result={"periods":{name:record(plenty) for name,_,_ in PERIODS}}
        passed=approval_gate(result)
        self.assertEqual(passed["passed"],len(CANDIDATES))
        self.assertFalse(passed["auto_promote"])

    def test_unsafe_variants_not_accepted(self):
        with self.assertRaisesRegex(ValueError,"Unregistered"):
            candidate(bars(),120,"v4_magic_100pct")

if __name__=="__main__":
    unittest.main()
