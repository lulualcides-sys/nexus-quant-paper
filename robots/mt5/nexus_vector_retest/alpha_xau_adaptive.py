#!/usr/bin/env python3
"""XAUUSD M15 EMA21 pullback — experimental trend-conditional position management.

Research-only OHLC proxy. This module does not send orders and is not an MT5
Strategy Tester report. All trend/stop decisions use CLOSED bars only.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_xau_longhold import simulate_xau, stats
from points10k import events, POINT, COST, WINDOW, WARM
from research_oos import download, bars_for, prepared

BASE = Path(__file__).resolve().parent
RESULTS = BASE / "alpha_xau_adaptive_results"
DATA_ROOT = Path("thirdparty/gold")
MAX_HOLD = 384
BASE_HOLD = 48
DATA_PIN = "b2cfdc571ffac9eff9f2132ea6946da559d29af2"

def trend_masks(df):
    """Return directional (micro, strong) boolean arrays using bar t or earlier.

    Compare EMA slope and price action in ATR units, without future pivots.
    Parameters precommitted before any 2024 holdout evaluation.
    """
    close = df.close.to_numpy(dtype=float)
    fast = df.fema.to_numpy(dtype=float)
    slow = df.sema.to_numpy(dtype=float)
    atr = df.atr.to_numpy(dtype=float)
    n = len(df)
    micro = np.zeros((2, n), dtype=bool)  # row 0 long, row 1 short
    strong = np.zeros((2, n), dtype=bool)
    for t in range(6, n):
        a = atr[t]
        if not np.isfinite(a) or a <= 0 or not np.all(np.isfinite(
                [close[t], fast[t], slow[t], fast[t-3], fast[t-5],
                 close[t-3], close[t-2], close[t-1]])):
            continue
        for idx, side in enumerate((1, -1)):
            ema_aligned = side * (fast[t] - slow[t]) >= 0
            slope3 = side * (fast[t] - fast[t-3])
            slope5 = side * (fast[t] - fast[t-5])
            movement = side * (close[t] - close[t-3])
            higher_closes = sum(side * (close[k] - close[k-1]) > 0
                                for k in (t-2, t-1, t))
            near_fast = side * (close[t] - fast[t]) >= -0.15 * a
            micro[idx, t] = (ema_aligned and near_fast and
                             slope3 >= 0.16 * a and movement >= 0.35 * a and
                             higher_closes >= 2)
            strong[idx, t] = (near_fast and
                              side * (fast[t] - slow[t]) >= 0.75 * a and
                              slope5 >= 0.25 * a)
    return micro, strong

def simulate_adaptive(df, signals, first, last, masks=None):
    """Apply fixed exits, extend ONLY the final third while closed-bar trend survives.

    Partial TP1 = 1R and TP2 = 1.5R. TP3 = 2R whenever a runner is not
    authorized by the previous closed bar. At most 48 candles for a trade
    without a trend-authorized runner; absolute emergency time cap 384 bars.
    Active runner closes at next OPEN after 2 closed non-trend bars. A trailing
    stop tightens ONLY after TP2 with closed EMA21 +/- 1.2 ATR, no looser than
    breakeven, and never loosens. SL takes precedence over TPs within a bar.
    """
    if not 0 <= first < last <= len(df):
        raise ValueError("invalid window")
    if masks is None:
        masks = trend_masks(df)
    micro, strong = masks
    op = df.open.to_numpy(dtype=float)
    hi = df.high.to_numpy(dtype=float)
    lo = df.low.to_numpy(dtype=float)
    cl = df.close.to_numpy(dtype=float)
    fema = df.fema.to_numpy(dtype=float)
    atr = df.atr.to_numpy(dtype=float)
    prev_end = first-1
    trades = []
    for i, side, source_stop, _ in signals:
        # Same right-tail embargo as fixed runner 384, for fair comparisons.
        if i < first or i + MAX_HOLD + 1 >= last:
            continue
        entrybar = i + 1
        if entrybar <= prev_end + 1:
            continue
        entry = float(op[entrybar])
        risk = float(side * (entry-source_stop))
        if not np.isfinite(risk) or risk <= 0:
            continue
        stop = float(source_stop)
        targets = [entry + side * risk * multiple for multiple in (1, 1.5, 2)]
        remain, taken, gross = 1., 0, 0.
        runner = False
        ever_runner = False
        end = entrybar + MAX_HOLD
        reason = "TIME_MAX"
        extended = False
        for j in range(entrybar, entrybar + MAX_HOLD + 1):
            prev = j - 1
            idx = 0 if side > 0 else 1
            trend_now = bool(micro[idx, prev] or strong[idx, prev])
            trend_prior = bool(micro[idx, prev-1] or strong[idx, prev-1]) if prev > 0 else False

            # Manage on the OPEN after observing the fully closed previous bar.
            if taken >= 2 and trend_now:
                runner = True
                ever_runner = True

            if runner and not trend_now and not trend_prior:
                gross += remain * side * (op[j] - entry)
                reason, end = "TREND_LOST", j
                break

            # Without runner confirmation, do not keep the position past 48 bars.
            if j >= entrybar + BASE_HOLD and not runner:
                gross += remain * side * (op[j] - entry)
                reason, end = "TIME_BASE", j
                break

            if j == entrybar + MAX_HOLD:
                gross += remain * side * (op[j] - entry)
                reason, end = "TIME_MAX", j
                extended = j > entrybar + BASE_HOLD
                break

            # Tighten stop at next open; preceding closed bar data ONLY.
            if runner and taken >= 2 and np.isfinite(fema[prev]) and np.isfinite(atr[prev]):
                proposed = fema[prev] - side * 1.2 * atr[prev]
                if side > 0:
                    stop = max(stop, entry, proposed)
                else:
                    stop = min(stop, entry, proposed)

            # Gap-aware stop fill, prior to target checks in ambiguous OHLC.
            hit_stop = lo[j] <= stop if side > 0 else hi[j] >= stop
            if hit_stop:
                fill = min(op[j], stop) if side > 0 else max(op[j], stop)
                gross += remain * side * (fill - entry)
                reason, end = "SL", j
                extended = j > entrybar + BASE_HOLD
                break

            # If trend exists at prior close, reserve the last third as runner
            # even when TP1/TP2 and TP3 would be hit inside the SAME OHLC bar.
            maximum_target = 2 if (runner or trend_now) else 3
            for k in range(taken, maximum_target):
                target_hit = hi[j] >= targets[k] if side > 0 else lo[j] <= targets[k]
                if not target_hit:
                    break
                fraction = remain if k == 2 else 1./3
                gross += fraction * side * (targets[k] - entry)
                remain -= fraction
                taken = k+1
            if taken >= 2 and trend_now:
                runner = True
                ever_runner = True
            if taken == 3:
                reason, end = "TP3", j
                extended = j > entrybar + BASE_HOLD
                break
        if remain < 0:
            raise AssertionError("over-allocated partials")
        trades.append(dict(signal=i, entry=entrybar, exit=end,
                           side=int(side), duration_bars=end-entrybar,
                           extended=bool(extended or end-entrybar>BASE_HOLD),
                           ever_runner=ever_runner, reason=reason,
                           gross_pts=gross/POINT, net_pts=(gross-COST)/POINT))
        prev_end = end
    return trades

def extended_stats(trades):
    row = stats(trades)
    if trades:
        row.update(extended_n=sum(x["extended"] for x in trades),
                   trend_runner_n=sum(x["ever_runner"] for x in trades),
                   median_bars=float(np.median([x["duration_bars"] for x in trades])),
                   reasons={reason:sum(t["reason"]==reason for t in trades)
                            for reason in ("SL","TP3","TIME_BASE","TIME_MAX","TREND_LOST")})
    else:
        row.update(extended_n=0,trend_runner_n=0,median_bars=None,reasons={})
    return row

def load_independent_year(year):
    """Read pinned public daily source with per-file integrity and time checks."""
    paths = sorted(DATA_ROOT.glob(f"XAUUSD/1m/{year}/*/*.csv"))
    if len(paths) < 240:
        raise RuntimeError(f"insufficient {year} daily files: {len(paths)}")
    fragments, digests = [], []
    for path in paths:
        payload = path.read_bytes()
        digests.append([path.relative_to(DATA_ROOT).as_posix(),
                        hashlib.sha256(payload).hexdigest()])
        d = pd.read_csv(path, usecols=["timestamp","datetime_utc",
                "open","high","low","close","volume"])
        stamp = pd.to_datetime(d["datetime_utc"], utc=True, errors="raise")
        if not ((stamp.astype("int64")//1000000) ==
                pd.to_numeric(d["timestamp"],errors="raise")).all():
            raise ValueError(f"timestamp mismatch: {path}")
        d["datetime"] = stamp
        fragments.append(d[["datetime","open","high","low","close","volume"]])
    raw = pd.concat(fragments,ignore_index=True)
    if raw.datetime.duplicated().any():
        raise ValueError("duplicate timestamp")
    raw = raw.sort_values("datetime").set_index("datetime")
    for col in ("open","high","low","close","volume"):
        raw[col] = pd.to_numeric(raw[col],errors="raise")
    valid = (raw.high >= raw[["open","close","low"]].max(axis=1)) & (
        raw.low <= raw[["open","close","high"]].min(axis=1)) & (raw.volume >= 0)
    if not valid.all():
        raise ValueError("invalid OHLCV")
    return raw, digests

def replay(raw, name):
    data = prepared(bars_for(raw,15))
    signals = events(data, "EMA21_PULLBACK")
    masks = trend_masks(data)
    count = (len(data)-WARM)//WINDOW
    if count < 1:
        raise ValueError(f"no full 10k windows for {name}")
    rows = []
    for window in range(count):
        first = WARM + window*WINDOW
        last = first + WINDOW
        alternatives = [
            ("BASE_48", simulate_xau(data,signals,first,last,48,runner=False)),
            ("FIXED_RUNNER_384", simulate_xau(data,signals,first,last,384,runner=True)),
            ("ADAPTIVE_TREND", simulate_adaptive(data,signals,first,last,masks))]
        for model, trades in alternatives:
            row = dict(source=name,window=window,model=model,
                start=str(data.index[first]),end=str(data.index[last-1]),
                **extended_stats(trades))
            rows.append(row)
            print("XAU_ADAPTIVE_RESULT",json.dumps(row,ensure_ascii=False),flush=True)
    return dict(source=name,m15_bars=len(data),windows=count,rows=rows)

def main():
    from points10k_2025 import source as year_2025
    raw26 = download()
    raw25, _ = year_2025()
    raw24, manifest24 = load_independent_year("2024")
    result = dict(symbol="XAUUSD",timeframe="M15",status="RESEARCH_ONLY",
        pinned_2024_commit=DATA_PIN, sha256_2024_manifest=manifest24,
        point_assumed=POINT,cost_usd_per_ounce_roundtrip_assumed=COST,
        max_hold=MAX_HOLD,base_hold=BASE_HOLD,
        warnings=["2026 and 2025 have already been inspected/used for candidate selection.",
          "2024 is an additional holdout; results cannot confirm live profitability.",
          "OHLC stop-first proxy, no broker tick, swap, spread variation or slippage.",
          "2024 and 2025 come from the same secondary source; not broker-independent."],
        cases=[replay(raw26,"2026_PREVIOUSLY_USED"),
               replay(raw25,"2025_PREVIOUSLY_USED"),
               replay(raw24,"2024_HOLDOUT")])
    RESULTS.mkdir(exist_ok=True,parents=True)
    (RESULTS/"results.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    lines=["# XAUUSD M15 — adaptive EMA21 trend-conditioned exits", "",
       "**Research only. No MT5 Strategy Tester/broker execution.**", "",
       "Entries = frozen EMA21 Pullback. TP1 1R; TP2 1.5R; TP3 2R unless",
       "micro/strong trend verified on previous CLOSED bar. Extend only final",
       "third while trend persists, tighten stop after TP2, exit at next open after",
       "two completed bars without trend. Base horizon 48 bars; hard cap 384.",
       "Point assumed 0.01 and fixed roundtrip 0.80 USD/oz; swap not modeled.",
       "Same 384-bar right-tail embargo for fair horizons, no overlap.", "",
       "| Dataset | Window | Variant | Trades | Net estimated pts | PF | MDD pts | Extended |",
       "|---|---:|---|---:|---:|---:|---:|---:|"]
    for case in result["cases"]:
        for r in case["rows"]:
            lines.append("| "+ " | ".join(str(r[k]) for k in (
                "source","window","model","N","net_pts","PF","mdd_pts","extended_n"))+" |")
    lines+=["","2024 was not used to choose thresholds; parameters were fixed first.",
            "Drawdown is computed on closed-trade equity, not intratrade equity.",
            "Do not approve live trading without independent real-tick MT5 forward tests.",""]
    (RESULTS/"REPORT.md").write_text("\n".join(lines))
    print("RESEARCH_COMPLETE",len(result["cases"]),flush=True)

if __name__=="__main__":
    main()
