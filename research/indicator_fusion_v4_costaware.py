"""XAU paper only: high-frequency 200/month research with lot-aware FBS cost scenarios.

Optimized retrospectively for FREQUENCY on already-viewed historical data.
Positive numbers here are not untouched holdouts or real-world results.
"""
from __future__ import annotations
from datetime import datetime, timezone
from collections import defaultdict, Counter
from research.indicator_fusion_v3_frequency import (
    features_and_signals, portfolio, check_bars, TIMEFRAMES,
)

# These values were selected retrospectively after studying V3 frequency.
# NOT an independently tested strategy or validated future P&L.
STOP_ATR_V4 = 3.0
TARGET_R_V4 = 3.0
MAX_HOLD_V4 = 36
RISK_FRAC_V4 = .0075
LOT_STEP_OZ = 1.0   # 0.01 lots x 100 troy ounces per 1 standard lot.
FBS_TYPICAL_SPREAD_USD_PER_OZ = .31  # Reference from FBS site, not executed tick data.
SCENARIOS = {
    'zero_cost_diagnostic':dict(fee_bps=0, fee_per_oz=0),
    'fbs_typical_spread_only':dict(fee_bps=0,fee_per_oz=.31),
    'fbs_spread_plus_0p15_each_side':dict(fee_bps=0,fee_per_oz=.61),
    'fbs_spread_plus_0p75_each_side':dict(fee_bps=0,fee_per_oz=1.81),
    'fbs_spread_plus_1p50_each_side':dict(fee_bps=0,fee_per_oz=3.31),
    'legacy_stress_7bps':dict(fee_bps=7,fee_per_oz=0),
    'legacy_stress_14bps':dict(fee_bps=14,fee_per_oz=0),
    'legacy_stress_28bps':dict(fee_bps=28,fee_per_oz=0),
}


def run(bars, timeframe='M5'):
    if timeframe!='M5':raise ValueError('V4 is pre-defined for M5 only')
    check_bars(bars,TIMEFRAMES[timeframe])
    atr,sig=features_and_signals(bars)
    params=dict(interval=300,max_hold=MAX_HOLD_V4,stop_atr=STOP_ATR_V4,
                target_r=TARGET_R_V4,risk_frac=RISK_FRAC_V4,
                min_qty_step_oz=LOT_STEP_OZ)
    output={'paper_only':True,'qualified_for_live':False,
            'market':'GC=F Yahoo proxy, NOT FBS XAUUSD bid-ask',
            'timeframe':'M5','source_bars':len(bars),
            'start_utc':datetime.fromtimestamp(bars[0]['time'],timezone.utc).isoformat(),
            'end_utc':datetime.fromtimestamp(bars[-1]['time'],timezone.utc).isoformat(),
            'historically_optimized_for_trade_frequency':True,
            'parameters':{'stop_ATR10':STOP_ATR_V4,'target_R':TARGET_R_V4,
                          'max_hold_bars':MAX_HOLD_V4,'risk_fraction':RISK_FRAC_V4,
                          'one_oz_lot_steps':True},
            'cost_scenarios':{},'folds':[]}
    for name,fees in SCENARIOS.items():
        result=portfolio(bars,atr,sig,**params,**fees)
        summary={k:v for k,v in result.items() if k!='ledger'}
        groups=defaultdict(list)
        for trade in result['ledger']:
            groups[trade['bot']].append(trade)
        summary['per_bot_attribution']={name:{
            'closed_trades':len(trades),
            'net_usd':round(sum(t['net'] for t in trades),2),
            'fees_usd':round(sum(t['cost'] for t in trades),2),
            'exits':dict(Counter(t['reason'] for t in trades)),
        } for name,trades in groups.items()}
        output['cost_scenarios'][name]=summary
    first=221
    cuts=[first]+[first+(len(bars)-first)*i//3 for i in (1,2)]+[len(bars)]
    for i in range(3):
        row={'first_candle_time':bars[cuts[i]]['time'],
             'last_candle_time':bars[cuts[i+1]-1]['time']}
        for name in ('fbs_spread_plus_0p15_each_side','fbs_spread_plus_0p75_each_side','legacy_stress_14bps'):
            rr=portfolio(bars,atr,sig,start=cuts[i],end=cuts[i+1],**params,**SCENARIOS[name])
            row[name]={'closed_trades':rr['closed_trades'],'net_usd':rr['net_usd'],
                       'drawdown_pct':rr['max_realized_drawdown_pct']}
        output['folds'].append(row)
    # Post-hoc ablation is diagnostic ONLY. Chosen after seeing which models
    # lost money on this same dataset: it is not an independent holdout.
    disabled='MOMENTUM_2BAR'
    ablation={name:(series if name!=disabled else [0]*len(series))
              for name,series in sig.items()}
    study={'disabled_model':disabled,'post_hoc_selected':True,
           'approved_for_live':False,'by_cost':{},'folds':[]}
    for key in ('fbs_spread_plus_0p15_each_side','fbs_spread_plus_0p75_each_side',
                'fbs_spread_plus_1p50_each_side','legacy_stress_14bps'):
        rr=portfolio(bars,atr,ablation,**params,**SCENARIOS[key])
        study['by_cost'][key]={k:v for k,v in rr.items() if k!='ledger'}
    for i in range(3):
        row={'first':bars[cuts[i]]['time'],'last':bars[cuts[i+1]-1]['time']}
        for key in ('fbs_spread_plus_0p15_each_side','fbs_spread_plus_0p75_each_side'):
            rr=portfolio(bars,atr,ablation,start=cuts[i],end=cuts[i+1],
                         **params,**SCENARIOS[key])
            row[key]={'trades':rr['closed_trades'],'net':rr['net_usd']}
        study['folds'].append(row)
    output['posthoc_ablation_no_momentum']=study
    out=output['cost_scenarios']['fbs_spread_plus_0p15_each_side']
    output['observed_monthly_trade_count']=out['trade_counts_by_utc_month']
    output['estimate_30day_trades']=out['trades_per_30_calendar_days_estimate']
    output['frequency_target_met_as_30day_estimate']=(out['trades_per_30_calendar_days_estimate'] or 0)>=190
    output['robust_profit_confirmed']=False
    return output