"""Run V5 against frozen GC=F and archived Dukascopy XAUUSD observations.

Only reads historical artifacts supplied by the workflow. No broker access,
no synthetic market prices, no retrospective edits of previous engines.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from math import isfinite
import gzip
import json

from research.indicator_fusion_v5_exits import paired_runs, TF_SECONDS

YAHOO_GZIP_SHA256 = 'e108c0b2aea67a913148c1922fe7568f7e464c5720360e1006547caf874fa79f'
EXPECTED_DUKA_SESSIONS = 24
DUKASCOPY_DAILY_ARCHIVE_SHA256 = '0fd2f4111bae5b71410deaa8e623f84f35a35f6d1ca4964950c45c6e65a95b2a'


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _dt(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def _validate_rows(rows, *, require_spread=False):
    if len(rows) < 600:
        raise ValueError('frozen feed has too few observed bars')
    previous = -1
    for row in rows:
        if not isinstance(row['time'], int) or row['time'] <= previous:
            raise ValueError('out of order or duplicated candles')
        previous = row['time']
        if any(not isinstance(row.get(k),(float,int)) or not isfinite(row[k]) or row[k]<=0 for k in ('open','high','low','close')):
            raise ValueError('bad observed OHLC')
        if row['low']>min(row['open'],row['close']) or row['high']<max(row['open'],row['close']):
            raise ValueError('impossible observed OHLC')
        if row['time'] % TF_SECONDS != 0:
            raise ValueError('unaligned observed M5')
        if require_spread and (not isinstance(row.get('max_spread'),(float,int)) or
                               not isfinite(row['max_spread']) or row['max_spread']<0):
            raise ValueError('Dukascopy max spread unavailable')
    return rows


def load_frozen_yahoo(path):
    if _sha(path) != YAHOO_GZIP_SHA256:
        raise ValueError('Yahoo frozen price fingerprint mismatch')
    with gzip.open(path,'rt',encoding='utf-8') as f:
        rows=json.load(f)
    if not isinstance(rows,list):
        raise ValueError('Yahoo data not an observed bar list')
    return _validate_rows(rows)


def _session_bars(rows):
    """12:00-20:55 UTC is the common actually observed window (9h)."""
    result=[]
    for row in rows:
        dt=_dt(row['time'])
        if 12 <= dt.hour <= 20:
            result.append(row)
    return result


def load_frozen_dukascopy(directory):
    base=Path(directory)/'xau-candles'
    names=sorted(base.glob('*.json'))
    if not names:
        raise ValueError('Dukascopy archive not materialized by CI')
    source_hashes=[]; allrows=[]; accepted=[]; quarantined=[]
    digest=sha256()
    for path in names:
        data=json.loads(path.read_text(encoding='utf8'))
        if data.get('day')!=path.stem:
            raise ValueError('Dukascopy day label mismatch')
        if data.get('quarantined'):
            quarantined.append(path.stem)
            continue
        if data.get('source')!='XAUUSD Dukascopy bid/ask quotes':
            raise ValueError('Dukascopy source label mismatch')
        rows=data.get('bars',{}).get('M5')
        if not isinstance(rows,list) or len(rows)<100:
            raise ValueError('Dukascopy day incomplete')
        rows=_session_bars(rows)
        if len(rows)!=108:
            raise ValueError(f'Incomplete Dukascopy selected UTC session: {path.stem}: {len(rows)}')
        if _dt(rows[0]['time']).strftime('%H:%M')!='12:00' or _dt(rows[-1]['time']).strftime('%H:%M')!='20:55':
            raise ValueError('Dukascopy session window incomplete')
        _validate_session(rows)
        allrows.extend(rows); accepted.append(path.stem)
        digest.update(path.name.encode()+b'\0'+path.read_bytes()+b'\0')
        source_hashes.append((path.stem, _sha(path),data['source_sha256']))
    if digest.hexdigest()!=DUKASCOPY_DAILY_ARCHIVE_SHA256:
        raise ValueError('Dukascopy frozen daily artifact checksum mismatch')
    if len(accepted)!=EXPECTED_DUKA_SESSIONS:
        raise ValueError(f'Dukascopy days: expected {EXPECTED_DUKA_SESSIONS}, got {len(accepted)}')
    if sorted(quarantined)!=['20261106']:
        raise ValueError('Quarantine information changed')
    _validate_rows(allrows,require_spread=True)
    return allrows,{'n_valid_days':len(accepted),'excluded_quarantined_days':quarantined,
                    'source_day_hashes':source_hashes,'frozen_daily_sha256':digest.hexdigest()}


def _validate_session(rows):
    if any(rows[i]['time']-rows[i-1]['time']!=TF_SECONDS for i in range(1,len(rows))):
        raise ValueError('Dukascopy missing within-session bar')


def match_sessions(yahoo,duka):
    by_day_y=defaultdict(dict)
    by_day_d=defaultdict(dict)
    for b in _session_bars(yahoo):
        by_day_y[_dt(b['time']).strftime('%Y%m%d')][b['time']]=b
    for b in duka:
        by_day_d[_dt(b['time']).strftime('%Y%m%d')][b['time']]=b
    days=sorted(set(by_day_y)&set(by_day_d))
    # Require actual UTC last observed candle 20:55 in both for daily flatten.
    valid_days=[]
    for day in days:
        y=by_day_y[day];d=by_day_d[day]
        h={'20:55':0}
        yt={_dt(t).strftime('%H:%M') for t in y}
        dt={_dt(t).strftime('%H:%M') for t in d}
        if '20:55' in yt and '20:55' in dt:
            valid_days.append(day)
    if len(valid_days)<15:
        raise ValueError('Too few matched source calendar sessions')
    common={t for day in valid_days for t in (set(by_day_y[day])&set(by_day_d[day]))}
    yy=[b for b in _session_bars(yahoo) if b['time'] in common]
    dd=[b for b in duka if b['time'] in common]
    _validate_rows(yy);_validate_rows(dd,require_spread=True)
    assert [b['time'] for b in yy]==[b['time'] for b in dd]
    return yy, dd, {'matched_days':valid_days,'matched_candles':len(yy),
                    'identical_timestamps':True,'no_synthetic_backfill':True}


def _copy_summary(d):
    return {k: v for k, v in d.items() if k not in ('ledger',)}


def run(yahoo_gzip,dukascopy_dir):
    yahoo=load_frozen_yahoo(yahoo_gzip)
    # Invariant: unchanged V4 exit reproduces historical V3 portfolio with
    # identical fills on every observed price bar, not just synthetic tests.
    from research.indicator_fusion_v5_exits import ablated_signals, replay_v5, original_portfolio, DEFAULT_PARAMETERS
    base_atr,base_sig=ablated_signals(yahoo)
    for per_oz in (.61,1.81):
        original=original_portfolio(yahoo,base_atr,base_sig,fee_per_oz=per_oz,fee_bps=0,**DEFAULT_PARAMETERS)
        copied=replay_v5(yahoo,base_atr,base_sig,fee_per_oz=per_oz,fee_bps=0,policy='fixed_v4',**DEFAULT_PARAMETERS)
        if (original['closed_trades']!=copied['closed_trades'] or
            original['net_usd']!=copied['net_usd'] or
            [(t['entry_i'],t['exit_i'],t['bot'],t['reason']) for t in original['ledger']] !=
            [(t['entry_i'],t['exit_i'],t['bot'],t['reason']) for t in copied['ledger']]):
            raise AssertionError('V4 baseline mismatch: abort V5 report')
    duka,dkmeta=load_frozen_dukascopy(dukascopy_dir)
    my,md,matched=match_sessions(yahoo,duka)
    data={'study':'V5 GOLD causal exit management against two historical sources',
          'paper_only':True,'approved_for_live':False,'previously_inspected_history':True,
          'no_independent_new_holdout':True,'no_actual_broker_fills':True,
          'target_200_per_30_days_not_order_quota':True,
          'yahoo_frozen_gzip_sha256':_sha(yahoo_gzip),
          'v4_unchanged_baseline_parity_verified':True,
          'duka_provenance':dkmeta,'matched_provenance':matched,
          'sources':{
              'Yahoo_GCF_full_M5':paired_runs(yahoo,dataset_name='Frozen Yahoo GC=F M5 ~30 calendar days',partial_sessions=False),
              'Dukascopy_XAUUSD_partial_UTC12_2055':paired_runs(duka,dataset_name='Dukascopy XAUUSD M5 UTC 12:00–20:55 only',partial_sessions=True),
              'Yahoo_GCF_matched_UTC12_2055':paired_runs(my,dataset_name='Yahoo GC=F M5 exact matched timestamps UTC 12:00–20:55',partial_sessions=True),
              'Dukascopy_XAUUSD_matched_UTC12_2055':paired_runs(md,dataset_name='Dukascopy XAUUSD M5 exact matched timestamps UTC 12:00–20:55',partial_sessions=True),
          }}
    return data


def format_report(report):
    out=['# GOLD V5 — comparação de saídas nas mesmas datas e duas fontes', '',
         '**Pesquisa retrospectiva sem ordens reais; histórico previamente consultado no projeto, não é holdout intocado.**',
         'Testes V4/V5 usam uma única posição por vez, os mesmos sinais (Momentum desabilitado pós-hoc) e mesmo capital inicial US$ 5.000.',
         'M5 entrada no próximo candle, sem antecipação do movimento; stop-first para ambiguidade intrabar.',
         'Spread de US$ 0,61 / 1,81 / 3,31 por onça simulado, não spreads reais da FBS; Dukascopy `max_spread` de candle é diagnóstico de estresse, não execução observada.',
         '', '## Comparações independentes de origem de preço', '',
         '| Fonte | Janela | Saída | Operações | 30 dias estimadas | 0,61 USD/oz | 1,81 USD/oz | 3,31 USD/oz | Folds todos + em 0,61 e 1,81? |',
         '|---|---|---|---:|---:|---:|---:|---:|---|']
    for source,v in report['sources'].items():
        partial=v['partial_sessions']
        for policy,results in v['by_policy'].items():
            s=results['scenarios']; norm=s['spread_0p61']['trades_per_30_calendar_days_estimate']
            out.append(f"| {source} | {'9h/dia parcial' if partial else '~24h/dia'} | {policy} | {s['spread_0p61']['closed_trades']} | {norm} | {s['spread_0p61']['net_usd']:+.2f} | {s['spread_1p81']['net_usd']:+.2f} | {s['spread_3p31']['net_usd']:+.2f} | {'Sim' if results['retrospective_consistency_pass'] else 'Não'} |")
    out += ['', '## Custos de spread observado apenas na Dukascopy', '',
            '| Fonte e política | Resultado com spread máximo de candle (média da entrada/saída) + US$0,15 por lado |',
            '|---|---:|']
    for source,v in report['sources'].items():
        if not v['partial_sessions']: continue
        for p,res in v['by_policy'].items():
            obj=res['scenarios'].get('observed_max_spread_plus_0p15_each_side')
            if obj is None:continue
            out.append(f"| {source} — {p} | {obj['net_usd']:+.2f} |")
    out += ['', '## Limitações e critérios', '',
            '- O feed Dukascopy inclui apenas UTC 12:00–20:55 (9 horas por sessão). Não extrapolar sua taxa para 24h nem declarar 200 entradas em um mês completo.',
            '- Yahoo GC=F é futuro de ouro; Dukascopy é spot XAUUSD; diferenças de instrumento podem alterar sinais e stop.',
            '- A conversão temporal usa exatamente os timestamps comuns; candles ausentes não são inventados.',
            '- Custos de execução não incluem swaps, requotes, impacto, erros de conectividade ou comissões específicas da conta.',
            '- A segunda fonte e as três saídas são diagnósticos retrospectivos, não forward prospectivo.',
            '- Se trailing só melhorar numa origem e piorar na outra, não o promover. Sem lucro comprovado nos segmentos de validação.',
            '- As estratégias salvas, estados e PR principal permanecem intactos; nenhuma execução real.', '']
    return '\n'.join(out)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--yahoo-gzip',type=Path,required=True)
    parser.add_argument('--dukascopy-dir',type=Path,required=True)
    p=parser.parse_args()
    data=run(p.yahoo_gzip,p.dukascopy_dir)
    output=Path('research/results');output.mkdir(parents=True,exist_ok=True)
    json_path=output/'indicator_fusion_v5_exit_latest.json'
    md_path=output/'indicator_fusion_v5_exit_latest.md'
    json_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    md_path.write_text(format_report(data),encoding='utf8')
    print('V5_INPUT_SHA256',data['yahoo_frozen_gzip_sha256'],flush=True)
    print('V5_MATCHED_SESSIONS',len(data['matched_provenance']['matched_days']),data['matched_provenance']['matched_candles'],flush=True)
    for source,cohort in data['sources'].items():
        for policy,v in cohort['by_policy'].items():
            summary=v['scenarios'];normal=summary['spread_0p61'];stress=summary['spread_1p81']
            print('V5_RESULT',source,policy,normal['closed_trades'],normal['trades_per_30_calendar_days_estimate'],normal['net_usd'],stress['net_usd'],v['retrospective_consistency_pass'],flush=True)
    print('V5_REPORT',json_path,md_path,flush=True)

if __name__=='__main__':main()