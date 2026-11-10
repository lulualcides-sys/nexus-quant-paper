"""Post-hoc uncertainty diagnostic on already computed original H4 spot trades.

Not a forward test, not a model-selection tool and not a probability guarantee.
Only reorganizes real historical closed trade PnLs, no new price candles.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import json
import random
from statistics import median

SEED=20261110
N_SAMPLES=5000
LOW_Q=0.025
UP_Q=0.975


def bootstrap_days(ledger,*,seed=SEED,samples=N_SAMPLES):
    if samples<100:raise ValueError('Require at least 100 resamples')
    by_day=defaultdict(float)
    for t in ledger:
        if not isinstance(t['net'],(int,float)) or 'exit_ts' not in t:
            raise ValueError('Invalid closed ledger')
        day=datetime.fromtimestamp(t['exit_ts'],timezone.utc).strftime('%Y-%m-%d')
        by_day[day]+=t['net']
    vals=list(by_day.values());n=len(vals)
    if n<15:
        return {'status':'too_few_exit_days','days':n,'trades':len(ledger),
                'observed_net':round(sum(vals),2),'interval_95':None,'p_nonpositive':None}
    rng=random.Random(seed)
    results=sorted(sum(vals[rng.randrange(n)] for _ in range(n)) for _ in range(samples))
    return {'status':'diagnostic_only','days':n,'trades':len(ledger),
            'observed_net':round(sum(vals),2),
            'interval_95':[round(results[int(LOW_Q*samples)],2),round(results[int(UP_Q*samples)],2)],
            'p_nonpositive':round(sum(v<=0 for v in results)/samples,4),
            'seed':seed,'samples':samples,
            'warning':'Naive iid exit-day bootstrap after historical strategy selection; trading days correlated, so NOT a valid prospective probability or 95% guarantee'}


def audit(source):
    out={'posthoc_only':True,'live_approved':False,'not_new_market_data':True,
         'bootstrap_not_probability_of_future_profit':True,'by_strategy':{}}
    for name,bot in source['strategies'].items():
        series={}
        for slip in ('0.15','0.75'):
            book=bot['sizing_and_execution'][f'capital_10000_slip_{slip}']
            trades=book['ledger'];pnl=book['overall']['net_usd']
            r=bootstrap_days(trades)
            if abs(r['observed_net']-pnl)>0.02:raise ValueError('Audit ledger does not match headline closed PnL')
            gains=sum(t['net'] for t in trades if t['net']>0)
            losses=sum(t['net'] for t in trades if t['net']<0)
            r['wins']=sum(t['net']>0 for t in trades)
            r['losses']=sum(t['net']<0 for t in trades)
            r['median_trade_net']=round(median([t['net'] for t in trades]),2) if trades else None
            r['sum_winner_pnl']=round(gains,2);r['sum_loser_pnl']=round(losses,2)
            series[f'slippage_per_side_{slip}']=r
        out['by_strategy'][name]=series
    return out


def format_markdown(result):
    lines=['# XAU V8 — diagnóstico de incerteza retrospectiva das operações H4', '',
           '**CUIDADO:** bootstrap pós-hoc por dias com fechamento; não transforma amostra já selecionada em validação prospectiva nem implica probabilidade real de lucro.', '',
           '| Robô | Custo adicional USD/onça/lado | Fechadas | Vencedoras | Líquido USD | Intervalo reamostrado 95% USD | Fração <=0 nas reamostragens |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for name,scenarios in result['by_strategy'].items():
        for key,row in scenarios.items():
            cost=key.removeprefix('slippage_per_side_')
            iv=row['interval_95']; iv=f"{iv[0]:+.2f} até {iv[1]:+.2f}" if iv else 'Dados insuficientes'
            lines.append(f"| {name} | {cost} | {row['trades']} | {row['wins']} | {row['observed_net']:+.2f} | {iv} | {row['p_nonpositive']} |")
    lines.extend(['','- Bancas: US$ 10.000 virtuais, uma posição por robô, risco-stop <=0,75%, spread bid/ask observado e custos por lado simulados.',
                  '- P&L reproduz integralmente o JSON do workflow V8; este script não modifica regras nem faz novas operações.',
                  '- Datas de fechamento são amostradas independentemente; isso ignora dependência temporal, regimes de volatilidade, múltiplos regimes e seleção retrospectiva entre estratégias e bancas.',
                  '- Intervalo que alcança prejuízo é sinal de incerteza; intervalo que exclui zero também não constitui aprovação de capital real.',
                  '- Apenas acompanhamento prospectivo e custos/executabilidade no corretor podem fundamentar uma decisão posterior.', ''])
    return '\n'.join(lines)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',default='research/results/xau_v8_h4_full_year.json')
    ap.add_argument('--output',default='research/results/xau_v8_bootstrap_audit.json')
    ap.add_argument('--md',default='research/results/xau_v8_bootstrap_audit.md')
    a=ap.parse_args()
    source=json.loads(Path(a.source).read_text(encoding='utf8'))
    report=audit(source)
    Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    Path(a.md).write_text(format_markdown(report)+'\n',encoding='utf8')
    for name,v in report['by_strategy'].items():
        for key,x in v.items():
            print('V8_BOOTSTRAP',name,key,'n',x['trades'],'net',x['observed_net'],
                  'CI',x['interval_95'],'fraction_nonpositive',x['p_nonpositive'],flush=True)

if __name__=='__main__':main()