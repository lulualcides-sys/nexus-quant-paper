"""XAUUSD indicator-fusion research robots, isolated from live/paper engines.

Derived candidates, NOT literal ports of Pine indicators and not proven profitable.
No broker connection, no orders, no state mutations, no fabricated candles.
Dependencies: Python standard library. Uses only completed OHLC bars.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import mean, pstdev

TIMEFRAMES = {'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800}
BOTS = ('BOS_DTC_QKE', 'RANGE_DTC_QKE', 'OB_RETEST', 'SWEEP_REVERSAL')
WARMUP = 220


def check_bars(bars, interval=None):
    if len(bars) < WARMUP + 3:
        raise ValueError('insufficient candles')
    previous = -1
    for b in bars:
        t = b['time']
        if not isinstance(t, int) or t <= previous:
            raise ValueError('duplicate/nonmonotonic time')
        previous = t
        vals = [b[x] for x in ('open', 'high', 'low', 'close')]
        if any(not isinstance(v, (int, float)) or not isfinite(v) or v <= 0 for v in vals):
            raise ValueError('non-finite/nonpositive OHLC')
        if b['low'] > min(b['open'], b['close']) or b['high'] < max(b['open'], b['close']):
            raise ValueError('inconsistent OHLC')
        if 'volume' in b and (not isinstance(b['volume'], (int, float)) or
                              not isfinite(b['volume']) or b['volume'] < 0):
            raise ValueError('invalid observed volume')
    if interval is not None and interval not in TIMEFRAMES.values():
        raise ValueError('unsupported interval')


def ema(values, span):
    a = 2 / (span + 1)
    out = []
    for x in values:
        out.append(x if not out else a * x + (1 - a) * out[-1])
    return out


def atr_wilder(bars, period=10):
    out = []
    for i, b in enumerate(bars):
        prev = bars[i-1]['close'] if i else b['close']
        tr = max(b['high']-b['low'], abs(b['high']-prev), abs(b['low']-prev))
        out.append(tr if not out else ((period-1)*out[-1] + tr)/period)
    return out


def make_features(bars):
    """Every index i depends on bars[:i+1], never future bars."""
    check_bars(bars)
    close = [b['close'] for b in bars]
    diff = [0.] + [close[i]-close[i-1] for i in range(1, len(bars))]
    em = {p: ema(close, p) for p in (20, 30, 35, 40, 45, 50, 60, 200)}
    a10 = atr_wilder(bars, 10)
    last_hi = last_lo = None
    features = []
    depth = 7
    for i, b in enumerate(bars):
        j = i - depth
        # Confirm pivot only after all 7 right-side bars have closed.
        if j >= depth:
            segment = bars[j-depth:i+1]
            if all(bars[j]['high'] > r['high'] for k,r in enumerate(segment) if k != depth):
                last_hi = (bars[j]['high'], j)
            if all(bars[j]['low'] < r['low'] for k,r in enumerate(segment) if k != depth):
                last_lo = (bars[j]['low'], j)
        p = diff[max(0, i-49):i+1]
        sd = pstdev(p) if len(p) >= 50 else 0.
        z = (diff[i]-mean(p))/sd if sd > 1e-12 else 0.
        span = b['high']-b['low']
        qke_up = i >= 5 and b['close']>b['open'] and close[i]>close[i-5] and span>a10[i] and span>0 and (b['close']-b['low'])/span>=.7
        qke_dn = i >= 5 and b['close']<b['open'] and close[i]<close[i-5] and span>a10[i] and span>0 and (b['high']-b['close'])/span>=.7
        stack_up = all(em[x][i] > em[y][i] for x,y in zip((30,35,40,45,50),(35,40,45,50,60)))
        stack_dn = all(em[x][i] < em[y][i] for x,y in zip((30,35,40,45,50),(35,40,45,50,60)))
        bos_up = (i >= WARMUP and last_hi is not None and close[i] > last_hi[0] and
                  close[i-1] <= last_hi[0] and z > .5)
        bos_dn = (i >= WARMUP and last_lo is not None and close[i] < last_lo[0] and
                  close[i-1] >= last_lo[0] and z < -.5)
        hh = max(x['high'] for x in bars[max(0, i-20):i]) if i else b['high']
        ll = min(x['low'] for x in bars[max(0, i-20):i]) if i else b['low']
        features.append(dict(atr=a10[i], z=z, hi=last_hi, lo=last_lo,
                             bos_up=bos_up, bos_dn=bos_dn, qke_up=qke_up,
                             qke_dn=qke_dn, stack_up=stack_up, stack_dn=stack_dn,
                             trend_up=em[50][i]>em[200][i], trend_dn=em[50][i]<em[200][i],
                             range_hi=hh, range_lo=ll, range_width=hh-ll))
    return features


def signals(bars, feats):
    """Conservative research interpretations. A signal at i enters at i+1 open."""
    if len(bars) != len(feats):
        raise ValueError('features mismatch')
    out = {name: [0]*len(bars) for name in BOTS}
    blocks = []
    cooldown = {name: -999 for name in BOTS}
    for i in range(WARMUP, len(bars)):
        b, f = bars[i], feats[i]
        atr = f['atr']
        if atr <= 0: continue
        def emit(name, side):
            if i - cooldown[name] >= 5:
                out[name][i] = side
                cooldown[name] = i
        if f['bos_up'] and f['stack_up'] and f['qke_up']:
            emit('BOS_DTC_QKE', 1)
        elif f['bos_dn'] and f['stack_dn'] and f['qke_dn']:
            emit('BOS_DTC_QKE', -1)
        # AutoRange idea: prior 20 closed bars are relatively compressed;
        # current close breaks beyond the prior bounds + ATR buffer.
        if 1.5*atr <= f['range_width'] <= 4.5*atr:
            if b['close'] > f['range_hi'] + .15*atr and f['stack_up'] and f['qke_up']:
                emit('RANGE_DTC_QKE', 1)
            elif b['close'] < f['range_lo'] - .15*atr and f['stack_dn'] and f['qke_dn']:
                emit('RANGE_DTC_QKE', -1)
        # Market Structure Dynamics: locate actual opposite candle, never default to current.
        if f['bos_up'] or f['bos_dn']:
            side = 1 if f['bos_up'] else -1
            for j in range(i-1, max(-1, i-11), -1):
                c = bars[j]
                if (side == 1 and c['close'] < c['open']) or (side == -1 and c['close'] > c['open']):
                    blocks.append(dict(side=side, top=c['high'], bottom=c['low'], born=i, expires=i+64))
                    break
        new_blocks = []
        for zone in blocks:
            if i > zone['expires']: continue
            # Must wait at least one completed bar after BOS; invalidate on close beyond distal edge.
            if zone['born'] < i:
                if (zone['side'] == 1 and b['close'] < zone['bottom']) or (zone['side'] == -1 and b['close'] > zone['top']):
                    continue
                touch = b['low'] <= zone['top'] and b['high'] >= zone['bottom']
                mid = (zone['top']+zone['bottom'])/2
                good = ((zone['side'] == 1 and b['close']>mid and b['close']>b['open'] and f['trend_up']) or
                        (zone['side'] == -1 and b['close']<mid and b['close']<b['open'] and f['trend_dn']))
                if touch and good:
                    emit('OB_RETEST', zone['side'])
                    continue  # zone used only once
            new_blocks.append(zone)
        blocks = new_blocks[-30:]
        # Monster Arrows inspiration: stop hunt of a previously confirmed pivot,
        # reversal candle close reclaims the pivot. No retroactive pivot entry.
        if f['lo'] and f['lo'][1] < i-1 and b['low'] < f['lo'][0] and b['close'] > f['lo'][0] and b['close']>b['open']:
            emit('SWEEP_REVERSAL', 1)
        elif f['hi'] and f['hi'][1] < i-1 and b['high'] > f['hi'][0] and b['close'] < f['hi'][0] and b['close']<b['open']:
            emit('SWEEP_REVERSAL', -1)
    return out


def replay(bars, signal, feats, *, cost_bps=14., start=None, end=None, capital=5000., interval=900):
    """Next-bar open entry; adverse gap fills; same-bar stop wins ties; costs on exit.

    Notional cap 1x and risk budget <=0.75% current equity. OOS window resets
    positions and equity. Mark open position to market at window end.
    """
    if cost_bps < 0 or capital <= 0 or interval not in TIMEFRAMES.values():
        raise ValueError('invalid replay parameters')
    check_bars(bars, interval)
    if len(signal)!=len(bars) or len(feats)!=len(bars): raise ValueError('bad input size')
    begin = WARMUP+1 if start is None else max(start,WARMUP+1)
    finish = len(bars) if end is None else min(end,len(bars))
    equity = capital
    peak = capital
    dd = 0.
    pos = None
    trades = []
    for i in range(begin,finish):
        b = bars[i]
        if pos:
            side = pos['side']
            hit_stop = b['low'] <= pos['stop'] if side==1 else b['high'] >= pos['stop']
            hit_target = b['high'] >= pos['target'] if side==1 else b['low'] <= pos['target']
            if hit_stop:
                # Worse gap price, not fictitious stop fill.
                fill = min(b['open'],pos['stop']) if side==1 else max(b['open'],pos['stop'])
                why = 'stop_first'
            elif hit_target:
                fill = pos['target']
                # favorable gap: cap at target, never exaggerate profit.
                why = 'target'
            elif i-pos['at']>=48:
                fill=b['close'];why='time'
            else:
                fill=None
            if fill is not None:
                gross=side*(fill-pos['entry'])*pos['qty']
                fees=pos['qty']*pos['entry']*cost_bps/10000
                pnl=gross-fees
                equity+=pnl
                trades.append({'entry_i':pos['at'], 'exit_i':i,'side':side,'entry':pos['entry'],
                               'exit':fill,'qty':pos['qty'],'gross':gross,'cost':fees,
                               'net':pnl,'exit_reason':why})
                peak=max(peak,equity)
                dd=max(dd, 100*(peak-equity)/peak)
                pos=None
        # Never enter from a signal in the current, not-yet-closed candle.
        # Never create two trades on one bar; no entries over missing bar gaps.
        if pos is None and equity>0 and signal[i-1] and bars[i]['time']-bars[i-1]['time']==interval:
            side=signal[i-1]
            a=feats[i-1]['atr']
            entry=b['open']
            dist=max(1.5*a,entry*cost_bps/10000*2.0)
            if dist>0 and isfinite(dist):
                qty=min(.0075*equity/dist, equity/entry)
                if qty>0:
                    pos={'side':side,'entry':entry,'qty':qty,'stop':entry-side*dist,
                         'target':entry+side*1.8*dist, 'at':i}
                    # Same-bar exit resolved conservatively (OHLC ambiguity).
                    stop_hit=b['low'] <= pos['stop'] if side==1 else b['high'] >= pos['stop']
                    target_hit=b['high'] >= pos['target'] if side==1 else b['low'] <= pos['target']
                    if stop_hit or target_hit:
                        fill=pos['stop'] if stop_hit else pos['target']
                        pnl=side*(fill-entry)*qty - qty*entry*cost_bps/10000
                        equity+=pnl
                        trades.append({'entry_i':i,'exit_i':i,'side':side,'entry':entry,
                                       'exit':fill,'qty':qty,'gross':side*(fill-entry)*qty,
                                       'cost':qty*entry*cost_bps/10000, 'net':pnl,
                                       'exit_reason':'stop_first' if stop_hit else 'target'})
                        peak=max(peak,equity)
                        dd=max(dd,100*(peak-equity)/peak)
                        pos=None
    mtm=0.
    if pos is not None and finish>begin:
        last=bars[finish-1]['close']
        mtm=pos['side']*(last-pos['entry'])*pos['qty']-pos['qty']*pos['entry']*cost_bps/10000
    gains=sum(max(0,t['net']) for t in trades)
    losses=-sum(min(0,t['net']) for t in trades)
    return {'trades':len(trades), 'closed_net_usd':round(equity-capital,2),
            'marked_net_usd':round(equity-capital+mtm,2),
            'open_at_end':pos is not None,'winrate_pct':round(100*sum(t['net']>0 for t in trades)/len(trades),2) if trades else None,
            'profit_factor':round(gains/losses,3) if losses else None,
            'max_realized_drawdown_pct':round(dd,3),'fees_usd':round(sum(t['cost'] for t in trades),2),
            'ledger':trades}


def research(bars, *, timeframe, costs=(14.,28.)):
    """Three chronological replay windows; earlier candles are warm-up only.
    Does not tune parameters on the validation windows. Strict paper-only label.
    """
    interval=TIMEFRAMES[timeframe]
    check_bars(bars, interval)
    f=make_features(bars)
    sig=signals(bars,f)
    first=WARMUP+1
    cut=[first]+[first+(len(bars)-first)*i//3 for i in (1,2)]+[len(bars)]
    out={'paper_only':True,'approved_for_live':False,'timeframe':timeframe,
         'source_first':bars[0]['time'],'source_last':bars[-1]['time'],
         'source_bars':len(bars),'cost_bps_roundtrip':list(costs),'strategies':{}}
    for name in BOTS:
        folds=[]
        for j in range(3):
            r={str(cost):replay(bars,sig[name],f,cost_bps=cost,start=cut[j],end=cut[j+1],interval=interval)
               for cost in costs}
            folds.append({'start':bars[cut[j]]['time'], 'end':bars[cut[j+1]-1]['time'],
                          'scenarios':{k:{n:v for n,v in d.items() if n!='ledger'} for k,d in r.items()}})
        normal,stress=(str(costs[0]),str(costs[-1]))
        total=sum(fold['scenarios'][normal]['trades'] for fold in folds)
        # Threshold only marks a RESEARCH candidate, never permission to trade.
        consistent=(total>=30 and all(fold['scenarios'][normal]['marked_net_usd']>0 and
                         fold['scenarios'][stress]['marked_net_usd']>0 and
                         fold['scenarios'][normal]['max_realized_drawdown_pct']<=10
                         for fold in folds))
        out['strategies'][name]={'closed_trades':total,
            'net_usd':round(sum(fold['scenarios'][normal]['marked_net_usd'] for fold in folds),2),
            'net_double_cost_usd':round(sum(fold['scenarios'][stress]['marked_net_usd'] for fold in folds),2),
            'retrospective_consistency_pass':consistent,'live_approved':False,'folds':folds}
    return out