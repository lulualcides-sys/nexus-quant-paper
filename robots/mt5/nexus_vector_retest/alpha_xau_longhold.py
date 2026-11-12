#!/usr/bin/env python3
"""Research ONLY: fixed XAUUSD M15 EMA21 pullback signals, inverted/long-hold.
Never an MT5 tester claim; broker tick, bid/ask and real slippage unavailable.
"""
import json
from pathlib import Path
import numpy as np
from points10k import events, POINT, COST, WINDOW, WARM
from research_oos import download, bars_for, prepared

HOLDS=(48,96,192,384)  # M15 bars: 12h / 24h / 48h / 96h of candles
MAX_HOLD=max(HOLDS)
OUTPUT=Path(__file__).resolve().parent/"alpha_xau_longhold_results"

def simulate_xau(df,signals,first,last,hold,reverse=False,runner=False):
    """Common entry population across all hold tests, never overlap positions."""
    if hold not in HOLDS or not 0<=first<last<=len(df):raise ValueError("window/hold")
    op=df.open.to_numpy(dtype=float);hi=df.high.to_numpy(dtype=float)
    lo=df.low.to_numpy(dtype=float);cl=df.close.to_numpy(dtype=float)
    prev_end=first-1;trades=[]
    for i,src_side,src_stop,quality in signals:
        # Same 384-bar right-tail embargo for EVERY variant, avoiding truncated holds.
        if i<first or i+MAX_HOLD+1>=last:continue
        entrybar=i+1
        if entrybar<=prev_end+1:continue
        entry=op[entrybar];risk=float(src_side*(entry-src_stop))
        if not np.isfinite(risk) or risk<=0:continue
        side=-src_side if reverse else src_side
        # Critical: reverse a TRADE, not P&L. A reversed SL must move above/below entry.
        stop=entry-side*risk
        targets=[entry+side*risk*k for k in (1.0,1.5,2.0)]
        remain=1.0;take=0;gross=0.;reason="TIME";end=entrybar+hold
        for j in range(entrybar,entrybar+hold+1):
            stopped=lo[j]<=stop if side>0 else hi[j]>=stop
            if stopped:
                price=min(op[j],stop) if side>0 else max(op[j],stop)
                gross+=remain*side*(price-entry)
                reason="SL";end=j;break
            # OHLC is uncertain: SL is processed first on every ambiguous candle.
            max_tp=2 if runner else 3
            for k in range(take,max_tp):
                hit=hi[j]>=targets[k] if side>0 else lo[j]<=targets[k]
                if not hit:break
                fraction=remain if k==2 else 1/3
                gross+=fraction*side*(targets[k]-entry)
                remain-=fraction;take=k+1
            if not runner and take==3:
                reason="TP3";end=j;break
            if j==entrybar+hold:
                gross+=remain*side*(cl[j]-entry)
                break
        trades.append({"entry":entrybar,"exit":end,"side":int(side),
                       "reason":reason,"gross_pts":gross/POINT,
                       "net_pts":(gross-COST)/POINT})
        prev_end=end
    return trades

def stats(trades):
    if not trades:return dict(N=0,gross_pts=0,net_pts=0,win_pct=None,PF=None,mdd_pts=None)
    net=np.array([t["net_pts"] for t in trades])
    pos=float(net[net>0].sum());neg=float(-net[net<0].sum())
    equity=np.r_[0.,np.cumsum(net)]
    return dict(N=len(trades),gross_pts=round(sum(t["gross_pts"] for t in trades),1),
        net_pts=round(float(net.sum()),1),win_pct=round(100*float(np.mean(net>0)),2),
        PF=round(pos/neg,3) if neg else None,
        mdd_pts=round(float((np.maximum.accumulate(equity)-equity).max()),1))

def replay(raw,name):
    data=prepared(bars_for(raw,15))
    signals=events(data,"EMA21_PULLBACK") # frozen 2026 signal rules
    n=(len(data)-WARM)//WINDOW
    if n<1:raise ValueError("No 10k-bar window for "+name)
    rows=[]
    for w in range(n):
        first=WARM+w*WINDOW;last=first+WINDOW
        for reverse in (False,True):
            for runner in (False,True):
                for hold in HOLDS:
                    deals=simulate_xau(data,signals,first,last,hold,reverse,runner)
                    rows.append(dict(source=name,window=w,from_date=str(data.index[first]),
                        to_date=str(data.index[last-1]),
                        direction="INVERTED" if reverse else "ORIGINAL",
                        exit_rule="RUNNER" if runner else "THREE_TPS",
                        hold_m15=hold,**stats(deals)))
    return dict(source=name,m1_bars=len(raw),m15_bars=len(data),windows_10k=n,rows=rows)

def main():
    from points10k_2025 import source as get_independent_2025
    raw2026=download()      # SHA256 checked in research_oos.py
    raw2025,_=get_independent_2025() # pinned separate 2025 public repository
    result={"symbol":"XAUUSD","timeframe":"M15","not_mt5_execution":True,
        "point_assumption":POINT,"roundtrip_cost_estimate_usd_oz":COST,
        "frozen_signal":"EMA21_PULLBACK from points10k.py",
        "fixed_tp_r":[1,1.5,2],
        "runner":"1/3 at 1R, 1/3 at 1.5R, last 1/3 at SL or max hold",
        "common_tail_exclusion_bars":MAX_HOLD,
        "data_model":"OHLC stop-first proxy, next-bar-open, no broker ticks",
        "cases":[replay(raw2026,"2026_EXPLORATORY"),
                 replay(raw2025,"2025_INDEPENDENT_AUDIT")]}
    OUTPUT.mkdir(exist_ok=True,parents=True)
    (OUTPUT/"RESULTADOS_XAU_LONGHOLD.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    lines=["# XAUUSD M15 — long hold, runner and signal inversion","",
        "**NOT an MT5/broker backtest. NOT approved for real-money trading.**","",
        "Original 41,641 gross points / 463 trades were from the UNMODIFIED 48-bar script.",
        "This new comparison uses a common 384-bar embargo at the end of every",
        "10k-candle window; therefore its number of trades is intentionally DIFFERENT.",
        "Costs: hypothetical 0.80 USD/oz per round trip. POINT=0.01 assumed.",
        "No tuning with 2025 independent periods.","",
        "| Source | Window | Direction | Exit | Hold M15 | N | Gross points | Net estimated points | PF | MDD |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|"]
    for c in result["cases"]:
        for r in c["rows"]:
            keys=("source","window","direction","exit_rule","hold_m15",
                "N","gross_pts","net_pts","PF","mdd_pts")
            lines.append("| "+" | ".join(str(r[k]) for k in keys)+" |")
            print("XAU_RESULT",json.dumps({k:r[k] for k in (
                "source","window","direction","exit_rule","hold_m15","N","net_pts","PF")}),flush=True)
    lines+=["","Validate broker real ticks, dynamic spread, fees and slippage before deployment."]
    (OUTPUT/"RELATORIO_XAU_LONGHOLD.md").write_text("\n".join(lines)+"\n")

if __name__=="__main__":main()
