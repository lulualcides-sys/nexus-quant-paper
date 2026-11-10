"""Run matched v1/v2 gold hypotheses on observed GC=F, not broker fills."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from research.indicator_fusion_v2 import matched_review
from research.indicator_fusion_bots import TIMEFRAMES
from research.run_indicator_fusion import download_m1
from research.atlas_mtf_comparison import download_m5, resample_m5


def main():
    output = {'study': 'Matched GOLD indicator fusion V1 vs V2 research',
              'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'paper_only': True, 'live_approved': False,
              'caution': 'Previously examined Yahoo proxy history; no FBS/MT5 bid-ask or fresh holdout',
              'timeframes': {}}
    m5 = None
    for tf in TIMEFRAMES:
        try:
            if tf=='M1':
                bars=download_m1()
            else:
                if m5 is None:
                    m5=download_m5()
                bars=resample_m5(m5,TIMEFRAMES[tf])
            report=matched_review(bars,tf)
            output['timeframes'][tf]=report
            for name,stats in report['bots'].items():
                z=stats['by_cost']
                print('PAIRED',tf,name,
                      'n',z['14.0']['closed_trades'],
                      'gross0',z['0.0']['net_usd'],
                      'net7',z['7.0']['net_usd'],
                      'net14',z['14.0']['net_usd'],
                      'net28',z['28.0']['net_usd'],
                      'folds14',z['14.0']['fold_net_usd'],
                      'folds28',z['28.0']['fold_net_usd'],
                      'pass',stats['research_review_pass'],flush=True)
        except Exception as ex:
            output['timeframes'][tf]={'status':'unavailable',
                'error':f'{type(ex).__name__}: {str(ex)[:200]}',
                'paper_only':True}
            print('DATA_UNAVAILABLE',tf,str(ex)[:250],flush=True)
    path=Path('research/results/indicator_fusion_v2_latest.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('RESULT_FILE',path,flush=True)
    if not any('bots' in x for x in output['timeframes'].values()):
        raise SystemExit('No observed candle data available')

if __name__=='__main__': main()