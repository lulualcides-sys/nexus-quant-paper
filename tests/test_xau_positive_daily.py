import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from src.xau_positive_daily import MAPPING, build, roster, run, local_day

NOW=int(datetime(2026,11,11,22,35,tzinfo=timezone.utc).timestamp())

class PositiveDigest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        p=self.root/'research/preserved';p.mkdir(parents=True)
        ids=[x for x in MAPPING if not x.startswith('gold_h4:pullback20')]
        self.assertEqual(len(ids),14)
        entries=[{'id':key,'original_rule_id':key} for key in ids]
        (p/'xau_all_positive_original_robots_20261110.json').write_text(json.dumps({'paper_only':True,'archived_positive_scenario_slots':52,'snapshots':[{'entries':entries}]}))
        five=['channel20','channel55','momentum100','pullback20','rsi_trend']
        (p/'xau_v8_all_positive_h4_snapshots_20261110.json').write_text(json.dumps({'paper_only':True,'historical_positive_scenarios':30,'entries':[{'family':f} for f in five]}))
        s=self.root/'state';s.mkdir()
        recent=NOW-3600
        sample={'equity':5012.5,'position':None,'closed':[{'entry_ts':NOW-7200,'exit_ts':NOW-3600,'net_usd':12.5}]}
        for fn,keys in [('selected_gold_v2.json',['channel20','channel55','momentum100','pullback20','rsi_trend']),('leveraged_gold_v1.json',['lev_channel20','lev_channel55','lev_momentum100','lev_momentum40','lev_trend_long'])]:
            (s/fn).write_text(json.dumps({'paper_only':True,'h4_watermark':recent,'books':{k:sample for k in keys}}))
        (s/'experimental_h1_v1.json').write_text(json.dumps({'paper_only':True,'watermarks':{'XAUUSD':recent},'books':{'XAUUSD:'+k:{'equity':1012.5,**{kk:vv for kk,vv in sample.items() if kk!='equity'}} for k in ['ema20_retest','channel10','rsi50']}}))
        (s/'momentum60_shadow_v1.json').write_text(json.dumps({'paper_only':True,'h4_watermark':recent,**sample}))
    def test_roster_complete(self):
        ids,n,v8=roster(self.root)
        self.assertEqual((len(ids),n,v8),(15,14,5))
    def test_daily_message_no_historical_profit_reuse(self):
        msg,meta=build(local_day(NOW),self.root,NOW)
        self.assertEqual(meta['available'],14)
        self.assertEqual(len(meta['unavailable']),1)
        self.assertIn('PENDENTE M1 BB20 adaptado XAU',msg)
        self.assertIn('H4 Channel20:',msg)
        self.assertIn('H1 RSI50:',msg)
        self.assertNotIn('844.56',msg)
        self.assertLess(len(msg),3900)
    def test_dedupe_after_confirmed_send(self):
        calls=[]
        self.assertTrue(run(root=self.root,now=NOW,send=lambda msg:calls.append(msg) or True))
        self.assertFalse(run(root=self.root,now=NOW,send=lambda msg:calls.append(msg) or True))
        self.assertEqual(len(calls),1)
    def test_failure_keeps_marker_unset(self):
        with self.assertRaises(RuntimeError):
            run(root=self.root,now=NOW,send=lambda msg:False)
        self.assertFalse((self.root/'state/xau_positive_daily_sent.json').exists())
    def test_missing_state_is_not_zero_pnl(self):
        (self.root/'state/experimental_h1_v1.json').unlink()
        msg,meta=build(local_day(NOW),self.root,NOW)
        self.assertEqual(meta['available'],11)
        self.assertIn('P/L desconhecido',msg)
    def test_archive_mismatch_fails_closed(self):
        p=self.root/'research/preserved/xau_all_positive_original_robots_20261110.json'
        j=json.loads(p.read_text());j['snapshots'][0]['entries'].pop();p.write_text(json.dumps(j))
        with self.assertRaises(ValueError):build(local_day(NOW),self.root,NOW)
    def test_ledger_realized_not_open_float(self):
        p=self.root/'state/selected_gold_v2.json';j=json.loads(p.read_text());j['books']['channel20']['position']={'start':NOW-300,'entry':4000.,'side':1};p.write_text(json.dumps(j))
        msg,_=build(local_day(NOW),self.root,NOW)
        self.assertIn('H4 Channel20: 2 ent., 1 saídas;',msg)
        self.assertIn('ABERTA',msg)

if __name__=='__main__':unittest.main()