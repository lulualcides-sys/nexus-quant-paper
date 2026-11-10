"""Run isolated indicator fusion research against observed Yahoo GC=F candles.

Usage: python -m research.run_indicator_fusion
Internet access is needed; failures are FAIL-CLOSED, never an invented result.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
import json, time, urllib.request
from research.indicator_fusion_bots import research, TIMEFRAMES
from research.atlas_mtf_comparison import download_m5, resample_m5


def download_m1():
    now=int(time.time())
    errors=[]
    for host in ('query1.finance.yahoo.com','query2.finance.yahoo.com'):
        url='https://'+host+'/v8/finance/chart/'+quote('GC=F',safe='')+'?interval=1m&range=5d'
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=30) as response:
                payload=json.load(response)
            x=(payload.get('chart') or {}).get('result') or []
            if not x: raise ValueError('missing Yahoo result')
            q=x[0]['indicators']['quote'][0]
            bars=[]
            for i,ts in enumerate(x[0]['timestamp']):
                ts=int(ts)
                if ts%60 or ts+60>now-180: continue
                try:
                    row={'time':ts, **{k:float(q[k][i]) for k in ('open','high','low','close')}}
                except (TypeError,ValueError,IndexError,KeyError): continue
                if row['low']<=min(row['open'],row['close']) and row['high']>=max(row['open'],row['close']) and row['low']>0:
                    bars.append(row)
            if len(bars)<450: raise ValueError('insufficient M1')
            if any(bars[i]['time']<=bars[i-1]['time'] for i in range(1,len(bars))): raise ValueError('unsorted M1')
            return bars
        except Exception as e:
            errors.append(host+': '+repr(e)[:120])
    raise RuntimeError('M1 unavailable: '+'; '.join(errors))


def main():
    # Keep distinct feed windows distinct, never compare unaligned samples as if identical.
    results={'market':'GC=F futures proxy (NOT broker XAUUSD fills)','paper_only':True,
             'executed_at_utc':datetime.now(timezone.utc).isoformat(),
             'data_warning':'M1 uses recent 5d. M5/M15/M30 share Yahoo M5 1mo. Not comparable windows.',
             'timeframes':{}}
    for tf in TIMEFRAMES:
        try:
            if tf=='M1':
                rows=download_m1()
            else:
                if 'm5' not in locals(): m5=download_m5()
                rows=resample_m5(m5,TIMEFRAMES[tf])
            report=research(rows,timeframe=tf)
            results['timeframes'][tf]=report
            for name,x in report['strategies'].items():
                print('RESULT',tf,name,x['closed_trades'],x['net_usd'],x['net_double_cost_usd'],x['retrospective_consistency_pass'],flush=True)
        except Exception as exc:
            results['timeframes'][tf]={'status':'UNAVAILABLE','error':type(exc).__name__+': '+str(exc)[:350],
                                      'paper_only':True,'approved_for_live':False}
            print('UNAVAILABLE',tf,results['timeframes'][tf]['error'],flush=True)
    dst=Path('research/results/indicator_fusion_latest.json')
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('WROTE',dst,flush=True)
    if not any(x.get('strategies') for x in results['timeframes'].values()):
        raise SystemExit('All source feeds unavailable, no backtests claimed')

if __name__=='__main__': main()