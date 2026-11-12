"""XAUUSD M5 V5 isolated exit research: no new signal filters, no broker orders.

V5 tests *exit management* against V4's exact four-signal portfolio baseline.
Inputs are already-observed historical data. Never label retrospective results OOS.
No parameter search is performed inside this module, and no market order exists.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import floor, isfinite

from research.indicator_fusion_v3_frequency import (
    WARMUP, NAMES, features_and_signals, portfolio as original_portfolio, check_bars,
)

TF_SECONDS = 300
DISABLED_SIGNAL = 'MOMENTUM_2BAR'  # V4 post-hoc removal, not independent confirmation.
EXIT_POLICIES = ('fixed_v4', 'breakeven_1p5R', 'close_trail_2R')
DEFAULT_PARAMETERS = dict(
    interval=TF_SECONDS, max_hold=36, stop_atr=3., target_r=3.,
    risk_frac=.0075, min_qty_step_oz=1.,
)


def ablated_signals(bars):
    atr, signals = features_and_signals(bars)
    return atr, {name: (values if name != DISABLED_SIGNAL else [0] * len(values))
                 for name, values in signals.items()}


def _month(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m')


def _close_trade(p, b, idx, price, reason, *, fee_bps, fee_per_oz, cost_mode, slip_per_side):
    qty = p['qty']
    gross = p['side'] * (price - p['entry']) * qty
    if cost_mode == 'observed_spread_max':
        spread_out = b.get('max_spread')
        if not isinstance(spread_out, (float, int)) or not isfinite(spread_out) or spread_out < 0:
            raise ValueError('missing valid observed exit maximum spread')
        # Diagnostic upper-stress proxy: highest quote spread within each
        # candle. These maxima are NOT exact executable spreads at fill.
        all_in_spread = .5 * (p['entry_spread_max'] + spread_out) + 2 * slip_per_side
        fees = qty * (p['entry'] * fee_bps / 10000 + all_in_spread)
    else:
        fees = qty * (p['entry'] * fee_bps / 10000 + fee_per_oz)
    return {'bot': p['bot'], 'entry_i': p['entry_i'], 'exit_i': idx,
            'entry_time': p['entry_time'], 'exit_time': b['time'],
            'entry': p['entry'], 'exit': price, 'side': p['side'], 'qty': qty,
            'reason': reason, 'net': gross - fees, 'gross': gross,
            'cost': fees, 'initial_risk_distance': p['dist']}


def _trailing_stop(position, close_price, observed_atr, policy):
    """Compute new stop using the just-CLOSED candle, effective NEXT candle.

    No high/low of a future candle is used to adjust a stop. Returns a price,
    never loosening existing stop or placing a long stop above close (vice versa).
    """
    p = position
    side = p['side']; entry = p['entry']; dist = p['dist']
    progress = side * (close_price - entry)
    candidate = p['stop']
    if policy == 'breakeven_1p5R' and progress >= 1.5 * dist:
        target = entry + side * .10 * dist
        candidate = max(candidate, target) if side == 1 else min(candidate, target)
    elif policy == 'close_trail_2R' and progress >= 2.0 * dist:
        p['best_close'] = (max(p['best_close'], close_price) if side == 1
                           else min(p['best_close'], close_price))
        r_floor = entry + side * .25 * dist
        ch = p['best_close'] - side * 1.25 * observed_atr
        target = max(ch, r_floor) if side == 1 else min(ch, r_floor)
        candidate = max(candidate, target) if side == 1 else min(candidate, target)
    if not isfinite(candidate):
        raise ValueError('invalid trailing stop')
    # Never declare a filled stop at this just-closed candle or manufacture
    # profit using a stop on the wrong side of the present close.
    buffer = .05 * observed_atr
    if side == 1:
        candidate = min(candidate, close_price - buffer)
        return max(p['stop'], candidate)
    candidate = max(candidate, close_price + buffer)
    return min(p['stop'], candidate)


def replay_v5(bars, atr, signals, *, policy='fixed_v4', fee_bps=0., fee_per_oz=.61,
              start=None, end=None, capital=5000., interval=300, max_hold=36,
              stop_atr=3., target_r=3., risk_frac=.0075, min_qty_step_oz=1.,
              cost_mode='fixed', slip_per_side=0., daily_flat_hour_utc=None):
    """One-symbol event-driven paper simulator with fixed signal priority.

    Fixed policy + fixed fee + no daily flat matches V3 exactly at trade level,
    verified by regression tests on real and synthetic candles. Other policies
    share entry logic and stop-first ambiguity handling.

    When daily_flat_hour_utc=20, positions are closed at 20:55 UTC; this is
    a specified *session comparison protocol* for sampled Dukascopy data,
    NOT a proposed live trading session. No entries on its last candle.
    """
    if policy not in EXIT_POLICIES or cost_mode not in ('fixed', 'observed_spread_max'):
        raise ValueError('unsupported policy or cost mode')
    if (fee_bps < 0 or fee_per_oz < 0 or slip_per_side < 0 or capital <= 0 or
        max_hold < 1 or stop_atr <= 0 or target_r <= 0 or not 0 < risk_frac <= 1 or
        interval != TF_SECONDS or min_qty_step_oz <= 0 or
        (daily_flat_hour_utc is not None and not 0 <= daily_flat_hour_utc <= 23)):
        raise ValueError('invalid simulator settings')
    check_bars(bars, interval)
    if set(signals) != set(NAMES) or any(len(v) != len(bars) for v in signals.values()):
        raise ValueError('bad signal lengths')
    if len(atr) != len(bars) or any(not isfinite(v) or v < 0 for v in atr):
        raise ValueError('bad ATR series')
    first = max(WARMUP + 1, start if start is not None else WARMUP + 1)
    last = min(end if end is not None else len(bars), len(bars))
    if last <= first: raise ValueError('empty window')
    if cost_mode == 'observed_spread_max':
        for b in bars[first - 1:last]:
            v = b.get('max_spread')
            if not isinstance(v, (int, float)) or not isfinite(v) or v < 0:
                raise ValueError('observed cost mode requires every candle spread')

    equity = capital; peak = capital; dd = 0.; position = None
    ledger = []; entered = Counter(); candidates = Counter(); rejected_min_lot = 0
    for i in range(first, last):
        b = bars[i]
        dt = datetime.fromtimestamp(b['time'], timezone.utc)
        session_end = daily_flat_hour_utc is not None and dt.hour == daily_flat_hour_utc and dt.minute == 55
        occupied_at_open = position is not None
        if occupied_at_open:
            p = position; side = p['side']; price = None; reason = None
            if (side == 1 and b['open'] <= p['stop']) or (side == -1 and b['open'] >= p['stop']):
                price = b['open']; reason = 'stop_gap'
            elif (side == 1 and b['open'] >= p['target']) or (side == -1 and b['open'] <= p['target']):
                price = p['target']; reason = 'target_gap'
            elif (side == 1 and b['low'] <= p['stop']) or (side == -1 and b['high'] >= p['stop']):
                price = p['stop']; reason = 'stop'
            elif (side == 1 and b['high'] >= p['target']) or (side == -1 and b['low'] <= p['target']):
                price = p['target']; reason = 'target'
            elif session_end:
                price = b['close']; reason = 'session_flat'
            elif i - p['entry_i'] >= max_hold:
                price = b['close']; reason = 'time'
            if price is not None:
                tr = _close_trade(p, b, i, price, reason, fee_bps=fee_bps,
                                  fee_per_oz=fee_per_oz, cost_mode=cost_mode,
                                  slip_per_side=slip_per_side)
                ledger.append(tr); equity += tr['net']; peak = max(peak, equity)
                dd = max(dd, 100 * (peak - equity) / peak)
                position = None
        choices = [(name, signals[name][i-1]) for name in NAMES if signals[name][i-1]]
        for name, _ in choices: candidates[name] += 1
        if occupied_at_open:  # do not travel back to earlier OPEN after intrabar exit
            if position is not None:
                position['stop'] = _trailing_stop(position, b['close'], atr[i], policy)
            continue
        if session_end or b['time'] - bars[i-1]['time'] != interval or not choices or equity <= 0:
            continue
        name, side = choices[0]
        entry = b['open']; dist = stop_atr * atr[i-1]
        if dist <= 0 or not isfinite(dist): continue
        qty = min(equity * risk_frac / dist, equity / entry)
        qty = floor((qty + 1e-9) / min_qty_step_oz) * min_qty_step_oz
        if qty <= 0:
            rejected_min_lot += 1
            continue
        entry_spread = b.get('max_spread', 0.)
        p = {'bot': name, 'side': side, 'entry': entry, 'qty': qty, 'entry_i': i,
             'entry_time': b['time'], 'stop': entry - side * dist,
             'target': entry + side * target_r * dist, 'dist': dist,
             'best_close': entry, 'entry_spread_max': entry_spread}
        position = p
        entered[name] += 1
        if (side == 1 and b['low'] <= p['stop']) or (side == -1 and b['high'] >= p['stop']):
            price = p['stop']; reason = 'stop'
        elif (side == 1 and b['high'] >= p['target']) or (side == -1 and b['low'] <= p['target']):
            price = p['target']; reason = 'target'
        else:
            price = None; reason = None
        if price is not None:
            tr = _close_trade(p, b, i, price, reason, fee_bps=fee_bps,
                              fee_per_oz=fee_per_oz, cost_mode=cost_mode,
                              slip_per_side=slip_per_side)
            ledger.append(tr); equity += tr['net']; peak = max(peak, equity)
            dd = max(dd, 100 * (peak - equity) / peak)
            position = None
        elif session_end:
            # Already prohibited entry above; defensive assertion.
            raise AssertionError('new position entered on flat candle')
        else:
            p['stop'] = _trailing_stop(p, b['close'], atr[i], policy)
    floating = 0.
    if position is not None:
        price = bars[last-1]['close']; floating = position['side'] * (price - position['entry']) * position['qty']
        if cost_mode == 'observed_spread_max':
            floating -= position['qty'] * (.5 * (position['entry_spread_max'] + bars[last-1]['max_spread']) + 2 * slip_per_side + position['entry'] * fee_bps / 10000)
        else:
            floating -= position['qty'] * (fee_per_oz + position['entry'] * fee_bps / 10000)
    gains = sum(t['net'] for t in ledger if t['net'] > 0)
    losses = -sum(t['net'] for t in ledger if t['net'] < 0)
    span_days = (bars[last-1]['time'] - bars[first]['time']) / 86400
    return {'policy': policy, 'source_first': bars[first]['time'], 'source_last': bars[last-1]['time'],
            'closed_trades': len(ledger), 'net_usd': round(equity-capital+floating, 2),
            'closed_net_usd': round(equity-capital, 2), 'gross_usd': round(sum(t['gross'] for t in ledger), 2),
            'fees_usd': round(sum(t['cost'] for t in ledger), 2),
            'wins': sum(t['net'] > 0 for t in ledger),
            'profit_factor': round(gains/losses, 3) if losses else None,
            'max_realized_drawdown_pct': round(dd, 3), 'open_at_end': position is not None,
            'trades_per_30_calendar_days_estimate': round(len(ledger)*30/span_days, 1) if span_days else None,
            'utc_month_counts': dict(Counter(_month(t['entry_time']) for t in ledger)),
            'entry_by_signal': dict(entered), 'signals_by_type': dict(candidates),
            'min_lot_rejections': rejected_min_lot,
            'ledger': ledger}


def paired_runs(bars, *, dataset_name='Yahoo GC=F', partial_sessions=False):
    """Predeclared three exit policies, one group of unfiltered signals.

    Requires same sampled candle timestamps for the three policies. Dukascopy
    partial sessions (12:00–20:55) are NOT comparable to full-day Yahoo rate.
    """
    check_bars(bars, TF_SECONDS)
    atr, sig = ablated_signals(bars)
    results = {'dataset': dataset_name, 'partial_sessions': partial_sessions,
               'source_bars': len(bars),'paper_only': True, 'approved_for_live': False,
               'historical_data_previously_viewed': True,
               'experimental_policies': EXIT_POLICIES, 'by_policy': {}}
    # Compare same exact 3 windows (reset virtual capital) per data source.
    first = WARMUP+1
    cuts = [first]+[first+(len(bars)-first)*i//3 for i in (1,2)]+[len(bars)]
    for policy in EXIT_POLICIES:
        row = {'scenarios': {},'folds': []}
        configs = {'spread_0p61':dict(cost_mode='fixed',fee_per_oz=.61),
                   'spread_1p81':dict(cost_mode='fixed',fee_per_oz=1.81),
                   'spread_3p31':dict(cost_mode='fixed',fee_per_oz=3.31),
                   'stress_14bps':dict(cost_mode='fixed',fee_bps=14,fee_per_oz=0.)}
        if partial_sessions and all('max_spread' in b for b in bars):
            configs['observed_max_spread_plus_0p15_each_side'] = dict(cost_mode='observed_spread_max',fee_per_oz=0.,slip_per_side=.15)
        for key, kwargs in configs.items():
            rr = replay_v5(bars,atr,sig,policy=policy,
                           daily_flat_hour_utc=20 if partial_sessions else None,
                           **DEFAULT_PARAMETERS, **kwargs)
            row['scenarios'][key] = {k:v for k,v in rr.items() if k!='ledger'}
        for j in range(3):
            d = {'first':bars[cuts[j]]['time'],'last':bars[cuts[j+1]-1]['time']}
            for key in ('spread_0p61','spread_1p81'):
                rr = replay_v5(bars,atr,sig,policy=policy,
                               daily_flat_hour_utc=20 if partial_sessions else None,
                               start=cuts[j],end=cuts[j+1],
                               **DEFAULT_PARAMETERS,**configs[key])
                d[key] = {'trades':rr['closed_trades'],'net':rr['net_usd']}
            row['folds'].append(d)
        n=row['scenarios']['spread_0p61']['closed_trades']
        row['retrospective_consistency_pass']=(n>=30 and
             all(x['spread_0p61']['net']>0 and x['spread_1p81']['net']>0 for x in row['folds']) and
             row['scenarios']['spread_1p81']['max_realized_drawdown_pct']<=10)
        row['approved_for_live'] = False
        results['by_policy'][policy] = row
    return results