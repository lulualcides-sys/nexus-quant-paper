import unittest
from math import sin
from research.indicator_fusion_v3_frequency import (NAMES,WARMUP,features_and_signals,portfolio,research)


def bars(n=400,step=300):
    out=[]
    for i in range(n):
        x=4000+0.025*i+5*sin(i/6)
        op=x-0.4*sin(i)
        cl=x+0.4*sin(i)
        out.append({'time':1700000100+step*i,'open':op,'close':cl,
                    'high':max(op,cl)+1.5,'low':min(op,cl)-1.5})
    return out


def one_signal(b,entry_signal_i,side=1,name=NAMES[0]):
    sig={n:[0]*len(b) for n in NAMES}
    sig[name][entry_signal_i]=side
    return sig

class FreqTests(unittest.TestCase):
    def test_causal_signals_unchanged_by_future_append(self):
        b=bars(420)
        a,s=features_and_signals(b)
        a2,s2=features_and_signals(b+bars(15)[0:0])
        self.assertEqual(s,s2)
        more=bars(440)
        a3,s3=features_and_signals(more)
        for name in NAMES:self.assertEqual(s[name],s3[name][:len(b)])
    def test_no_trade_without_signal(self):
        b=bars();atr=[3.]*len(b)
        z=portfolio(b,atr,one_signal(b,-1),interval=300)
        self.assertEqual(z['closed_trades'],0)
    def test_entry_next_open_only(self):
        b=bars();atr=[3.]*len(b)
        sig=one_signal(b,250)
        r=portfolio(b,atr,sig,interval=300,fee_bps=0)
        self.assertTrue(r['ledger']);self.assertEqual(r['ledger'][0]['entry_i'],251)
    def test_no_reentry_on_intrabar_exit(self):
        b=bars();atr=[2.]*len(b)
        sig=one_signal(b,250)
        sig[NAMES[0]][251]=1
        entry=b[251]['open']
        # Bar of entry remains inside stop/target boundaries.
        b[251].update(high=entry+0.5, low=entry-0.5, close=entry)
        # Next bar exits prior long intrabar; its OPEN is already in the past.
        b[252]['open']=entry
        b[252]['high']=entry+0.5
        b[252]['low']=entry-3.0
        b[252]['close']=entry-1.0
        r=portfolio(b,atr,sig,interval=300)
        self.assertEqual(r['ledger'][0]['entry_i'],251)
        self.assertEqual(r['ledger'][0]['exit_i'],252)
        self.assertNotIn(252,[t['entry_i'] for t in r['ledger']])
    def test_no_fill_over_data_gap(self):
        b=bars();b[251]['time']+=600
        for j in range(252,len(b)):b[j]['time']+=600
        atr=[3.]*len(b)
        sig=one_signal(b,250)
        r=portfolio(b,atr,sig,interval=300)
        self.assertEqual(r['entered_by_type'],{})
        self.assertEqual(r['blocked_at_data_gap'][NAMES[0]],1)
    def test_same_signals_two_cost_scenarios(self):
        b=bars();atr,sig=features_and_signals(b)
        x=portfolio(b,atr,sig,interval=300,fee_bps=0)
        y=portfolio(b,atr,sig,interval=300,fee_bps=28)
        self.assertEqual([t['entry_i'] for t in x['ledger']],[t['entry_i'] for t in y['ledger']])
        self.assertLessEqual(y['net_usd'],x['net_usd']+0.01)
    def test_unique_portfolio_no_overlap(self):
        b=bars();atr=[3.]*len(b)
        sig={n:[0]*len(b) for n in NAMES}
        for k in NAMES:sig[k][250]=1
        r=portfolio(b,atr,sig,interval=300)
        self.assertEqual(sum(r['entered_by_type'].values()),1)
        self.assertEqual(r['signals_total'],5)
    def test_risk_and_notional_caps(self):
        b=bars();atr=[0.1]*len(b)
        sig=one_signal(b,250)
        r=portfolio(b,atr,sig,interval=300)
        self.assertLessEqual(r['ledger'][0]['qty']*r['ledger'][0]['entry'],5000.001)
    def test_gaps_prioritized_on_open(self):
        b=bars();atr=[1.]*len(b)
        sig=one_signal(b,250)
        entry=b[251]['open']
        b[251]['high']=max(b[251]['high'],entry+2.6)
        b[251]['low']=min(b[251]['low'],entry-1.5)
        r=portfolio(b,atr,sig,interval=300)
        self.assertEqual(r['ledger'][0]['reason'],'stop')
    def test_refuse_monthly_quota_fabrication(self):
        b=bars();r=research(b,timeframe='M5')
        self.assertEqual(r['target_monthly_completed_trades'],200)
        self.assertFalse(r['qualified_for_live'])
        self.assertTrue(r['by_cost']['14.0']['closed_trades']<200)
    def test_flat_data_no_phantom_signals(self):
        b=bars()
        for j,x in enumerate(b):
            x.update(open=4000,close=4000,high=4001,low=3999)
        _,s=features_and_signals(b)
        self.assertEqual(sum(bool(v) for seq in s.values() for v in seq),0)

if __name__=='__main__':unittest.main()