"""Causality, control isolation and matched backtest policy for V2 research."""
import unittest
from research.indicator_fusion_v2 import signal_v2,matched_review,V2_BOTS
from research.indicator_fusion_bots import make_features, signals, WARMUP
from tests.test_indicator_fusion_bots import sample

class IndicatorFusionV2Tests(unittest.TestCase):
    def test_causal_prefix(self):
        bars=sample(310)
        f=make_features(bars)
        s=signal_v2(bars,f)
        extra={'time':bars[-1]['time']+900,'open':10000.,'high':11000.,
               'low':9000.,'close':10500.,'volume':130}
        b2=bars+[extra]
        s2=signal_v2(b2,make_features(b2))
        self.assertEqual(set(s),set(V2_BOTS))
        for name in V2_BOTS:
            self.assertEqual(s[name],s2[name][:len(bars)])

    def test_controls_not_modified(self):
        bars=sample(360)
        v1=signals(bars,make_features(bars))
        a=matched_review(bars,'M15')
        self.assertEqual(len(a['bots']),len(V2_BOTS)+len(v1))
        self.assertFalse(a['approved_for_live'])
        for name in v1:
            self.assertIn('V1_'+name,a['bots'])
            self.assertEqual(a['bots']['V1_'+name]['signal_count'],sum(bool(v) for v in v1[name]))

    def test_no_fake_positive_on_flat_market(self):
        bars=sample(360)
        s=signal_v2(bars,make_features(bars))
        for bot in V2_BOTS:
            self.assertTrue(all(v==0 for v in s[bot]))

    def test_same_v1_risk_and_fees_scenarios(self):
        report=matched_review(sample(370),'M15')
        for name,row in report['bots'].items():
            self.assertEqual(set(row['by_cost']),{'0.0','7.0','14.0','28.0'})
            self.assertFalse(row['live_approved'])
            self.assertEqual(len(row['folds']),3)
            self.assertTrue(all(r['closed_trades']==row['by_cost']['0.0']['closed_trades'] for r in row['by_cost'].values()))

    def test_retest_never_emits_on_breakout_bar(self):
        # Craft 55-bar channel breakout with trend, then optional retest.
        bars=sample(300)
        i=250
        old_h=max(b['high'] for b in bars[i-55:i])
        bars[i].update(open=old_h,high=old_h+4,low=old_h-.5,close=old_h+3)
        feats=make_features(bars)
        out=signal_v2(bars,feats)
        self.assertEqual(out['CHANNEL55_RETEST'][i],0)

    def test_channel55_retest_is_causal_and_emits_later(self):
        bars=[]
        for i in range(310):
            p=2000.+0.012*i
            bars.append({'time':1700000100+i*900,'open':p,
                         'high':p+.65,'low':p-.65,'close':p+.05,'volume':100.})
        i=250
        resistance=max(b['high'] for b in bars[i-55:i])
        bars[i].update(open=resistance+.1,high=resistance+2.5,
                       low=resistance-.05,close=resistance+1.65)
        # Next candle touches the former resistance, then rejects upward.
        bars[i+1].update(open=resistance-.1,high=resistance+2.0,
                         low=resistance-.2,close=resistance+1.1)
        features=make_features(bars)
        out=signal_v2(bars,features)
        self.assertEqual(out['CHANNEL55_CONTROL'][i],1)
        self.assertEqual(out['CHANNEL55_RETEST'][i],0)
        self.assertEqual(out['CHANNEL55_RETEST'][i+1],1)
        self.assertTrue(all(out['CHANNEL55_RETEST'][j]==0 for j in range(i)))

    def test_missing_or_bad_history_rejected(self):
        with self.assertRaises(ValueError):
            matched_review(sample(150),'M15')

if __name__=='__main__': unittest.main()