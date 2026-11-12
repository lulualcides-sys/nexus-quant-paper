"""V5 causal execution and two-source audit unit tests (no market orders)."""
import copy
import json
import math
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from research.indicator_fusion_v3_frequency import NAMES, portfolio as v3_portfolio
from research.indicator_fusion_v5_exits import (
    _trailing_stop, ablated_signals, replay_v5, paired_runs,
    DEFAULT_PARAMETERS, EXIT_POLICIES, DISABLED_SIGNAL,
)
from research.run_indicator_fusion_v5_exits import match_sessions, load_frozen_yahoo


def sample(n=350, start=1700000100):
    rows=[]
    for i in range(n):
        price=4100+.06*i+3*math.sin(i/6)
        rows.append({'time':start+300*i, 'open':price-.2,
                     'close':price+.2,'high':price+1.5,'low':price-1.5,
                     'max_spread':.7+.02*(i%5)})
    return rows


def signals(n,at,model='EMA20_RECLAIM',side=1):
    x={name:[0]*n for name in NAMES}
    x[model][at]=side
    return x


def session_rows(days=20):
    first=datetime(2026,10,12,12,0,tzinfo=timezone.utc)
    rows=[]
    for d in range(days):
        date=first+timedelta(days=d)
        for i in range(108):
            ts=int((date+timedelta(minutes=i*5)).timestamp())
            price=4120+.06*i+2*math.sin((d*108+i)/8)
            rows.append({'time':ts,'open':price-.2,'close':price+.2,
                         'high':price+1.5,'low':price-1.5,'max_spread':.7})
    return rows


class V5UnitTests(unittest.TestCase):
    def test_policy_names_and_no_additional_signal_filters(self):
        self.assertEqual(EXIT_POLICIES, ('fixed_v4','breakeven_1p5R','close_trail_2R'))
        self.assertEqual(DISABLED_SIGNAL,'MOMENTUM_2BAR')
        rows=sample(400)
        a,s=ablated_signals(rows)
        self.assertEqual(len(a),len(rows))
        self.assertTrue(all(not v for v in s['MOMENTUM_2BAR']))
        self.assertEqual(set(s),set(NAMES))

    def test_v4_exact_execution_parity_synthetic(self):
        rows=sample(450);atr,signals_=ablated_signals(rows)
        for fee in (.61,1.81,3.31):
            old=v3_portfolio(rows,atr,signals_,fee_bps=0.,fee_per_oz=fee,**DEFAULT_PARAMETERS)
            new=replay_v5(rows,atr,signals_,policy='fixed_v4',fee_bps=0.,fee_per_oz=fee,
                          **DEFAULT_PARAMETERS)
            self.assertEqual(old['closed_trades'],new['closed_trades'])
            self.assertEqual(old['net_usd'],new['net_usd'])
            self.assertEqual(old['gross_usd'],new['gross_usd'])
            self.assertEqual(old['fees_usd'],new['fees_usd'])
            self.assertEqual([(t['entry_i'],t['exit_i'],t['reason']) for t in old['ledger']],
                             [(t['entry_i'],t['exit_i'],t['reason']) for t in new['ledger']])

    def test_signal_is_placed_at_following_open(self):
        b=sample(300);s=signals(len(b),240);rr=replay_v5(b,[1.]*len(b),s,fee_per_oz=0,
                                                          max_hold=2,**{k:v for k,v in DEFAULT_PARAMETERS.items() if k!='max_hold'})
        self.assertEqual(rr['ledger'][0]['entry_i'],241)
        self.assertAlmostEqual(rr['ledger'][0]['entry'],b[241]['open'])

    def test_closed_bar_break_even_applied_only_next_candle(self):
        b=sample(280)
        # Force a bar that ends +1.6R after entry (R = 3), but intrabar low
        # below new breakeven; no same-bar stop retroactively inserted.
        price=b[241]['open']
        b[241].update(high=price+6,low=price-.5,close=price+5,open=price)
        # Next bar opens below breakeven but above original stop.
        b[242].update(open=price,close=price+.5,high=price+1,low=price-.5)
        s=signals(len(b),240)
        rr=replay_v5(b,[1.]*len(b),s,policy='breakeven_1p5R',fee_per_oz=0,
                     **DEFAULT_PARAMETERS)
        tr=rr['ledger'][0]
        self.assertEqual((tr['entry_i'],tr['exit_i'],tr['reason']),(241,242,'stop_gap'))

    def test_high_without_close_does_not_trigger_trailing(self):
        p=dict(side=1,entry=4100.,stop=4097.,dist=3.,best_close=4100.)
        self.assertEqual(_trailing_stop(p,4101.,1.,'breakeven_1p5R'),4097.)
        self.assertEqual(_trailing_stop(p,4101.,1.,'close_trail_2R'),4097.)

    def test_trailing_never_loosens_and_stays_below_long_close(self):
        p=dict(side=1,entry=4100.,stop=4097.,dist=3.,best_close=4100.)
        new=_trailing_stop(p,4107.,1.,'close_trail_2R')
        self.assertGreater(new,p['stop'])
        self.assertLess(new,4107.)
        p['stop']=new
        self.assertGreaterEqual(_trailing_stop(p,4102.,1.,'close_trail_2R'),new)

    def test_trailing_never_loosens_short(self):
        p=dict(side=-1,entry=4100.,stop=4103.,dist=3.,best_close=4100.)
        new=_trailing_stop(p,4092.,1.,'close_trail_2R')
        self.assertLess(new,p['stop'])
        self.assertGreater(new,4092.)
        p['stop']=new
        self.assertLessEqual(_trailing_stop(p,4099.,1.,'close_trail_2R'),new)

    def test_no_reentry_after_intrabar_exit(self):
        b=sample(280);p=b[241]['open']; s=signals(len(b),240)
        s['CHANNEL12_BREAK'][241]=1
        b[241].update(open=p,high=p+.5,low=p-.5,close=p)
        b[242].update(open=p,high=p+.5,low=p-4.,close=p-2.)
        r=replay_v5(b,[1.]*len(b),s,fee_per_oz=0,**DEFAULT_PARAMETERS)
        self.assertEqual(r['ledger'][0]['exit_i'],242)
        self.assertNotIn(242,[t['entry_i'] for t in r['ledger']])

    def test_cost_mode_uses_candle_spread_as_diagnostic_not_signal(self):
        b=sample(270);s=signals(len(b),240)
        x=replay_v5(b,[1.]*len(b),s,policy='fixed_v4',max_hold=2,
                    cost_mode='observed_spread_max',slip_per_side=.15,
                    **{k:v for k,v in DEFAULT_PARAMETERS.items() if k!='max_hold'})
        self.assertEqual(len(x['ledger']),1)
        tr=x['ledger'][0]
        spread=.5*(b[tr['entry_i']]['max_spread']+b[tr['exit_i']]['max_spread'])+.3
        self.assertAlmostEqual(tr['cost'],tr['qty']*spread,places=7)

    def test_reject_missing_spread_in_variable_scenario(self):
        b=sample(270);del b[240]['max_spread']
        with self.assertRaises(ValueError):
            replay_v5(b,[1.]*len(b),signals(len(b),240),cost_mode='observed_spread_max',
                      **DEFAULT_PARAMETERS)

    def test_session_flat_closes_before_missing_overnight(self):
        b=session_rows(5);sig=signals(len(b),240)
        price=b[241]['open']
        for j in range(241,324):
            b[j].update(open=price,close=price,high=price+.2,low=price-.2)
        cfg={**DEFAULT_PARAMETERS,'max_hold':1000}
        r=replay_v5(b,[1.]*len(b),sig,fee_per_oz=.61,
                    daily_flat_hour_utc=20,**cfg)
        t=r['ledger'][0]
        self.assertEqual(t['reason'],'session_flat')
        self.assertEqual(datetime.fromtimestamp(t['exit_time'],timezone.utc).strftime('%H:%M'),'20:55')

    def test_session_cannot_open_on_flat_bar(self):
        b=session_rows(5);idx=323
        sig=signals(len(b),idx)
        # Signal at third day's last bar 20:55; next day 12:00 is gap,
        # so the position must not fill with phantom overnight prices.
        r=replay_v5(b,[1.]*len(b),sig,fee_per_oz=0,daily_flat_hour_utc=20,**DEFAULT_PARAMETERS)
        self.assertEqual(r['closed_trades'],0)

    def test_common_timestamp_matching_drops_missing_bar_without_faking(self):
        b=session_rows(20)
        d=copy.deepcopy(b)
        y=copy.deepcopy(b)
        del y[250]
        yy,dd,meta=match_sessions(y,d)
        self.assertTrue(meta['identical_timestamps'])
        self.assertEqual(len(yy),len(dd))
        self.assertEqual(len(yy),len(y))
        self.assertNotIn(b[250]['time'],[q['time'] for q in yy])

    def test_full_research_returns_no_live_approval(self):
        z=paired_runs(sample(450),dataset_name='synthetic unit-test',partial_sessions=False)
        self.assertTrue(z['paper_only'])
        self.assertFalse(z['approved_for_live'])
        for pol,r in z['by_policy'].items():
            self.assertEqual(len(r['folds']),3)
            self.assertFalse(r['approved_for_live'])

    def test_frozen_price_fingerprint_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'x.json.gz'
            f.write_bytes(b'bad data')
            with self.assertRaises(ValueError):
                load_frozen_yahoo(f)

    def test_no_forced_200_trade_quota(self):
        r=replay_v5(sample(300),[1.]*300,signals(300,250),fee_per_oz=.61,**DEFAULT_PARAMETERS)
        self.assertLess(r['closed_trades'],200)


if __name__=='__main__': unittest.main()