"""Invariant tests for old gold research families on spot quote-side H4 replay."""
import csv
import io
import unittest
from datetime import datetime,timezone
from research import xau_v7_preserved_h4_bidask as x


def mockbars(n=260,base=4000):
    start=int(datetime(2026,6,1,tzinfo=timezone.utc).timestamp())
    rows=[]
    for i in range(n):
        p=base+2*i
        bid=dict(open=p-.4,high=p+9,low=p-9,close=p+1-.4)
        ask=dict(open=p+.4,high=p+10,low=p-8,close=p+1+.4)
        rows.append({'time':start+i*14400, 'open':p,'high':p+9.5,'low':p-8.5,'close':p+1,'bid':bid,'ask':ask})
    return rows


def features(n):
    return [dict(atr=3., e50=10.,e200=9.,rsi=50., e20=11.,upper20=8.,lower20=1.,
                 upper55=8.,lower55=1., avg_atr=2.5) for _ in range(n)]


class V7(unittest.TestCase):
    def test_four_predeclared_cost_cases(self):
        self.assertEqual(len(x.SCENARIOS),4)
        self.assertEqual(x.RULES,('channel20','channel55','momentum100','rsi_trend','pullback20'))
    def test_invalid_month_format(self):
        raw=b'timestamp,open,high,low,close\n0,4,5,3,4\n'
        with self.assertRaises(ValueError):x.read_monthly_side(raw,2026,4)
    def test_spot_read_rejects_future_date(self):
        ts=int(datetime(2026,5,1,tzinfo=timezone.utc).timestamp())*1000
        row=f'timestamp,open,high,low,close\n{ts},4000,4010,3990,4002\n'.encode()
        with self.assertRaises(ValueError):x.read_monthly_side(row,2026,4)
    def test_no_signals_no_trades(self):
        rows=mockbars();f=features(len(rows))
        v=x.backtest(rows,f,'channel20',begin=rows[245]['time'],finish=rows[-1]['time']+14400,signal_fn=lambda *a:0)
        self.assertEqual(v['closed_trades'],0)
    def test_new_signal_next_candle_and_ask_entry_long(self):
        rows=mockbars();f=features(len(rows));start=rows[244]['time'];end=rows[249]['time']+14400
        sig=lambda name,bars,feat,i: 1 if i==243 else 0
        r=x.backtest(rows,f,'channel20',begin=start,finish=end,signal_fn=sig,lot_step=0.,slippage=0.)
        self.assertGreaterEqual(r['entries'],1)
        self.assertEqual(r['ledger'][0]['entry_i'],244)
        self.assertAlmostEqual(r['ledger'][0]['entry'],rows[244]['ask']['open'])
    def test_no_entry_on_missing_h4_gap(self):
        rows=mockbars();rows[244]['time']+=14400;f=features(len(rows))
        sig=lambda name,bars,feat,i: 1 if i==243 else 0
        r=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[249]['time']+14400,signal_fn=sig,lot_step=0.)
        self.assertEqual(r['entries'],0)
        self.assertGreater(r['blocked'].get('gap_at_entry',0),0)
    def test_fractional_not_equal_to_lot_minimum(self):
        rows=mockbars();f=features(len(rows));f[243]['atr']=60.
        sig=lambda name,bars,feat,i: 1 if i==243 else 0
        a=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[249]['time']+14400,signal_fn=sig,lot_step=0.)
        b=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[249]['time']+14400,signal_fn=sig,lot_step=1.)
        self.assertEqual(a['entries'],1);self.assertEqual(b['entries'],0)
        self.assertEqual(b['blocked'].get('minimum_lot_or_risk'),1)
    def test_short_uses_bid_entry_ask_exit(self):
        rows=mockbars();f=features(len(rows));sig=lambda name,bars,feat,i: -1 if i==243 else 0
        r=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[247]['time']+14400,signal_fn=sig,lot_step=0.,slippage=0.)
        self.assertEqual(r['entries'],1)
        self.assertAlmostEqual(r['ledger'][0]['entry'],rows[244]['bid']['open'])
    def test_slippage_cannot_improve_same_entry_exit(self):
        rows=mockbars();f=features(len(rows));sig=lambda name,bars,feat,i: 1 if i==243 else 0
        a=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[247]['time']+14400,signal_fn=sig,lot_step=0.,slippage=0.)
        b=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[247]['time']+14400,signal_fn=sig,lot_step=0.,slippage=.15)
        self.assertLessEqual(b['net_usd'],a['net_usd']+.001)
    def test_cannot_call_unsupported_rule(self):
        rows=mockbars();f=features(len(rows))
        with self.assertRaises(ValueError):x.backtest(rows,f,'custom',begin=rows[244]['time'],finish=rows[247]['time']+14400)
    def test_position_no_reentry_after_stop(self):
        rows=mockbars();f=features(len(rows));sig=lambda n,b,z,i:1 if i in (243,244) else 0
        r=x.backtest(rows,f,'channel20',begin=rows[244]['time'],finish=rows[247]['time']+14400,signal_fn=sig,lot_step=0.)
        self.assertLessEqual(r['entries'],1)
    def test_no_live_approval(self):
        self.assertNotIn('orders',x.study.__code__.co_names)

if __name__=='__main__':unittest.main()