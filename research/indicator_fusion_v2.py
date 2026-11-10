"""Second-generation XAU indicator research: causal retests and channel controls.

Paper research only. New rules are competing hypotheses, not profitable robots.
Original indicator_fusion_bots and 27 existing strategy engines are unchanged.
Reuses the SAME entry fill, stop, target, risk sizing and fee assumptions as v1
so comparison measures signal changes instead of hidden execution differences.
"""
from __future__ import annotations

from math import isfinite

from research.indicator_fusion_bots import (
    WARMUP, TIMEFRAMES, make_features, signals as old_signals,
    replay, check_bars,
)

V2_BOTS = (
    'CHANNEL55_CONTROL',
    'CHANNEL55_IMPULSE',
    'CHANNEL55_RETEST',
    'BOS_LEVEL_RETEST',
    'RANGE_LEVEL_RETEST',
)


def signal_v2(bars, features):
    """Evaluate only fully closed candles and pre-existing levels.

    Every event is a current bar confirmation against a prior high/low level.
    Pending levels are recorded on the breakout bar and can only trigger on a
    later candle. Missing history/gaps are not fabricated and the replay itself
    rejects entries on a next-open gap in the feed.
    """
    check_bars(bars)
    if len(features) != len(bars):
        raise ValueError('feature count mismatch')
    result = {key: [0] * len(bars) for key in V2_BOTS}
    pending = {'CHANNEL55_RETEST': None, 'BOS_LEVEL_RETEST': None,
               'RANGE_LEVEL_RETEST': None}
    last = {key: -10_000 for key in V2_BOTS}

    def emit(name, side, i):
        # Entry rule itself emits once per qualifying event/confirmed retest.
        if i-last[name] >= 8:
            result[name][i] = side
            last[name] = i
            return True
        return False

    for i in range(WARMUP, len(bars)):
        b = bars[i]
        f = features[i]
        prev = bars[i-1]
        atr = f['atr']
        if not isfinite(atr) or atr <= 0:
            continue
        # Don't treat a highly gapped data series as a continuous setup.
        if bars[i]['time']-prev['time'] != bars[i-1]['time']-bars[i-2]['time']:
            pending = dict.fromkeys(pending)
            continue
        close, opn = b['close'], b['open']
        up, down = f['trend_up'], f['trend_dn']
        h55 = max(x['high'] for x in bars[i-55:i])
        l55 = min(x['low'] for x in bars[i-55:i])
        h55prev = max(x['high'] for x in bars[i-56:i-1])
        l55prev = min(x['low'] for x in bars[i-56:i-1])
        long55 = close > h55 and prev['close'] <= h55prev
        short55 = close < l55 and prev['close'] >= l55prev
        # Baseline control: only the channel event, for matched-policy attribution.
        if long55:
            emit('CHANNEL55_CONTROL', 1, i)
        elif short55:
            emit('CHANNEL55_CONTROL', -1, i)
        # Variant: channel breakout with only causal impulse/trend confirmation.
        # EMA50 vs EMA200 is less redundant than stacking all 6 EMAs.
        if long55 and up and f['qke_up'] and f['z'] > .5:
            emit('CHANNEL55_IMPULSE', 1, i)
        elif short55 and down and f['qke_dn'] and f['z'] < -.5:
            emit('CHANNEL55_IMPULSE', -1, i)
        # Expire old pending breakouts. Candidate retest must occur AFTER BOS.
        for key, state in list(pending.items()):
            if state is None:
                continue
            age = i-state['born']
            if age > state['max_age']:
                pending[key] = None
                continue
            direction, level = state['side'], state['level']
            # Invalidate broken structures, don't short an old bullish level.
            if (direction == 1 and close < level - .55*atr) or (direction == -1 and close > level + .55*atr):
                pending[key] = None
                continue
            if age < 1:
                continue
            # Retest must touch the old structure on this bar and close back in
            # the breakout direction with a meaningful candle body.
            touched = b['low'] <= level + .25*atr if direction == 1 else b['high'] >= level - .25*atr
            hold = (close > level + .10*atr and close > opn) if direction == 1 else (close < level - .10*atr and close < opn)
            body = abs(close-opn) >= .15*atr
            trend = up if direction == 1 else down
            if touched and hold and body and trend:
                emit(key, direction, i)
                pending[key] = None  # only one retest entry for each breakout
        # New pending states begin NOW and are not eligible until a later bar.
        if long55:
            pending['CHANNEL55_RETEST'] = {'side': 1, 'level': h55, 'born': i, 'max_age': 12}
        elif short55:
            pending['CHANNEL55_RETEST'] = {'side': -1, 'level': l55, 'born': i, 'max_age': 12}
        if f['bos_up'] and f['hi']:
            pending['BOS_LEVEL_RETEST'] = {'side': 1, 'level': f['hi'][0], 'born': i, 'max_age': 12}
        elif f['bos_dn'] and f['lo']:
            pending['BOS_LEVEL_RETEST'] = {'side': -1, 'level': f['lo'][0], 'born': i, 'max_age': 12}
        # Prior 20-bar compression. This is a candidate derived from the range
        # indicator's idea, not the proprietary full state machine.
        compressed = 1.5*atr <= f['range_width'] <= 4.5*atr
        if compressed and close > f['range_hi']+.15*atr:
            pending['RANGE_LEVEL_RETEST'] = {'side': 1, 'level': f['range_hi'], 'born': i, 'max_age': 10}
        elif compressed and close < f['range_lo']-.15*atr:
            pending['RANGE_LEVEL_RETEST'] = {'side': -1, 'level': f['range_lo'], 'born': i, 'max_age': 10}
    return result


def matched_review(bars, timeframe, costs=(0., 7., 14., 28.)):
    """Paired chronological comparison, same OHLC and identical order engine.

    Explicitly not an untouched holdout (same periods previously researched).
    The four previous bots are controls, not silently replaced by new versions.
    """
    check_bars(bars, TIMEFRAMES[timeframe])
    f = make_features(bars)
    prior = old_signals(bars, f)
    candidate = signal_v2(bars, f)
    cut0 = WARMUP + 1
    cuts = [cut0] + [cut0 + (len(bars)-cut0)*i//3 for i in (1,2)] + [len(bars)]
    all_signals = {('V1_'+k): v for k,v in prior.items()}
    all_signals.update(candidate)
    out = {'market': 'GC=F', 'timeframe': timeframe, 'paper_only': True,
           'approved_for_live': False, 'history_previously_examined': True,
           'sample_start': bars[0]['time'], 'sample_end': bars[-1]['time'],
           'source_bars': len(bars), 'risk_policy': 'same V1 fixed 1.5ATR stop 1.8R target 0.75pct 1x cap',
           'fees_bps': list(costs), 'bots': {}}
    for name, series in all_signals.items():
        folds = []
        for j in range(3):
            data = {str(fee): replay(bars, series, f, cost_bps=fee, start=cuts[j], end=cuts[j+1],
                                     interval=TIMEFRAMES[timeframe]) for fee in costs}
            folds.append({'start': bars[cuts[j]]['time'], 'end': bars[cuts[j+1]-1]['time'],
                          'scenarios': {fee: {key: val for key,val in d.items() if key != 'ledger'}
                                        for fee, d in data.items()}})
        by_cost = {str(fee): {
            'closed_trades': sum(x['scenarios'][str(fee)]['trades'] for x in folds),
            'net_usd': round(sum(x['scenarios'][str(fee)]['marked_net_usd'] for x in folds),2),
            'closed_gross_usd': round(sum(x['scenarios'][str(fee)]['closed_gross_usd'] for x in folds),2),
            'closed_fees_usd': round(sum(x['scenarios'][str(fee)]['closed_fees_usd'] for x in folds),2),
            'fold_net_usd': [x['scenarios'][str(fee)]['marked_net_usd'] for x in folds],
            'max_closed_dd_pct': max(x['scenarios'][str(fee)]['max_realized_drawdown_pct'] for x in folds),
        } for fee in costs}
        a = by_cost['14.0']; b = by_cost['28.0']
        passes = (a['closed_trades'] >= 30 and all(x > 0 for x in a['fold_net_usd']) and
                  all(x > 0 for x in b['fold_net_usd']) and a['max_closed_dd_pct'] <= 10.)
        out['bots'][name] = {'by_cost': by_cost, 'research_review_pass': passes,
                             'live_approved': False,
                             'signal_count': sum(x != 0 for x in series),
                             'folds': folds}
    return out