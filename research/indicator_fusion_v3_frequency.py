"""High-frequency XAU research: 200/month is a TARGET, never an order quota.

Uses only closed OHLC bars. A real one-position-per-symbol paper portfolio,
with deterministic signal priority, no same-bar re-entry, and per-trade fees.
No modification of preserved robots, no broker or paper-state side effects.
"""
from __future__ import annotations
from collections import Counter
from calendar import monthrange
from datetime import datetime, timezone
from math import isfinite, floor
from statistics import mean

from research.indicator_fusion_bots import check_bars, ema, atr_wilder, TIMEFRAMES

NAMES = ('EMA20_RECLAIM', 'CHANNEL12_BREAK', 'PIVOT_SWEEP',
         'MOMENTUM_2BAR', 'RANGE_EDGE_REJECTION')
WARMUP = 220
MAX_HOLD = 12                  # 1h on M5, fixed before evaluation
RISK_FRAC = .0035             # planned stop risk <=0.35% portfolio equity
STOP_ATR = 1.25
TARGET_R = 1.8
MONTHLY_TARGET = 200


def features_and_signals(bars):
    """Priors only, signal at close[i] and order eligible at open[i+1].

    No higher-TF filter stack. One primary structural trigger per model,
    candle direction only where needed to define reversal/reclaim.
    """
    check_bars(bars)
    close = [b['close'] for b in bars]
    a = atr_wilder(bars, 10)
    e20 = ema(close, 20)
    signals = {name:[0]*len(bars) for name in NAMES}
    cooldown = {name: -10000 for name in NAMES}
    expected_interval = min(bars[i]['time']-bars[i-1]['time'] for i in range(1,len(bars)))
    for i in range(WARMUP,len(bars)):
        if bars[i]['time']-bars[i-1]['time'] != expected_interval:
            continue
        b,p=bars[i],bars[i-1]
        atr = a[i]
        if atr <= 0: continue
        side = {}
        # 20 EMA recapture after a touch: no 6x EMA alignment.
        if p['close'] < e20[i-1] and b['close'] > e20[i] and b['close']>b['open']:
            side[NAMES[0]] = 1
        elif p['close'] > e20[i-1] and b['close'] < e20[i] and b['close']<b['open']:
            side[NAMES[0]] = -1
        # Short channel - frequent structure breaks, previous 12 bars only.
        h12 = max(x['high'] for x in bars[i-12:i]); l12=min(x['low'] for x in bars[i-12:i])
        if b['close'] > h12 and p['close'] <= h12:
            side[NAMES[1]] = 1
        elif b['close'] < l12 and p['close'] >= l12:
            side[NAMES[1]] = -1
        # Liquidity sweep of rolling 8-bar levels, reclaim on same *closed* bar.
        h8 = max(x['high'] for x in bars[i-8:i]); l8=min(x['low'] for x in bars[i-8:i])
        if b['low'] < l8 and b['close'] > l8 and b['close']>b['open']:
            side[NAMES[2]] = 1
        elif b['high'] > h8 and b['close'] < h8 and b['close']<b['open']:
            side[NAMES[2]] = -1
        # Two-candle continuation with a break of previous candle high/low.
        if (b['close']>p['high'] and b['close']>b['open'] and p['close']>p['open']):
            side[NAMES[3]] = 1
        elif (b['close']<p['low'] and b['close']<b['open'] and p['close']<p['open']):
            side[NAMES[3]] = -1
        # Rolling range extreme rejection; repeated signal requires fresh bar.
        h16=max(x['high'] for x in bars[i-16:i]); l16=min(x['low'] for x in bars[i-16:i])
        if b['low'] < l16 and b['close'] > l16 + .10*atr and b['close']>b['open']:
            side[NAMES[4]]=1
        elif b['high'] > h16 and b['close'] < h16 - .10*atr and b['close']<b['open']:
            side[NAMES[4]]=-1
        for name,direction in side.items():
            # No cap on monthly trades; 2 bars cooldown avoids duplicate flicker.
            if i-cooldown[name]>=2:
                signals[name][i]=direction
                cooldown[name]=i
    return a,signals


def _time_month(ts):
    return datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m')


def _close(position,exit_price,bar_i,reason,fee_bps,fee_per_oz=0.):
    p=position
    gross=p['side']*(exit_price-p['entry'])*p['qty']
    fee=p['qty']*(p['entry']*fee_bps/10000+fee_per_oz)
    return {'bot':p['bot'],'side':p['side'],'entry_i':p['entry_i'],
            'exit_i':bar_i,'entry_time':p['entry_time'],
            'entry':p['entry'],'exit':exit_price,'qty':p['qty'],
            'gross':gross,'cost':fee,'net':gross-fee,'reason':reason}


def portfolio(bars,atr,sig,*,fee_bps=14.,start=None,end=None,capital=5000.,
              interval=300,max_hold=MAX_HOLD,stop_atr=STOP_ATR,target_r=TARGET_R,
              risk_frac=RISK_FRAC,min_qty_step_oz=None,fee_per_oz=0.):
    """One real position on XAU, no overlapping virtual books or double-counting.

    At each candle OPEN, an existing position occupies the bar, even if
    it exits before CLOSE; avoids retroactive next entry. Stops/targets are
    evaluated after the opening gap. Intrabar ambiguity is stop-first.
    """
    check_bars(bars,interval)
    if (fee_bps<0 or capital<=0 or max_hold<1 or fee_per_oz<0 or
        risk_frac<=0 or risk_frac>1 or stop_atr<=0 or target_r<=0 or
        (min_qty_step_oz is not None and min_qty_step_oz<=0)):
        raise ValueError('invalid settings')
    if set(sig)!=set(NAMES) or any(len(v)!=len(bars) for v in sig.values()):
        raise ValueError('signal dimensions')
    first=max(WARMUP+1,start if start is not None else WARMUP+1)
    final=min(end if end is not None else len(bars),len(bars))
    if final<=first:raise ValueError('empty replay')
    pnl=[];equity=capital;peak=capital;dd=0.;position=None
    seen_candidates=Counter();blocked_position=Counter();blocked_gap=Counter()
    entered=Counter(); min_lot_rejections=0
    for i in range(first,final):
        b=bars[i]
        occupied=position is not None
        if occupied:
            p=position;s=p['side']
            if (s==1 and b['open']<=p['stop']) or (s==-1 and b['open']>=p['stop']):
                fill=b['open'];reason='stop_gap'
            elif (s==1 and b['open']>=p['target']) or (s==-1 and b['open']<=p['target']):
                fill=p['target'];reason='target_gap'
            elif (s==1 and b['low']<=p['stop']) or (s==-1 and b['high']>=p['stop']):
                fill=p['stop'];reason='stop'
            elif (s==1 and b['high']>=p['target']) or (s==-1 and b['low']<=p['target']):
                fill=p['target'];reason='target'
            elif i-p['entry_i']>=max_hold:
                fill=b['close'];reason='time'
            else:
                fill=None
            if fill is not None:
                trade=_close(p,fill,i,reason,fee_bps,fee_per_oz)
                pnl.append(trade);equity+=trade['net']
                peak=max(peak,equity)
                if peak>0: dd=max(dd,(peak-equity)/peak*100)
                position=None
        choices=[(name,sig[name][i-1]) for name in NAMES if sig[name][i-1]]
        for name,_ in choices:seen_candidates[name]+=1
        if occupied:
            for name,_ in choices:blocked_position[name]+=1
            continue
        # Causal: no entry on missing bar/gap at next open.
        if bars[i]['time']-bars[i-1]['time'] != interval:
            for name,_ in choices:blocked_gap[name]+=1
            continue
        if not choices or equity<=0:continue
        # Priority precommitted by fixed order; no retrospective selection.
        name,side=choices[0]
        entry=b['open'];dist=stop_atr*atr[i-1]
        if not isfinite(dist) or dist<=0:continue
        qty=min(equity*risk_frac/dist,equity/entry)
        if min_qty_step_oz is not None:
            qty=floor((qty+1e-9)/min_qty_step_oz)*min_qty_step_oz
            if qty<=0:
                min_lot_rejections+=1
                continue
        if qty<=0:continue
        entered[name]+=1
        position={'bot':name,'side':side,'entry':entry,'qty':qty,
                  'entry_i':i,'entry_time':b['time'],
                  'stop':entry-side*dist,'target':entry+side*target_r*dist}
        # Candles after OPEN can hit stop/target on the entry candle.
        s=side
        if (s==1 and b['low']<=position['stop']) or (s==-1 and b['high']>=position['stop']):
            fill=position['stop'];reason='stop'
        elif (s==1 and b['high']>=position['target']) or (s==-1 and b['low']<=position['target']):
            fill=position['target'];reason='target'
        else:fill=None
        if fill is not None:
            trade=_close(position,fill,i,reason,fee_bps,fee_per_oz)
            pnl.append(trade);equity+=trade['net'];peak=max(peak,equity)
            if peak>0:dd=max(dd,(peak-equity)/peak*100)
            position=None
    floating=0
    if position is not None:
        last=bars[final-1]['close']
        floating=position['side']*(last-position['entry'])*position['qty']-position['qty']*(position['entry']*fee_bps/10000+fee_per_oz)
    winners=sum(t['net'] for t in pnl if t['net']>0)
    losers=-sum(t['net'] for t in pnl if t['net']<0)
    months=Counter(_time_month(t['entry_time']) for t in pnl)
    observed_days=(bars[final-1]['time']-bars[first]['time'])/86400
    normalized= len(pnl)*30/observed_days if observed_days>0 else None
    start_utc=datetime.fromtimestamp(bars[first]['time'],timezone.utc)
    end_utc=datetime.fromtimestamp(bars[final-1]['time'],timezone.utc)
    full_month_count=0
    for key,n in months.items():
        year,month=(int(v) for v in key.split('-'))
        # Require strict coverage of month start and month end. No partial
        # month's trade count may be claimed to meet a monthly quota.
        month_days=monthrange(year,month)[1]
        start_month=datetime(year,month,1,tzinfo=timezone.utc)
        end_month=datetime(year,month,month_days,23,55,tzinfo=timezone.utc)
        if start_utc <= start_month and end_utc >= end_month and n>=MONTHLY_TARGET:
            full_month_count+=1
    return {
        'closed_trades':len(pnl),'signals_total':sum(seen_candidates.values()),
        'signals_by_type':dict(seen_candidates),'entered_by_type':dict(entered),
        'blocked_by_open_position':dict(blocked_position),
        'blocked_at_data_gap':dict(blocked_gap),
        'min_lot_rejections':min_lot_rejections,
        'net_usd':round(equity-capital+floating,2),
        'realized_usd':round(equity-capital,2),
        'gross_usd':round(sum(t['gross'] for t in pnl),2),
        'fees_usd':round(sum(t['cost'] for t in pnl),2),
        'open_at_end':position is not None,
        'win_rate_pct':round(100*sum(t['net']>0 for t in pnl)/len(pnl),2) if pnl else None,
        'profit_factor':round(winners/losers,3) if losers else None,
        'max_realized_drawdown_pct':round(dd,3),
        'trade_counts_by_utc_month':dict(months),
        'trades_per_30_calendar_days_estimate':round(normalized,1) if normalized is not None else None,
        'goal_200_full_calendar_month_verified':full_month_count>0,
        'partial_month_counts_are_not_monthly_proof':True,
        'ledger':pnl,
    }


def research(bars,*,timeframe='M5',costs=(0.,7.,14.,28.)):
    if timeframe not in TIMEFRAMES:raise ValueError('timeframe')
    interval=TIMEFRAMES[timeframe]
    check_bars(bars,interval)
    a,s=features_and_signals(bars)
    out={'study':'XAU 200 entries/month feasibility; not quota',
         'market':'GC=F public gold futures proxy, NOT FBS XAUUSD',
         'timeframe':timeframe,'target_monthly_completed_trades':MONTHLY_TARGET,
         'paper_only':True,'live_approved':False,
         'previously_examined_data':True,
         'period_start':bars[WARMUP+1]['time'],'period_end':bars[-1]['time'],
         'bars':len(bars),'models':list(NAMES),'by_cost':{}}
    for fee in costs:
        x=portfolio(bars,a,s,fee_bps=fee,interval=interval)
        out['by_cost'][str(fee)]={k:v for k,v in x.items() if k!='ledger'}
    # Folds reset the account; counts are diagnostics, not an additive portfolio PnL.
    first=WARMUP+1
    cuts=[first]+[first+(len(bars)-first)*j//3 for j in (1,2)]+[len(bars)]
    out['folds_14_28bps']=[]
    for j in range(3):
        z14=portfolio(bars,a,s,fee_bps=14.,start=cuts[j],end=cuts[j+1],interval=interval)
        z28=portfolio(bars,a,s,fee_bps=28.,start=cuts[j],end=cuts[j+1],interval=interval)
        out['folds_14_28bps'].append({'start':bars[cuts[j]]['time'],
             'end':bars[cuts[j+1]-1]['time'],
             'n14':z14['closed_trades'],'net14':z14['net_usd'],'net28':z28['net_usd']})
    out['qualified_for_live']=False
    out['research_consistency_pass']=(all(z['net14']>0 and z['net28']>0 for z in out['folds_14_28bps'])
                                      and out['by_cost']['14.0']['closed_trades']>=50
                                      and out['by_cost']['28.0']['max_realized_drawdown_pct']<=10)
    return out