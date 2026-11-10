"""Bounded, deterministic regression tests for historical BID/ASK V6 paper engine."""
import lzma
import struct
import unittest
from datetime import date,datetime,timezone
from research import xau_v6_bidask_research as m


def synthetic_quotes(n=290, *,spread=.30):
    start=int(datetime(2026,7,1,tzinfo=timezone.utc).timestamp())
    arr=[]
    for i in range(n):
        mid=3500 + i*.05
        def side(price):return dict(open=price,close=price,high=price+.40,low=price-.40)
        b=side(mid-spread/2);a=side(mid+spread/2)
        arr.append({'time':start+i*300,'open':mid,'close':mid,'high':mid+.40,'low':mid-.40,
                    'bid':b,'ask':a,'open_spread':spread,'close_spread':spread})
    return arr

class ResearchV6Tests(unittest.TestCase):
    def test_url_has_zero_based_month(self):
        self.assertTrue(m._day_url(date(2026,7,1),'BID').endswith('/2026/06/01/BID_candles_min_1.bi5'))
        with self.assertRaises(ValueError):m._day_url(date(2026,7,1),'MID')
    def test_raw_decode_different_side_and_field_order(self):
        raw=struct.pack('>IIIIIf',60,3501000,3503000,3499000,3504000,1.0)
        b=lzma.compress(raw,format=lzma.FORMAT_ALONE)
        x=m.decode_bi5_minute(b,date(2026,7,1))[0]
        self.assertEqual((x['open'],x['close'],x['low'],x['high']),(3501.,3503.,3499.,3504.))
    def test_raw_decode_rejects_duplicate(self):
        row=struct.pack('>IIIIIf',60,3501000,3503000,3499000,3504000,1.0)
        with self.assertRaises(ValueError):m.decode_bi5_minute(lzma.compress(row*2),date(2026,7,1))
    def test_merge_rejects_bidask_inversion(self):
        b=[{'time':1,'open':3,'close':3}];a=[{'time':1,'open':2,'close':2}]
        with self.assertRaises(ValueError):m.combine_minutes(b,a)
    def test_no_interpolation_of_missing_minute(self):
        mid=3500
        rows=[{'time':i*60,'bid':{'open':mid,'high':mid+1,'low':mid-1,'close':mid},
               'ask':{'open':mid+.3,'high':mid+1.3,'low':mid-.7,'close':mid+.3}} for i in range(5)]
        self.assertEqual(len(m.aggregate_m5(rows)[0]),1)
        self.assertEqual(len(m.aggregate_m5([r for r in rows if r['time']!=120])[0]),0)
    def test_entry_long_ask_exit_bid_cost_without_extra_spread(self):
        bars=synthetic_quotes()
        signals={k:[0]*len(bars) for k in m.NAMES};signals[m.NAMES[0]][225]=1
        atr=[2]*len(bars)
        result,ledger=m.replay_bidask(bars,slippage=0,atr=atr,signals=signals)
        self.assertTrue(result['closed_trades']>=1)
        t=ledger[0]
        self.assertAlmostEqual(t['entry'],bars[226]['ask']['open'])
        self.assertEqual(t['side'],1)
        self.assertAlmostEqual(t['net_usd'],t['qty_oz']*(t['exit']-t['entry'])) # no phantom commission
    def test_short_entry_bid_side(self):
        bars=synthetic_quotes();signals={k:[0]*len(bars) for k in m.NAMES};signals[m.NAMES[0]][225]=-1
        result,ledger=m.replay_bidask(bars,slippage=0,atr=[2]*len(bars),signals=signals)
        self.assertEqual(result['closed_trades'],1)
        self.assertAlmostEqual(ledger[0]['entry'],bars[226]['bid']['open'])
    def test_higher_slippage_not_fictitious_gain(self):
        bars=synthetic_quotes();signals={k:[0]*len(bars) for k in m.NAMES};signals[m.NAMES[0]][225]=1
        a,_=m.replay_bidask(bars,slippage=.15,atr=[2]*len(bars),signals=signals)
        b,_=m.replay_bidask(bars,slippage=.75,atr=[2]*len(bars),signals=signals)
        self.assertLessEqual(b['net_usd'],a['net_usd'])
    def test_next_candle_not_same_signal_bar(self):
        bars=synthetic_quotes();signals={k:[0]*len(bars) for k in m.NAMES};signals[m.NAMES[0]][225]=1
        _,ledger=m.replay_bidask(bars,slippage=0,atr=[2]*len(bars),signals=signals)
        self.assertEqual(ledger[0]['entry_time'],bars[226]['time'])
    def test_no_signal_no_trades(self):
        bars=synthetic_quotes();signals={k:[0]*len(bars) for k in m.NAMES}
        res,_=m.replay_bidask(bars,slippage=.15,atr=[2]*len(bars),signals=signals)
        self.assertEqual(res['closed_trades'],0)
    def test_no_valid_window_no_fabricated(self):
        with self.assertRaises(ValueError):m.replay_bidask(synthetic_quotes(),start=300,end=290)
    def test_deterministic_bootstrap(self):
        sample=[{'exit_time':int(datetime(2026,7,1+i,tzinfo=timezone.utc).timestamp()),'net_usd':(-1)**i*10} for i in range(25)]
        self.assertEqual(m.bootstrap_daily_pnl(sample),m.bootstrap_daily_pnl(sample))
    def test_small_bootstrap_does_not_claim_significance(self):
        self.assertEqual(m.bootstrap_daily_pnl([])['status'],'too_few_days')
    def test_lot_enforced(self):
        bars=synthetic_quotes();signals={k:[0]*len(bars) for k in m.NAMES};signals[m.NAMES[0]][225]=1
        res,_=m.replay_bidask(bars,slippage=.15,capital=100,atr=[2]*len(bars),signals=signals)
        self.assertEqual(res['closed_trades'],0)
        self.assertGreater(res['blocked'].get('min_lot',0),0)
    def test_parameter_fixed(self):
        self.assertEqual((m.PARAMS['stop_atr'],m.PARAMS['target_r'],m.PARAMS['max_hold']),(3.,3.,36))
        self.assertEqual(m.DISABLED,'MOMENTUM_2BAR')
    def test_zero_cost_not_magic_return(self):
        bars=synthetic_quotes();signals={k:[0]*len(bars) for k in m.NAMES}
        res,_=m.replay_bidask(bars,slippage=0,atr=[2]*len(bars),signals=signals)
        self.assertEqual(res['net_usd'],0)

if __name__=='__main__':unittest.main()