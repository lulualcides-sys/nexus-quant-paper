"""Unit tests for causal signal handling, execution, safeguards and fold integrity."""
import unittest
from research.indicator_fusion_bots import (BOTS, WARMUP, check_bars, make_features,
                                            signals, replay, research)


def sample(n=320, dt=900):
    out=[]
    for i in range(n):
        p=2000+i*.08 + (i%7)*.14
        out.append({'time':1700000100+i*dt,'open':p,'high':p+1.2,'low':p-1.2,'close':p+.3,'volume':100+i%31})
    return out


def empty_features(n, atr=5):
    return [{'atr':atr} for _ in range(n)]


class IndicatorFusionTest(unittest.TestCase):
    def test_causal_prefix(self):
        short=sample(290)
        long=short+[{'time':short[-1]['time']+900,'open':1000,'high':9999,
                     'low':1,'close':9998,'volume':1000}]
        sf=make_features(short); lf=make_features(long)
        self.assertEqual(sf,lf[:len(short)])
        self.assertEqual(signals(short,sf),{k:v[:len(short)] for k,v in signals(long,lf).items()})

    def test_no_signals_with_flat_market(self):
        bars=sample()
        f=make_features(bars);s=signals(bars,f)
        self.assertEqual(set(s),set(BOTS))
        self.assertTrue(all(x==0 for x in s['BOS_DTC_QKE']))

    def test_invalid_data_rejected(self):
        b=sample();b[100]['time']=b[99]['time']
        with self.assertRaises(ValueError): check_bars(b)
        b=sample();b[20]['low']=b[20]['high']+1
        with self.assertRaises(ValueError): check_bars(b)

    def test_next_bar_open_and_roundtrip_cost(self):
        b=sample()
        s=[0]*len(b);s[WARMUP]=1
        # one trade, held and time-exited
        f=empty_features(len(b),atr=100)
        a=replay(b,s,f,cost_bps=7,interval=900)
        z=replay(b,s,f,cost_bps=28,interval=900)
        self.assertEqual(a['trades'],1)
        self.assertEqual(a['ledger'][0]['entry_i'],WARMUP+1)
        self.assertAlmostEqual(a['ledger'][0]['entry'],b[WARMUP+1]['open'])
        self.assertLess(z['ledger'][0]['net'],a['ledger'][0]['net'])
        self.assertEqual([(t['entry_i'],t['exit_i'],t['qty']) for t in a['ledger']],
                         [(t['entry_i'],t['exit_i'],t['qty']) for t in z['ledger']])

    def test_intrabar_exit_must_not_reenter_retroactively_at_open(self):
        b=sample(280)
        first=WARMUP+1
        second=first+1
        # First position survives its entry candle, then stops within next bar.
        b[second]['open']=b[first]['open']
        b[second]['high']=b[second]['open']+1.
        b[second]['low']=b[second]['open']-20.
        b[second]['close']=b[second]['open']-1.
        s=[0]*len(b)
        s[first-1]=1
        s[second-1]=1
        r=replay(b,s,empty_features(len(b),atr=5),interval=900,
                 start=first,end=second+1)
        self.assertEqual(r['trades'],1)
        self.assertEqual(r['ledger'][0]['entry_i'],first)
        self.assertEqual(r['ledger'][0]['exit_i'],second)
        self.assertFalse(r['open_at_end'])

    def test_decompose_cost_impact_with_zero_cost_control(self):
        b=sample(295);s=[0]*len(b);s[WARMUP]=1
        f=empty_features(len(b),atr=100)
        z=replay(b,s,f,cost_bps=0.,interval=900)
        v=replay(b,s,f,cost_bps=14.,interval=900)
        self.assertEqual(z['trades'],v['trades'])
        self.assertEqual(z['closed_fees_usd'],0)
        self.assertAlmostEqual(v['closed_gross_usd']-v['closed_fees_usd'],v['closed_net_usd'],places=2)

    def test_cost_floor_prevents_cost_dominated_trades(self):
        b=sample();s=[0]*len(b);s[WARMUP]=1
        r=replay(b,s,empty_features(len(b),atr=.01),interval=900)
        self.assertEqual(r['trades'],0)

    def test_stop_before_target_same_bar(self):
        b=sample();idx=WARMUP+1
        b[idx]['open']=2200;b[idx]['high']=2230;b[idx]['low']=2170;b[idx]['close']=2200
        s=[0]*len(b);s[WARMUP]=1
        r=replay(b,s,empty_features(len(b),atr=4),cost_bps=14,interval=900)
        t=r['ledger'][0]
        self.assertEqual(t['entry_i'],idx)
        self.assertEqual(t['exit_i'],idx)
        self.assertEqual(t['exit_reason'],'stop_first')
        self.assertLess(t['net'],0)

    def test_gap_skips_entry(self):
        b=sample();idx=WARMUP+1
        for i in range(idx,len(b)):
            b[i]['time']+=900
        s=[0]*len(b);s[WARMUP]=1
        r=replay(b,s,empty_features(len(b)),interval=900)
        self.assertEqual(r['trades'],0)

    def test_research_all_cannot_live_approve(self):
        b=sample(360)
        r=research(b,timeframe='M15')
        self.assertFalse(r['approved_for_live'])
        self.assertEqual(len(r['strategies']),4)
        for bot in r['strategies'].values():
            self.assertFalse(bot['live_approved'])
            self.assertEqual(len(bot['folds']),3)
            self.assertTrue(bot['folds'][0]['end'] < bot['folds'][1]['start'])

    def test_no_history_no_fake_profit(self):
        with self.assertRaises(ValueError): research(sample(200),timeframe='M15')

    def test_only_completed_previous_candle_enters(self):
        b=sample(300)
        s=[0]*len(b)
        s[WARMUP+1]=1
        f=empty_features(len(b),atr=100)
        r=replay(b,s,f,start=WARMUP+1,end=WARMUP+2,interval=900)
        self.assertEqual(r['trades'],0)
        r2=replay(b,s,f,start=WARMUP+1,end=WARMUP+3,interval=900)
        self.assertTrue(r2['open_at_end'])

if __name__=='__main__': unittest.main()