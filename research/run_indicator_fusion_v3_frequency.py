"""Reproducible high-frequency GOLD research. No live orders or state writes."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json, gzip, hashlib
from research.indicator_fusion_v3_frequency import research
from research.atlas_mtf_comparison import download_m5,resample_m5
from research.run_indicator_fusion import download_m1


def main():
    result={'study':'XAU 200 monthly trades - observed frequency and cost audit',
            'paper_only':True,'live_approved':False,'date_utc':datetime.now(timezone.utc).isoformat(),
            'no_real_broker_fills':True,'timeframes':{}}
    m5=None
    # ~1 month of observed Yahoo GC=F; short 5 day M1 is diagnostic ONLY.
    for name in ('M5','M15','M1'):
        try:
            if name=='M1':data=download_m1()
            else:
                if m5 is None:m5=download_m5()
                data=resample_m5(m5,300 if name=='M5' else 900)
            if name=='M5':
                out=Path('research/results/xau_gc_f_observed_m5_20261110.json.gz')
                out.parent.mkdir(parents=True,exist_ok=True)
                raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode('utf-8')
                with gzip.open(out,'wb') as handle: handle.write(raw)
                digest=hashlib.sha256(raw).hexdigest()
                result['m5_snapshot_sha256']=digest
                result['m5_snapshot_bars']=len(data)
                print('V3_SNAPSHOT',out,'sha256',digest,'bars',len(data),flush=True)
            stats=research(data,timeframe=name)
            result['timeframes'][name]=stats
            for cost in ('0.0','7.0','14.0','28.0'):
                z=stats['by_cost'][cost]
                print('V3',name,'cost',cost,'closed',z['closed_trades'],
                      'signals',z['signals_total'], 'normalized30d',z['trades_per_30_calendar_days_estimate'],
                      'net_usd',z['net_usd'],'fees',z['fees_usd'],'dd',z['max_realized_drawdown_pct'],
                      'wins',z['win_rate_pct'],'per_bot',z['entered_by_type'],flush=True)
            print('V3_FOLDS',name,stats['folds_14_28bps'],flush=True)
        except Exception as e:
            result['timeframes'][name]={'status':'unavailable','reason':f'{type(e).__name__}: {e}'[:350],
                                         'paper_only':True,'live_approved':False}
            print('V3_UNAVAILABLE',name,repr(e)[:300],flush=True)
    out=Path('research/results/indicator_fusion_v3_frequency_latest.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('V3_WRITTEN',out,flush=True)
    if not any('by_cost' in x for x in result['timeframes'].values()):raise SystemExit('No valid feed data')

if __name__=='__main__':main()