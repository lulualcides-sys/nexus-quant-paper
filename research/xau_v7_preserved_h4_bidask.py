"""Frozen historic transfer of the five original H4 gold signal families onto
Dukascopy M1 BID/ASK. Research only, no brokerage/state/orders.

Critically compares historical paper fractional ounces with broker-style one
ounce lot step. No optimization, no threshold chosen by observed P&L.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
from math import floor, isfinite
from pathlib import Path
from statistics import median
from urllib.request import Request, urlopen
import json
import time

from research.xau_v6_bidask_research import combine_minutes, aggregate_m5
from research.screen_v2 import sign
from src.strategies import make_indicators

SOURCE_REPO='kevingtlin/Market-Data-Lab'
SOURCE_COMMIT='b60bd71d0e34a42cb962daf688ff252e73f409ca'
MONTHS=(4,5,6,7,8,9)  # prewarm April-June; evaluate July-September
RULES=('channel20','channel55','momentum100','rsi_trend','pullback20')
CAPITAL=5000.
RISK=.0075
STOP_ATR=2.
TARGET_ATR=3.5
MAX_HOLD=90
H4=14400
M5=300
EVAL_START=int(datetime(2026,7,1,tzinfo=timezone.utc).timestamp())
EVAL_END=int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp())
MONTH_BOUNDS=[int(datetime(2026,m,1,tzinfo=timezone.utc).timestamp()) for m in (7,8,9,10)]
SCENARIOS={
    'fractional_slip_0p15':{'lot_step':0.,'slippage':.15},
    'one_ounce_slip_0':{'lot_step':1.,'slippage':0.},
    'one_ounce_slip_0p15':{'lot_step':1.,'slippage':.15},
    'one_ounce_slip_0p75':{'lot_step':1.,'slippage':.75},
}


def read_monthly_side(raw:bytes,year:int,month:int)->list[dict]:
    try:
        lines=StringIO(raw.decode('utf-8-sig'))
        reader=csv.DictReader(lines)
        if not {'timestamp','open','high','low','close'}.issubset(reader.fieldnames or []):
            raise ValueError('Missing required monthly candle columns')
        out=[];prev=-1
        for row in reader:
            tms=int(row['timestamp'])
            if tms%60000:raise ValueError('M1 timestamp misaligned')
            ts=tms//1000
            dt=datetime.fromtimestamp(ts,timezone.utc)
            if (dt.year,dt.month)!=(year,month):raise ValueError('Source month mismatch')
            if ts<=prev:raise ValueError('Duplicate/out-of-order source timestamp')
            prev=ts
            item={'time':ts,**{k:float(row[k]) for k in ('open','high','low','close')}}
            q=[item[k] for k in ('open','high','low','close')]
            if any(not isfinite(v) or v<=100 or v>20000 for v in q):raise ValueError('Invalid spot price')
            if item['low']>min(item['open'],item['close']) or item['high']<max(item['open'],item['close']):
                raise ValueError('OHLC source invalid')
            out.append(item)
        if len(out)<200:raise ValueError('Insufficient monthly source')
        return out
    except (KeyError,TypeError) as err:
        raise ValueError('Source row invalid') from err


def get_raw(url,*,retries=3):
    for j in range(retries):
        try:
            with urlopen(Request(url,headers={'User-Agent':'Nexus-quant-research/1.0'}),timeout=35) as stream:
                raw=stream.read(5_000_000)
            if not raw:raise ValueError('empty price response')
            return raw
        except Exception:
            if j==retries-1:raise
            time.sleep(j+.3)


def load_spot_h4(*,downloader=get_raw):
    h4rows=[]; meta=[];bad_m5=0;bad_h4=0;spreads=[];missing_side=0
    month_m5=[]
    for month in MONTHS:
        sides={}
        for side in ('bid','ask'):
            filename=f'xauusd_{side}_m1_2026_{month:02d}.csv'
            url=f'https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/xauusd/{side}/m1/{filename}'
            raw=downloader(url)
            sides[side]=read_monthly_side(raw,2026,month)
            meta.append({'name':filename,'bytes':len(raw),'sha256':sha256(raw).hexdigest(),
                         'm1_candles':len(sides[side])})
        joined,counts=combine_minutes(sides['bid'],sides['ask'])
        if counts['orphan_minutes']>60:raise ValueError('Asymmetric missing BID/ASK M1 source')
        missing_side+=counts['orphan_minutes']
        m5,stats=aggregate_m5(joined)
        bad_m5+=stats['excluded_incomplete_m5_buckets']
        if len(m5)<500:raise ValueError('Insufficient complete M5 for month')
        month_m5.extend(m5)
        spreads.extend(b['ask']['open']-b['bid']['open'] for b in m5)
    buckets=defaultdict(list)
    for b in month_m5:
        buckets[b['time']//H4*H4].append(b)
    for timestamp in sorted(buckets):
        rows=sorted(buckets[timestamp],key=lambda x:x['time'])
        if len(rows)!=48 or any(r['time']!=timestamp+M5*i for i,r in enumerate(rows)):
            bad_h4+=1
            continue
        def aggregate_side(side):
            return {'open':rows[0][side]['open'],'close':rows[-1][side]['close'],
                    'high':max(r[side]['high'] for r in rows),'low':min(r[side]['low'] for r in rows)}
        bid=aggregate_side('bid');ask=aggregate_side('ask')
        mid={k:(bid[k]+ask[k])/2 for k in ('open','high','low','close')}
        h4rows.append({'time':timestamp,**mid,'bid':bid,'ask':ask})
    if len(h4rows)<350 or not any(EVAL_START<=b['time']<EVAL_END for b in h4rows):
        raise ValueError('Insufficient complete H4 candles')
    if any(h4rows[i]['time']<=h4rows[i-1]['time'] for i in range(1,len(h4rows))):
        raise ValueError('Nonmonotonic H4 feed')
    metaout={'repo':SOURCE_REPO,'commit':SOURCE_COMMIT,'months':list(MONTHS),
            'source_files':meta,'source_minutes_orphaned':missing_side,
            'partial_m5_excluded':bad_m5,'incomplete_h4_excluded':bad_h4,
            'h4_complete':len(h4rows),'median_spread_open_usd_oz':round(median(spreads),5),
            'first_h4':h4rows[0]['time'],'last_h4':h4rows[-1]['time'],
            'no_backfilled_prices':True,'source':'Dukascopy M1 BID/ASK via public pinned mirror, NOT FBS fills'}
    return h4rows,metaout


def _close(pos,bar,i,level,why,slippage):
    s=pos['side'];fill=level-s*slippage
    net=s*(fill-pos['entry'])*pos['qty']
    return {'entry_i':pos['i'],'exit_i':i,'entry_ts':pos['time'],'exit_ts':bar['time'],
            'side':s,'bot':pos['bot'],'qty_oz':pos['qty'],'entry':pos['entry'],
            'exit':fill,'net':net,'reason':why}


def backtest(bars,features,strategy,*,begin=EVAL_START,finish=EVAL_END,
             slippage=.15,lot_step=1.,capital=CAPITAL,force_close=True,
             signal_fn=sign):
    """Same H4 entry conditions as original gold_forward/screen_v2, but
    fills use actual ASK/BID OHLC, next-bar and no lookahead. Exact historical
    news blackout is not reproducible (no archived historical news calendar).
    """
    if strategy not in RULES:raise ValueError('non-preserved signal family')
    if capital<=0 or slippage<0 or lot_step<0 or begin>=finish:raise ValueError('invalid replay')
    if len(bars)!=len(features):raise ValueError('features length mismatch')
    equity=capital;peak=capital;dd=0.;pos=None;ledger=[];blocked=Counter();entry_cnt=0
    indices=[i for i,b in enumerate(bars) if begin<=b['time']<finish]
    if not indices:raise ValueError('empty range')
    for i in indices:
        b=bars[i];was_occupied=pos is not None
        if was_occupied:
            p=pos;s=p['side'];q=b['bid'] if s==1 else b['ask']
            if (s==1 and q['open']<=p['stop']) or (s==-1 and q['open']>=p['stop']):
                level=q['open'];why='stop_gap'
            elif (s==1 and q['open']>=p['target']) or (s==-1 and q['open']<=p['target']):
                level=p['target'];why='target_gap'
            elif (s==1 and q['low']<=p['stop']) or (s==-1 and q['high']>=p['stop']):
                level=p['stop'];why='stop'
            elif (s==1 and q['high']>=p['target']) or (s==-1 and q['low']<=p['target']):
                level=p['target'];why='target'
            elif i-p['i']>=MAX_HOLD:
                level=q['close'];why='max_hold'
            else:level=None
            if level is not None:
                t=_close(pos,b,i,level,why,slippage);ledger.append(t);equity+=t['net'];pos=None
                peak=max(peak,equity);dd=max(dd,100*(peak-equity)/peak)
        # A position occupied at the candle OPEN cannot reopen after an intrabar exit.
        if not was_occupied and i>=242 and equity>0:
            if b['time']-bars[i-1]['time']!=H4:
                blocked['gap_at_entry']+=1
            else:
                s=signal_fn(strategy,bars,features,i-1)
                old=signal_fn(strategy,bars,features,i-2)
                if s and s!=old:
                    atr=features[i-1]['atr']
                    if isfinite(atr) and atr>0:
                        quote=b['ask'] if s==1 else b['bid']
                        entry=quote['open']+s*slippage
                        dist=STOP_ATR*atr
                        qty=min(equity*RISK/dist,equity/entry)
                        if lot_step>0:qty=floor(qty/lot_step+1e-9)*lot_step
                        if qty<=0:blocked['minimum_lot_or_risk']+=1
                        else:
                            pos={'side':s,'bot':strategy,'entry':entry,'i':i,'time':b['time'],
                                 'stop':entry-s*dist,'target':entry+s*TARGET_ATR*atr,'qty':qty}
                            entry_cnt+=1
                            opposing=b['bid'] if s==1 else b['ask']
                            if (s==1 and opposing['low']<=pos['stop']) or (s==-1 and opposing['high']>=pos['stop']):
                                level=pos['stop'];why='stop_same_bar'
                            elif (s==1 and opposing['high']>=pos['target']) or (s==-1 and opposing['low']<=pos['target']):
                                level=pos['target'];why='target_same_bar'
                            else:level=None
                            if level is not None:
                                t=_close(pos,b,i,level,why,slippage);ledger.append(t);equity+=t['net'];pos=None
                                peak=max(peak,equity);dd=max(dd,100*(peak-equity)/peak)
        # Conservative intrabar adverse equity mark (H4 bars only; drawdown may
        # still miss intraminute broker liquidations/overnight financing).
        mark=0.
        if pos is not None:
            side=pos['side'];q=b['bid'] if side==1 else b['ask']
            level=q['low'] if side==1 else q['high']
            mark=side*(level-side*slippage-pos['entry'])*pos['qty']
        conservative_eq=equity+mark
        if conservative_eq>peak:peak=conservative_eq
        if peak>0:dd=max(dd,100*(peak-conservative_eq)/peak)
    if pos is not None:
        last_i=indices[-1];last=bars[last_i];q=last['bid'] if pos['side']==1 else last['ask']
        if force_close:
            tr=_close(pos,last,last_i,q['close'],'window_end',slippage)
            ledger.append(tr);equity+=tr['net'];pos=None
        else:
            equity+=pos['side']*(q['close']-pos['side']*slippage-pos['entry'])*pos['qty']
    pnl=equity-capital
    gain=sum(max(0,t['net']) for t in ledger); loss=-sum(min(0,t['net']) for t in ledger)
    return {'strategy':strategy,'closed_trades':len(ledger),'entries':entry_cnt,
            'net_usd':round(pnl,2),'return_pct':round(100*pnl/capital,3),
            'profit_factor':round(gain/loss,3) if loss else None,
            'wins':sum(t['net']>0 for t in ledger),'winrate_pct':round(100*sum(t['net']>0 for t in ledger)/len(ledger),2) if ledger else None,
            'max_intrabar_proxy_dd_pct':round(dd,3),'blocked':dict(blocked),
            'lot_step_oz':lot_step,'slippage_side':slippage,'exit_month_inclusive':False,
            'ledger':ledger}


def study(bars):
    features=make_indicators(bars)
    if len(bars)<245 or sum(EVAL_START<=b['time']<EVAL_END for b in bars)<250:
        raise ValueError('Insufficient H4 evaluation with warmup')
    out={'study':'Original H4 channel20/channel55/momentum100/rsi_trend/pullback20, frozen rule transfer',
         'data':'XAUUSD spot BID/ASK M1->M5->H4 (quotes; not real FBS fills)',
         'paper_only':True,'approved_for_live':False,'pre_inspected_period':True,
         'development_tuning_on_eval':False,'costs_excluded':['swap','overnight financing','FBS-specific commissions','requotes'],
         'model_settings':{'original_signal_rules':True,'original_stop_atr':STOP_ATR,'target_atr':TARGET_ATR,
                           'risk_frac':RISK,'max_h4_hold':MAX_HOLD,'max_notional_1x':True},
         'strategies':{},'candidate_for_forward':[]}
    for name in RULES:
        configurations={}
        for key,params in SCENARIOS.items():
            full=backtest(bars,features,name,**params)
            month={}
            for a,b in zip(MONTH_BOUNDS,MONTH_BOUNDS[1:]):
                month[datetime.fromtimestamp(a,timezone.utc).strftime('%Y-%m')]=backtest(bars,features,name,begin=a,finish=b,**params)
            configurations[key]={'overall':{k:v for k,v in full.items() if k!='ledger'},
                                 'months':{m:{k:v for k,v in d.items() if k!='ledger'} for m,d in month.items()},
                                 'ledger':full['ledger']}
        d=configurations['one_ounce_slip_0p15']; stress=configurations['one_ounce_slip_0p75']
        # Not a live approval, even if these pass: historical period already analyzed.
        eligible=(d['overall']['closed_trades']>=30 and d['overall']['net_usd']>0 and
                  stress['overall']['net_usd']>0 and
                  all(d['months'][m]['net_usd']>0 and stress['months'][m]['net_usd']>0 for m in d['months']) and
                  d['overall']['max_intrabar_proxy_dd_pct']<=12)
        out['strategies'][name]={'configs':configurations,'research_screen_pass':eligible,
                                 'live_approved':False}
        if eligible:out['candidate_for_forward'].append(name)
    return out


def format_report(payload):
    lines=['# XAUUSD V7 — robôs H4 preservados em BID/ASK spot', '',
          'Reprodução de regras de sinais; os fills não reproduzem o guard de notícias nem ordens FBS. Retrospectivo, não forward.', '',
          '| Robô | Trades $5k (1oz min) | $0.15 /lado | $0.75 /lado | Meses positivos 0.15 | Lote fracionário 0.15 | Screen |',
          '|---|---:|---:|---:|---:|---:|---|']
    for name,study in payload['strategies'].items():
        c=study['configs']; normal=c['one_ounce_slip_0p15']; stress=c['one_ounce_slip_0p75']; frac=c['fractional_slip_0p15']
        m=sum(x['net_usd']>0 for x in normal['months'].values())
        lines.append(f"| {name} | {normal['overall']['closed_trades']} | {normal['overall']['net_usd']:+.2f} | {stress['overall']['net_usd']:+.2f} | {m}/3 | {frac['overall']['net_usd']:+.2f} | {study['research_screen_pass']} |")
    lines +=['','- Capital: US$5,000 por modelo, independente, nunca somados numa carteira; risco-stop máximo planejado 0,75%, 1x notional.',
             '- Min 1 oz impede operações quando distância de stop e banca não satisfazem o risco. Fracionário é **controle teórico não executável** em lote abaixo de 0.01 de 100oz.',
             '- Janeiro não estudado. Meses avaliados: 2026-07, 2026-08, 2026-09 com April-Jun warmup. Corretora não auditada; spread já cobrado no BID/ASK.',
             '- Quatro cenários pré-declarados, sem seleção de hiperparâmetros por resultado; históricos previamente examinados.',
             '- Sem classificação live; pesquisa apenas. Meses independentes resetam banca; somar resultados desses meses não é equivalente à carteira contínua.',
             '- Nenhuma estratégia alcança a conclusão de lucro consistente sem stress + meses + número suficiente de operações e forward.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='research/results/xau_v7_preserved_h4.json')
    p.add_argument('--md',default='research/results/xau_v7_preserved_h4.md')
    args=p.parse_args()
    rows,meta=load_spot_h4();report=study(rows);report['source_metadata']=meta
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    Path(args.md).write_text(format_report(report)+'\n',encoding='utf8')
    print('V7_DATA',json.dumps({k:v for k,v in meta.items() if k!='source_files'},sort_keys=True),flush=True)
    for name,item in report['strategies'].items():
        c=item['configs']
        print('V7_RESULT',name,json.dumps({k: {'n':v['overall']['closed_trades'],'net':v['overall']['net_usd'],
               'pf':v['overall']['profit_factor'],'dd':v['overall']['max_intrabar_proxy_dd_pct'],
               'blocked':v['overall']['blocked'],'monthly_net':{m:r['net_usd'] for m,r in v['months'].items()}}
               for k,v in c.items()},sort_keys=True),item['research_screen_pass'],flush=True)
    print('V7_SCREEN',report['candidate_for_forward'],'LIVE',report['approved_for_live'],flush=True)

if __name__=='__main__':main()