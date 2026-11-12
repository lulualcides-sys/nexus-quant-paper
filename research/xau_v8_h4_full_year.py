"""Preserved H4 gold strategy validation on pinned historic Dukascopy BID/ASK.

Apr-Sep 2025 is warmup only, Oct 2025-Sep 2026 is retrospective year.
No optimizing and no real broker orders. History is not truly unexamined.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from math import isfinite
from pathlib import Path
from statistics import median
import argparse
import json

from research.xau_v6_bidask_research import combine_minutes, aggregate_m5
from research.xau_v7_preserved_h4_bidask import (
    SOURCE_REPO, SOURCE_COMMIT, M5,H4,RULES,read_monthly_side,get_raw,backtest
)
from src.strategies import make_indicators

CALENDAR=tuple((y,m) for y,months in ((2025,range(4,13)),(2026,range(1,10))) for m in months)
EVAL_FIRST=int(datetime(2025,10,1,tzinfo=timezone.utc).timestamp())
EVAL_LAST=int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp())
QUARTERS=(
 ('2025-Q4',datetime(2025,10,1,tzinfo=timezone.utc),datetime(2026,1,1,tzinfo=timezone.utc)),
 ('2026-Q1',datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,4,1,tzinfo=timezone.utc)),
 ('2026-Q2',datetime(2026,4,1,tzinfo=timezone.utc),datetime(2026,7,1,tzinfo=timezone.utc)),
 ('2026-Q3',datetime(2026,7,1,tzinfo=timezone.utc),datetime(2026,10,1,tzinfo=timezone.utc)),
)
CAPITALS=(5000.,10000.,20000.) # capital sensitivity, NOT investment guidance
SLIPPAGES=(.15,.75)


def load_h4(*,downloader=get_raw):
    complete_m5=[];files=[];orphan=0;incomplete_m5=0;open_spreads=[]
    for yr,mth in CALENDAR:
        quotes={}
        for side in ('bid','ask'):
            filename=f'xauusd_{side}_m1_{yr}_{mth:02d}.csv'
            url=(f'https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/'
                 f'xauusd/{side}/m1/{filename}')
            raw=downloader(url)
            rows=read_monthly_side(raw,yr,mth)
            quotes[side]=rows
            files.append({'file':filename,'sha256':sha256(raw).hexdigest(),'bytes':len(raw),'rows':len(rows)})
        synced,counts=combine_minutes(quotes['bid'],quotes['ask'])
        if counts['orphan_minutes']>60:raise ValueError('BID/ASK asymmetry too high')
        orphan+=counts['orphan_minutes']
        grouped,q=aggregate_m5(synced)
        if len(grouped)<500:raise ValueError('Missing meaningful monthly M5 source')
        incomplete_m5+=q['excluded_incomplete_m5_buckets']
        open_spreads += [r['ask']['open']-r['bid']['open'] for r in grouped]
        complete_m5.extend(grouped)
    by_h4=defaultdict(list)
    for b in complete_m5:by_h4[b['time']//H4*H4].append(b)
    bars=[];skip=0
    for t,raws in sorted(by_h4.items()):
        rows=sorted(raws,key=lambda r:r['time'])
        if len(rows)!=48 or any(b['time']!=t+M5*i for i,b in enumerate(rows)):
            skip+=1;continue
        bid={k: (rows[0]['bid']['open'] if k=='open' else rows[-1]['bid']['close'] if k=='close' else
                 max(b['bid']['high'] for b in rows) if k=='high' else min(b['bid']['low'] for b in rows))
             for k in ('open','high','low','close')}
        ask={k: (rows[0]['ask']['open'] if k=='open' else rows[-1]['ask']['close'] if k=='close' else
                 max(b['ask']['high'] for b in rows) if k=='high' else min(b['ask']['low'] for b in rows))
             for k in ('open','high','low','close')}
        mid={k:(bid[k]+ask[k])/2 for k in ('open','high','low','close')}
        if mid['low']>min(mid['open'],mid['close']) or mid['high']<max(mid['open'],mid['close']):
            raise ValueError('Invalid H4 mid derived from observed quotes')
        bars.append({'time':t,**mid,'bid':bid,'ask':ask})
    if len(bars)<1500 or bars[0]['time']>=int(datetime(2025,5,1,tzinfo=timezone.utc).timestamp()):
        raise ValueError('Insufficient H4 warmup observed')
    if any(bars[i]['time']<=bars[i-1]['time'] for i in range(1,len(bars))):
        raise ValueError('Duplicate/out-of-order H4')
    after=[b for b in bars if EVAL_FIRST<=b['time']<EVAL_LAST]
    if len(after)<900:raise ValueError('Insufficient H4 test year')
    return bars,{'files':files,'repo':SOURCE_REPO,'commit':SOURCE_COMMIT,
                 'h4_count':len(bars),'h4_test_period_count':len(after),
                 'incomplete_h4_omitted':skip,'incomplete_m5_omitted':incomplete_m5,
                 'orphan_side_minutes':orphan,'median_open_spread_per_oz':round(median(open_spreads),4),
                 'test_start_utc':'2025-10-01','test_end_exclusive_utc':'2026-10-01',
                 'warmup_begin_utc':'2025-04-01',
                 'no_synthetic_prices':True,'source_not_fbs':True}


def run(rows):
    feats=make_indicators(rows)
    report={'study':'V8 frozen original H4 signal family full-year BID/ASK quote replay',
            'paper_only':True,'live_approved':False,'historical_research_not_untouched':True,
            'no_strategy_tuning':True,'strategy_families':list(RULES),
            'initial_capitals':list(CAPITALS),'slippage_per_side':list(SLIPPAGES),
            'year_bounds_utc':['2025-10-01','2026-10-01'],'strategies':{},
            'eligible_retrospective_research':[]}
    for name in RULES:
        reports={}
        for capital in CAPITALS:
            for slip in SLIPPAGES:
                full=backtest(rows,feats,name,begin=EVAL_FIRST,finish=EVAL_LAST,
                              capital=capital,slippage=slip,lot_step=1.)
                quarters={}
                for key,first,last in QUARTERS:
                    part=backtest(rows,feats,name,begin=int(first.timestamp()),finish=int(last.timestamp()),
                                  capital=capital,slippage=slip,lot_step=1.)
                    quarters[key]={k:v for k,v in part.items() if k!='ledger'}
                k=f'capital_{int(capital)}_slip_{slip:.2f}'
                reports[k]={'overall':{k:v for k,v in full.items() if k!='ledger'},
                            'quarters':quarters,'ledger':full['ledger']}
        # Only the 10k sizing cohort is a diagnostic benchmark; cannot approve by observing another bankroll.
        normal=reports['capital_10000_slip_0.15'];stress=reports['capital_10000_slip_0.75']
        ok=(normal['overall']['closed_trades']>=30 and
            normal['overall']['net_usd']>0 and stress['overall']['net_usd']>0 and
            all(normal['quarters'][k]['net_usd']>0 and stress['quarters'][k]['net_usd']>0 for k in normal['quarters']) and
            stress['overall']['max_intrabar_proxy_dd_pct']<=12)
        report['strategies'][name]={'sizing_and_execution':reports,'research_screen_pass':ok,'live_approved':False}
        if ok:report['eligible_retrospective_research'].append(name)
    return report


def markdown(report):
    lines=['# XAU V8 — ano completo de robôs H4 preservados, BID/ASK spot', '',
           '**Pesquisa retrospectiva; não são fills da FBS e lucro real não é comprovado.**',
           'Lotes mínimos de uma onça, risco-stop <=0.75%, posição nocional <=1x, sem alavancagem; cada candidato é conta virtual independente.',
           'Sem adaptação de gatilhos/stop/alvo para o histórico. 2025-04 a 2025-09 aquece EMA200 H4. Avaliação 2025-10 a 2026-09.', '',
           '| Modelo | Banca | Operações 0,15 | Resultado líquido 0,15 | PF 0,15 | Resultado líquido 0,75 | Q4/25 | Q1/26 | Q2/26 | Q3/26 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,item in report['strategies'].items():
        for capital in CAPITALS:
            c=item['sizing_and_execution'];a=c[f'capital_{int(capital)}_slip_0.15'];b=c[f'capital_{int(capital)}_slip_0.75']
            q=[a['quarters'][n]['net_usd'] for n,_,_ in QUARTERS]
            lines.append(f"| {name} | {int(capital)} | {a['overall']['closed_trades']} | {a['overall']['net_usd']:+.2f} | {a['overall']['profit_factor']} | {b['overall']['net_usd']:+.2f} | " + ' | '.join(f'{v:+.2f}' for v in q) + ' |')
    lines +=['', '**Ponto crítico:** resultados são baseados em histórico já estudado pelo projeto, não em forward. Sem swap/financiamento/FBS requote/impacto.',
             'Não escolher o maior resultado entre capitais como otimização. Os grupos com banca de US$10 mil/20 mil são só teste de execução do lote mínimo; não recomendam aporte.',
             'As janelas trimestrais reinicializam US$5 mil/10 mil/20 mil e não são somadas ao capital contínuo.',
             'Todos os testes usam as mesmas regras de sinais H4 importadas do código existente, não recriações que permitiriam mudar os sinais.',
             'Cenários positivos isolados com menos de 30 trades permanecem inconclusivos; prova de lucro não pode ser declarada.', '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json',default='research/results/xau_v8_h4_full_year.json')
    parser.add_argument('--md',default='research/results/xau_v8_h4_full_year.md');args=parser.parse_args()
    bars,metadata=load_h4();report=run(bars);report['source_metadata']=metadata
    dst=Path(args.json);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    Path(args.md).write_text(markdown(report)+'\n',encoding='utf8')
    print('V8_DATA',json.dumps({k:v for k,v in metadata.items() if k!='files'},sort_keys=True),flush=True)
    for name,cohort in report['strategies'].items():
        for key,item in cohort['sizing_and_execution'].items():
            o=item['overall']
            print('V8_RESULT',name,key,'n',o['closed_trades'],'net',o['net_usd'],'return_pct',o['return_pct'],
                  'pf',o['profit_factor'],'dd',o['max_intrabar_proxy_dd_pct'],
                  'quarters',[x['net_usd'] for x in item['quarters'].values()],flush=True)
    print('V8_SCREEN',report['eligible_retrospective_research'],'LIVE',report['live_approved'],flush=True)

if __name__=='__main__':main()