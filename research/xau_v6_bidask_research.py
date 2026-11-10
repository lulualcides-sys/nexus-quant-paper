"""Nexus Quant V6: fixed V4 XAU M5 strategies on Dukascopy BID/ASK, older months.

EXPERIMENT ONLY: no broker credentials, trading API, orders, state mutations,
parameter optimization, synthetic price imputation, or positive-PnL targeting.
This is historical temporal transfer, not a prospective forward test or FBS fills.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta, timezone
from hashlib import sha256
from math import floor, isfinite, sqrt
from pathlib import Path
from statistics import mean, median
import argparse
import json
import lzma
import random
import struct
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from research.indicator_fusion_v3_frequency import features_and_signals, NAMES, WARMUP

HOST = 'https://datafeed.dukascopy.com/datafeed/XAUUSD'
RECORD = struct.Struct('>IIIIIf')
SCALE = 1000  # XAUUSD 3 decimal places (verify plausible observed magnitudes)
PERIOD = 300
START = date(2026, 6, 25)  # warm-up only: no June trades are evaluated
EVALUATION_START = date(2026, 7, 1)
END_EXCLUSIVE = date(2026, 10, 1)
CAPITAL = 5000.0
PARAMS = dict(stop_atr=3.0, target_r=3.0, max_hold=36, risk_frac=.0075, min_lot_oz=1.)
DISABLED = 'MOMENTUM_2BAR'  # frozen prior to this independent older-source evaluation
POLICY = 'fixed_v4'         # frozen prior to data acquisition (no new filter)
SCENARIOS = (0., .15, .75, 1.5)  # USD/oz slippage PER SIDE; actual bid/ask spread already in fills


def _day_url(day: date, side: str) -> str:
    if side not in ('BID', 'ASK'): raise ValueError('side')
    return f'{HOST}/{day.year}/{day.month-1:02d}/{day.day:02d}/{side}_candles_min_1.bi5'


def _get_file(url: str, *, retries=3) -> bytes | None:
    for attempt in range(retries):
        try:
            req = Request(url, headers={'User-Agent':'Mozilla/5.0 (historical research; no live execution)'})
            with urlopen(req, timeout=25) as response:
                data=response.read(5_000_000)
            if not data: raise ValueError('empty downloaded bytes')
            return data
        except HTTPError as exc:
            if exc.code == 404: return None
            if exc.code not in (429,500,502,503,504): raise
        except (TimeoutError, URLError):
            pass
        if attempt+1 < retries: time.sleep(.5 * (attempt+1))
    raise RuntimeError('Download failed after bounded retries for ' + url)


def decode_bi5_minute(raw: bytes, day: date) -> list[dict]:
    """Open, close, low, high per 24-byte Dukascopy minute candle, UTC offset seconds."""
    binary=lzma.decompress(raw)
    if not binary or len(binary)%RECORD.size:
        raise ValueError('Invalid Dukascopy 24-byte record file')
    day_ts=int(datetime(day.year,day.month,day.day,tzinfo=timezone.utc).timestamp())
    out=[]; seen=set()
    for offs,open_raw,close_raw,low_raw,high_raw,vol in RECORD.iter_unpack(binary):
        if offs >= 86400 or offs % 60 or offs in seen:
            raise ValueError('Duplicate/out-of-range/non-minute Dukascopy offset')
        seen.add(offs)
        op,cl,lo,hi=(p/SCALE for p in (open_raw,close_raw,low_raw,high_raw))
        if not all(isfinite(v) and 200 <= v <= 20000 for v in (op,cl,lo,hi)):
            raise ValueError('Unexpected gold quote scale/value')
        if not lo <= min(op,cl) <= max(op,cl) <= hi or not isfinite(vol):
            raise ValueError('Invalid observed candle price/volume')
        out.append({'time':day_ts+offs,'open':op,'high':hi,'low':lo,'close':cl})
    out.sort(key=lambda row:row['time'])
    return out


def combine_minutes(bids: list[dict], asks: list[dict]) -> tuple[list[dict],dict]:
    bmap={x['time']:x for x in bids}; amap={x['time']:x for x in asks}
    if len(bmap)!=len(bids) or len(amap)!=len(asks):
        raise ValueError('Duplicate timestamp in BID or ASK candles')
    common=sorted(set(bmap)&set(amap))
    if not common: return [], {'common_minutes':0,'orphan_minutes':len(bmap)+len(amap)}
    observed=[]
    for t in common:
        b,a=bmap[t],amap[t]
        if a['open']+1e-8 < b['open'] or a['close']+1e-8 < b['close']:
            raise ValueError('Inverted observed bid/ask opening or closing quote')
        row={'time':t,'bid':b,'ask':a}
        observed.append(row)
    return observed,{'common_minutes':len(common),'orphan_minutes':len(bmap)+len(amap)-2*len(common)}


def aggregate_m5(minute_rows: list[dict]) -> tuple[list[dict],dict]:
    """Only complete synchronized five-minute blocks; never forward/backfill quotes."""
    buckets=defaultdict(list)
    for row in minute_rows:
        t=row['time']
        buckets[t-t%PERIOD].append(row)
    out=[]; excluded=0
    for key in sorted(buckets):
        rows=sorted(buckets[key],key=lambda r:r['time'])
        if len(rows)!=5 or any(r['time']!=key+60*i for i,r in enumerate(rows)):
            excluded+=1
            continue
        def agg(side):
            arr=[r[side] for r in rows]
            return {'open':arr[0]['open'],'high':max(r['high'] for r in arr),
                    'low':min(r['low'] for r in arr),'close':arr[-1]['close']}
        bid,ask=agg('bid'),agg('ask')
        mid={field:(bid[field]+ask[field])/2 for field in ('open','high','low','close')}
        if mid['low']>min(mid['open'],mid['close']) or mid['high']<max(mid['open'],mid['close']):
            raise ValueError('Aggregated mid candle inconsistent')
        out.append({'time':key,**mid,'bid':bid,'ask':ask,
                    'open_spread':ask['open']-bid['open'],
                    'close_spread':ask['close']-bid['close']})
    return out,{'excluded_incomplete_m5_buckets':excluded,'m5_complete':len(out)}


def download_history(start: date=START, end_exclusive: date=END_EXCLUSIVE, workers=6):
    if start >= end_exclusive or workers<1 or workers>8: raise ValueError('invalid fetch settings')
    days=[]; d=start
    while d < end_exclusive:
        if d.weekday()<5: days.append(d)
        d+=timedelta(days=1)
    tasks={}; collected={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for day in days:
            for side in ('BID','ASK'):
                tasks[pool.submit(_get_file, _day_url(day,side))]=(day,side)
        for future in as_completed(tasks):
            day,side=tasks[future]
            try: collected[(day,side)]=future.result()
            except Exception as exc:
                # Fail closed if any requested weekday had a network error.
                raise RuntimeError(f'Dukascopy download failed {day} {side}: {exc}') from exc
    price_rows=[]; source=[]; missing=[]; excluded=Counter(); spread_m=[]; total_minutes=0
    for day in days:
        bid_bytes=collected[(day,'BID')];ask_bytes=collected[(day,'ASK')]
        if bid_bytes is None and ask_bytes is None:
            missing.append(day.isoformat());continue
        if bid_bytes is None or ask_bytes is None:
            raise ValueError('A weekday has only one bid/ask quote side: '+day.isoformat())
        b=decode_bi5_minute(bid_bytes,day)
        a=decode_bi5_minute(ask_bytes,day)
        merged,meta=combine_minutes(b,a)
        if meta['common_minutes']<200:
            raise ValueError('Under 200 synchronized minutes on weekday: '+day.isoformat())
        total_minutes+=meta['common_minutes']
        if meta['orphan_minutes']>20:
            raise ValueError('Excess bid/ask missing-minute mismatch '+day.isoformat())
        agg,q=aggregate_m5(merged)
        price_rows.extend(agg)
        spread_m.extend(r['open_spread'] for r in agg)
        excluded['incomplete_m5']+=q['excluded_incomplete_m5_buckets']
        source.append({'date':day.isoformat(),'sha256_bid':sha256(bid_bytes).hexdigest(),
                       'sha256_ask':sha256(ask_bytes).hexdigest(),'complete_m5':len(agg)})
    if len(missing)>max(3, len(days)//10):
        raise ValueError(f'Too many unavailable weekdays: {len(missing)}')
    if len(price_rows)<5000 or len(source)<25:
        raise ValueError('Insufficient real full-session BID/ASK data')
    if any(price_rows[i]['time']<=price_rows[i-1]['time'] for i in range(1,len(price_rows))):
        raise ValueError('Nonmonotonic aggregated quotes')
    metadata={'provider':'Dukascopy raw XAUUSD BID and ASK 1-minute candles via datafeed',
              'instrument':'XAUUSD spot (NOT executed FBS quotes)', 'start':start.isoformat(),
              'end_exclusive':end_exclusive.isoformat(), 'days_with_data':len(source),
              'missing_weekdays':missing,'minute_pairs':total_minutes,'complete_m5':len(price_rows),
              'excluded_partial_m5_buckets':excluded['incomplete_m5'],
              'median_observed_m5_open_spread_usd_per_oz':round(median(spread_m),5),
              'source_hashes':source,
              'no_filled_bars':True,'source_only_completed_m5':True}
    return price_rows,metadata


def _exit_price(position, bar, slippage, *, reason):
    side=position['side']; opposite=bar['bid'] if side==1 else bar['ask']
    exit_q = opposite['close'] if reason=='time' else (opposite['open'] if reason=='gap_stop' else position['target'] if reason.startswith('target') else position['stop'])
    return exit_q-side*slippage


def replay_bidask(bars, *, slippage=.15, start=None,end=None,capital=CAPITAL, atr=None, signals=None):
    """Ask for long entry, bid for long exit; inverted for short. One position.

    A 5min BID/ASK OHLC is not tick sequencing. If both stop and target touched
    within 5m, stop wins. Entry signal is previous COMPLETED mid candle only.
    """
    if slippage<0 or capital<=0:raise ValueError('invalid execution settings')
    if atr is None or signals is None:
        atr,signals=features_and_signals(bars)
        signals={k:([0]*len(bars) if k==DISABLED else v) for k,v in signals.items()}
    if len(atr)!=len(bars) or set(signals)!=set(NAMES):raise ValueError('invalid signal array')
    first=max(WARMUP+1,start if start is not None else WARMUP+1)
    last=min(len(bars),end if end is not None else len(bars))
    if first>=last:raise ValueError('empty replay window')
    equity=capital; peak=capital; dd=0.;pos=None;ledger=[];blocked=Counter();open_counts=Counter();snapped=[]
    for i in range(first,last):
        b=bars[i];occupied=pos is not None
        if occupied:
            p=pos;s=p['side'];q=b['bid'] if s==1 else b['ask']
            gap_stop=(s==1 and q['open']<=p['stop']) or (s==-1 and q['open']>=p['stop'])
            gap_target=(s==1 and q['open']>=p['target']) or (s==-1 and q['open']<=p['target'])
            stop_touch=q['low']<=p['stop'] if s==1 else q['high']>=p['stop']
            target_touch=q['high']>=p['target'] if s==1 else q['low']<=p['target']
            if gap_stop:
                level=q['open']; reason='gap_stop'
            elif gap_target:
                level=p['target']; reason='target_gap'
            elif stop_touch:
                level=p['stop']; reason='stop'
            elif target_touch:
                level=p['target'];reason='target'
            elif i-p['entry_i'] >= PARAMS['max_hold']:
                level=q['close'];reason='time'
            else:level=None
            if level is not None:
                exit_price=level-s*slippage
                gross=s*(exit_price-p['entry'])*p['qty']
                item={'bot':p['bot'],'entry_time':p['time'],'exit_time':b['time'],'side':s,
                      'entry':p['entry'],'exit':exit_price,'qty_oz':p['qty'],
                      'net_usd':gross,'exit_reason':reason,'stop_and_target_touch':stop_touch and target_touch}
                ledger.append(item); equity+=gross;peak=max(equity,peak)
                dd=max(dd,100*(peak-equity)/peak)
                pos=None
        if occupied:continue
        if i==0 or b['time']-bars[i-1]['time']!=PERIOD:
            blocked['missing_next_open']+=1;continue
        choices=[(name,signals[name][i-1]) for name in NAMES if signals[name][i-1]]
        if not choices or equity<=0:continue
        name,s=choices[0]
        dist=PARAMS['stop_atr']*atr[i-1]
        if not isfinite(dist) or dist<=0:continue
        open_q=b['ask']['open'] if s==1 else b['bid']['open']
        entry=open_q+s*slippage
        qty=min(equity*PARAMS['risk_frac']/dist, equity/entry)
        qty=floor(qty/PARAMS['min_lot_oz']+1e-9)*PARAMS['min_lot_oz']
        if qty<=0:
            blocked['min_lot']+=1;continue
        p={'bot':name,'side':s,'entry':entry,'qty':qty,'time':b['time'],'entry_i':i,
           'stop':entry-s*dist,'target':entry+s*PARAMS['target_r']*dist}
        pos=p;open_counts[name]+=1
        q=b['bid'] if s==1 else b['ask']
        if q['low']<=p['stop'] if s==1 else q['high']>=p['stop']:
            level=p['stop'];reason='stop_same_bar'
        elif q['high']>=p['target'] if s==1 else q['low']<=p['target']:
            level=p['target'];reason='target_same_bar'
        else:level=None
        if level is not None:
            exit_price=level-s*slippage;gross=s*(exit_price-entry)*qty
            ledger.append({'bot':name,'entry_time':b['time'],'exit_time':b['time'],
                           'side':s,'entry':entry,'exit':exit_price,'qty_oz':qty,
                           'net_usd':gross,'exit_reason':reason,'stop_and_target_touch':False})
            equity+=gross;peak=max(peak,equity);dd=max(dd,100*(peak-equity)/peak)
            pos=None
    floating=0.
    if pos is not None:
        b=bars[last-1];p=pos;s=p['side'];
        price=(b['bid'] if s==1 else b['ask'])['close'] - s*slippage
        floating=s*(price-p['entry'])*p['qty']
    gains=sum(max(0,t['net_usd']) for t in ledger)
    losses=-sum(min(0,t['net_usd']) for t in ledger)
    summary={'closed_trades':len(ledger),'net_usd':round(equity-capital+floating,2),
             'closed_net_usd':round(equity-capital,2),'floating_usd':round(floating,2),
             'initial_capital_usd':capital,'pct_return':round(100*(equity-capital+floating)/capital,3),
             'profit_factor':round(gains/losses,3) if losses>0 else None,
             'win_rate':round(100*sum(t['net_usd']>0 for t in ledger)/len(ledger),2) if ledger else None,
             'max_closed_equity_drawdown_pct':round(dd,3),'open_at_end':pos is not None,
             'by_signal':dict(open_counts),'blocked':dict(blocked),
             'slippage_each_side_usd_per_oz':slippage,'spread_already_in_bidask_quotes':True}
    return summary,ledger


def bootstrap_daily_pnl(trades, *, repeats=3000, seed=20261110):
    """Resample calendar-day daily P&Ls. Diagnostic, NOT independent proof."""
    daily=defaultdict(float)
    for t in trades:
        day=datetime.fromtimestamp(t['exit_time'],timezone.utc).date().isoformat()
        daily[day]+=t['net_usd']
    if len(daily)<20:return {'status':'too_few_days','n_days_with_closes':len(daily)}
    vals=list(daily.values());rng=random.Random(seed)
    samples=[]
    for _ in range(repeats):
        samples.append(sum(rng.choices(vals,k=len(vals))))
    samples.sort()
    return {'status':'diagnostic_only','days_with_closes':len(vals),
            'gross_bootstrap_assumption':'days sampled IID; serial dependence ignored; open P&L excluded',
            'two_sided_95pct_ci_for_net_closed_usd':[round(samples[int(repeats*.025)],2),round(samples[int(repeats*.975)],2)],
            'resamples':repeats,'seed':seed}


def run_study(bars,meta):
    atr,signals=features_and_signals(bars)
    signals={k:([0]*len(bars) if k==DISABLED else v) for k,v in signals.items()}
    results={'study':'XAU V6 bid/ask spot out-of-period transfer, no new filters',
             'paper_only':True,'live_approved':False,
             'no_actual_broker_fills':True,'historical_temporal_transfer_not_prospective':True,
             'date_range':[START.isoformat(),END_EXCLUSIVE.isoformat()],
             'same_precommitted_v4_parameters':PARAMS,'source':meta,
             'outcomes':{},'monthly_folds':{},
             'trade_count_is_statistical_power_not_entry_quota':True}
    eval_ts=int(datetime(2026,7,1,tzinfo=timezone.utc).timestamp())
    eval_i=next((i for i,b in enumerate(bars) if b['time']>=eval_ts),len(bars))
    if eval_i < WARMUP+1 or eval_i >= len(bars):
        raise ValueError('Insufficient preceding warmup or no evaluation bars')
    for slip in SCENARIOS:
        overall,ledger=replay_bidask(bars,start=eval_i,slippage=slip,atr=atr,signals=signals)
        overall['daily_bootstrap_ci']=bootstrap_daily_pnl(ledger)
        label=f'slippage_{slip:.2f}_each_side'
        results['outcomes'][label]=overall
        fold={}
        # Monthly equity resets for comparability, but warmup features carry over.
        for month in (7,8,9):
            fromdate=int(datetime(2026,month,1,tzinfo=timezone.utc).timestamp())
            nextmonth=10 if month==9 else month+1
            enddate=int(datetime(2026,nextmonth,1,tzinfo=timezone.utc).timestamp())
            startidx=next((i for i,b in enumerate(bars) if b['time']>=fromdate),len(bars))
            endidx=next((i for i,b in enumerate(bars) if b['time']>=enddate),len(bars))
            if startidx<WARMUP+1:startidx=WARMUP+1
            if endidx<=startidx:
                fold[str(month)]={'status':'no_candles'};continue
            x,lt=replay_bidask(bars,slippage=slip,start=startidx,end=endidx,atr=atr,signals=signals)
            fold[f'2026-{month:02d}']={k:v for k,v in x.items() if k not in ('by_signal','blocked')}
        results['monthly_folds'][label]=fold
    normal=results['outcomes']['slippage_0.15_each_side'];stress=results['outcomes']['slippage_0.75_each_side'];
    f1=results['monthly_folds']['slippage_0.15_each_side'];f2=results['monthly_folds']['slippage_0.75_each_side']
    full=all(f1.get(f'2026-{x:02d}',{}).get('closed_trades',0)>0 for x in (7,8,9))
    n=normal['closed_trades']
    results['research_screen_pass']=(n>=150 and full and
       all(f1[f'2026-{x:02d}']['net_usd']>0 and f2[f'2026-{x:02d}']['net_usd']>0 for x in (7,8,9)) and
       stress['max_closed_equity_drawdown_pct']<=12 and
       normal['daily_bootstrap_ci'].get('two_sided_95pct_ci_for_net_closed_usd',[-1])[0]>0)
    results['live_approved']=False
    return results


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='research/results/xau_v6_bidask_2026_jul_sep.json')
    p.add_argument('--workers',type=int,default=6)
    args=p.parse_args()
    bars,meta=download_history(workers=args.workers)
    report=run_study(bars,meta)
    dst=Path(args.output);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('DATA',json.dumps({k:v for k,v in meta.items() if k!='source_hashes'},sort_keys=True),flush=True)
    for key,r in report['outcomes'].items():
        print('V6_RESULT',key,'trades',r['closed_trades'],'net_usd',r['net_usd'],
              'return_pct',r['pct_return'],'PF',r['profit_factor'],'DD',r['max_closed_equity_drawdown_pct'],
              'CI',r['daily_bootstrap_ci'].get('two_sided_95pct_ci_for_net_closed_usd'),flush=True)
        print('V6_MONTHLY',key,json.dumps(report['monthly_folds'][key],sort_keys=True),flush=True)
    print('V6_SCREEN',report['research_screen_pass'],'LIVE',report['live_approved'],'OUTPUT',str(dst),flush=True)

if __name__=='__main__':main()