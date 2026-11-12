#!/usr/bin/env python3
"""XAUUSD EMA21 M15: incremental entry/runner-risk research, 2025 onward ONLY.

This module is research-only. It sends no trades. 2025 and 2026 were previously
inspected and are NOT untouched out-of-sample data. No broker bid/ask or swap.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import events, WARM, WINDOW, COST, POINT
from alpha_xau_longhold import simulate_xau
from research_oos import download, bars_for, prepared

OUT = Path(__file__).resolve().parent / "alpha_xau_entry_risk_results"
MIN_DATE = pd.Timestamp("2025-01-01", tz="UTC")
MAX_HOLD = 384
COST_GRID = (0.8, 1.2, 1.6)
PROFILES = ("RUNNER384_ORIGINAL", "ENTRY_QUALITY", "BREAKEVEN_AFTER_TP2", "ENTRY_QUALITY_BE")


def qualified_entry(frame, i, side, risk):
    """Predeclared entry guard, using only closed signal candle i + known entry open.

    No volume or session proxy, no look-ahead. Risk is assessed on next OPEN,
    which is exactly when this entry can be accepted or rejected in production.
    """
    if i < 5:
        return False
    a = float(frame.atr.iloc[i])
    f = float(frame.fema.iloc[i])
    s = float(frame.sema.iloc[i])
    past = float(frame.fema.iloc[i-5])
    bar_range = float(frame.high.iloc[i] - frame.low.iloc[i])
    return bool(np.isfinite([a, f, s, past, risk, bar_range]).all()
        and a > 0 and
        side*(f-s) >= 0.25*a and
        side*(f-past) >= 0.12*a and
        0.25*a <= risk <= 2.40*a and
        bar_range <= 2.5*a)


def simulate_profile(frame, signals, first, last, profile):
    """Run the frozen 384-bar runner; optionally gate entry or protect last 1/3.

    TP1 at 1R and TP2 at 1.5R, each one third. Final third remains until SL or
    cap. Breakeven stop moves only on candle AFTER TP2, with gap-aware fills.
    For intrabar ambiguity, stop always wins. No position overlap, 1-bar
    cooldown, same 384-bar right-end embargo as frozen comparison.
    """
    if profile not in PROFILES or not 0 <= first < last <= len(frame):
        raise ValueError("invalid profile or window")
    op = frame.open.to_numpy(dtype=float)
    hi = frame.high.to_numpy(dtype=float)
    lo = frame.low.to_numpy(dtype=float)
    cl = frame.close.to_numpy(dtype=float)
    use_gate = profile in ("ENTRY_QUALITY", "ENTRY_QUALITY_BE")
    use_be = profile in ("BREAKEVEN_AFTER_TP2", "ENTRY_QUALITY_BE")
    prev_end = first-1
    out = []
    for i, side, source_stop, quality in signals:
        if i < first or i + MAX_HOLD + 1 >= last:
            continue
        entrybar = i+1
        if entrybar <= prev_end+1:
            continue
        entry = float(op[entrybar])
        risk = float(side*(entry-source_stop))
        if not np.isfinite(risk) or risk <= 0:
            continue
        if use_gate and not qualified_entry(frame, i, side, risk):
            continue
        stop = entry-side*risk
        targets = [entry+side*risk, entry+side*1.5*risk]
        remain, filled_tps, gross = 1., 0, 0.
        be_pending = False
        reason = "TIME"
        end = entrybar+MAX_HOLD
        for j in range(entrybar,entrybar+MAX_HOLD+1):
            if be_pending:
                # Can be tightened at the next OPEN; never widen initial SL.
                stop = max(stop, entry) if side>0 else min(stop, entry)
                be_pending = False
            stopped = (lo[j] <= stop if side>0 else hi[j] >= stop)
            if stopped:
                fill = min(op[j], stop) if side>0 else max(op[j],stop)
                gross += remain*side*(fill-entry)
                reason = "SL_AFTER_TP2" if use_be and filled_tps==2 else "SL"
                end = j
                break
            for k in range(filled_tps,2):
                hit = (hi[j] >= targets[k] if side>0 else lo[j] <= targets[k])
                if not hit:
                    break
                gross += (1./3)*side*(targets[k]-entry)
                remain -= 1./3
                filled_tps = k+1
            if use_be and filled_tps==2:
                be_pending = True
            if j==entrybar+MAX_HOLD:
                gross += remain*side*(cl[j]-entry)
                reason, end = "TIME", j
                break
        out.append(dict(signal=i, entry=entrybar, exit=end, side=int(side),
            quality=float(quality), gross_pts=gross/POINT, net_pts=(gross-COST)/POINT,
            stopped_at_be=(reason=="SL_AFTER_TP2"), reason=reason))
        prev_end=end
    return out


def metrics(trades, cost_usd_oz=COST):
    if not trades:
        return dict(N=0,gross_pts=0.,net_pts=0.,PF=None,win_pct=None,mdd_pts=None,
                    avg_net_pts=None,avg_hold_bars=None)
    gross = np.array([t["gross_pts"] for t in trades], dtype=float)
    net = gross-cost_usd_oz/POINT
    gain = float(net[net>0].sum())
    loss = float(-net[net<0].sum())
    curve = np.r_[0.,np.cumsum(net)]
    return dict(N=len(trades),gross_pts=round(float(gross.sum()),1),
        net_pts=round(float(net.sum()),1),
        PF=round(gain/loss,3) if loss else None,
        win_pct=round(float(np.mean(net>0)*100),2),
        mdd_pts=round(float((np.maximum.accumulate(curve)-curve).max()),1),
        avg_net_pts=round(float(net.mean()),1),
        avg_hold_bars=round(float(np.mean([t["exit"]-t["entry"] for t in trades])),1))


def checked_window(frame, signals, first, last):
    frozen = simulate_xau(frame, signals, first, last, MAX_HOLD, runner=True)
    clone = simulate_profile(frame, signals, first, last, "RUNNER384_ORIGINAL")
    if len(frozen) != len(clone):
        raise AssertionError("baseline clone has a different number of trades")
    for a,b in zip(frozen, clone):
        if any(a[key] != b[key] for key in ("entry","exit","side")):
            raise AssertionError("baseline clone changed entry, exit or side")
        if not np.isclose(a["gross_pts"], b["gross_pts"], rtol=0, atol=1e-6):
            raise AssertionError("baseline clone changed gross P&L")
    return clone


def replay(raw, label):
    if raw.empty or raw.index.min() < MIN_DATE:
        # Stronger than a silent slice: refuse an accidental pre-2025 feed.
        raise ValueError(f"out-of-scope input dates: {label}")
    frame = prepared(bars_for(raw,15))
    if frame.empty or frame.index.min() < MIN_DATE:
        raise ValueError(f"invalid M15 date scope: {label}")
    signals = events(frame, "EMA21_PULLBACK")
    windows = (len(frame)-WARM)//WINDOW
    if windows < 1:
        raise ValueError(f"no complete 10k M15 window for {label}")
    data = []
    for w in range(windows):
        first = WARM + w*WINDOW
        last = first + WINDOW
        base = checked_window(frame,signals,first,last)
        for model in PROFILES:
            trades = base if model=="RUNNER384_ORIGINAL" else simulate_profile(
                frame,signals,first,last,model)
            row = dict(dataset=label,window=w,model=model,
                first=str(frame.index[first]),last=str(frame.index[last-1]),
                costs={str(c):metrics(trades,c) for c in COST_GRID},
                be_stops=sum(x["stopped_at_be"] for x in trades))
            data.append(row)
            print("XAU_ENTRY_RESULT",json.dumps(dict(dataset=label,window=w,
                  model=model,base_cost=row["costs"]["0.8"],
                  stress_1_2=row["costs"]["1.2"],be_stops=row["be_stops"])),
                  flush=True)
    return dict(dataset=label,m15_bars=len(frame),windows=windows,rows=data)


def comparison(rows):
    """No post-hoc 'winner' claim: compare to fixed baseline in each date block."""
    out = {}
    keys = sorted({(r["dataset"],r["window"]) for r in rows})
    for profile in PROFILES[1:]:
        paired = []
        for dataset, w in keys:
            base = next(r for r in rows if (r["dataset"],r["window"],r["model"]) ==
                        (dataset,w,"RUNNER384_ORIGINAL"))
            candidate = next(r for r in rows if (r["dataset"],r["window"],r["model"]) ==
                        (dataset,w,profile))
            a = base["costs"]["0.8"];b = candidate["costs"]["0.8"]
            if a["mdd_pts"] is None or b["mdd_pts"] is None:
                continue
            paired.append(dict(dataset=dataset,window=w,
                net_delta=round(b["net_pts"]-a["net_pts"],1),
                mdd_delta=round(b["mdd_pts"]-a["mdd_pts"],1),
                N=b["N"],
                stress_net=candidate["costs"]["1.2"]["net_pts"]))
        out[profile] = dict(blocks=paired,beats_all_blocks=bool(paired) and
            len(paired)==len(keys) and all(
                p["net_delta"]>0 and p["mdd_delta"]<=0 and p["N"]>=80 and
                p["stress_net"]>0 for p in paired))
    return out


def main():
    from points10k_2025 import source
    raw25,_ = source()
    raw26 = download()
    if raw26.index.min() < MIN_DATE or raw25.index.min() < MIN_DATE:
        raise ValueError("year 2025 lower-bound violation")
    results = dict(symbol="XAUUSD",timeframe="M15",
        minimum_date="2025-01-01T00:00:00Z",frozen_original=True,
        profiles=PROFILES,cost_grid_usd_oz=COST_GRID,
        point_assumption=POINT,first_two_tps_R=[1,1.5],
        max_hold_bars=MAX_HOLD,
        warnings=[
           "Research-only OHLC; no MT5 broker-tick validation, bid/ask, swap or realistic slippage.",
           "2025 and 2026 were seen in earlier tests; results are exploratory not untouched OOS.",
           "Costs are fixed, hypothetical USD per ounce; actual broker symbols may differ.",
           "Drawdown on CLOSED trades only; intratrade exposure may be higher."],
        cases=[replay(raw25,"2025"),replay(raw26,"2026")])
    rows=[r for c in results["cases"] for r in c["rows"]]
    results["comparison"]=comparison(rows)
    results["all_blocks_better_than_original"]=[
        name for name,x in results["comparison"].items() if x["beats_all_blocks"]]
    # Even a green result remains an exploratory research candidate.
    results["approved_for_real_trading"]=False
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"RESULTADOS_2025PLUS.json").write_text(
        json.dumps(results,ensure_ascii=False,indent=2)+"\n")
    lines=["# XAUUSD EMA21 M15 — qualidade de entrada e proteção do runner",
      "", "**Pesquisa apenas; não é backtest MT5 nem promessa de rentabilidade.**",
      "", "Datas estritamente de 2025 em diante. O original foi reproduzido",
      "trade a trade antes da comparação (sem alterar regras ou snapshots).",
      "Perfis: original Runner384; qualidade de entrada EMA21/55 com inclinação",
      "e risco normalizado por ATR; breakeven apenas no candle seguinte ao TP2;",
      "e combinação das duas mudanças. SL sempre precede TPs no candle ambíguo.",
      "Custos hipotéticos 0,8 / 1,2 / 1,6 USD por onça por operação.",
      "2025 e 2026 já eram conhecidos: isto NÃO é OOS novo.", "",
      "| Janela | Modelo | Operações | Pts líquidos (0,8) | PF (0,8) | MDD pts | Pts líquidos (1,2) |",
      "|---|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        a=row["costs"]["0.8"];b=row["costs"]["1.2"]
        lines.append("| "+ " | ".join(map(str,(row["dataset"]+"-"+str(row["window"]),
            row["model"],a["N"],a["net_pts"],a["PF"],a["mdd_pts"],b["net_pts"])))+" |")
    lines+=["","## Teste de dominância nos três blocos disponíveis","",
      "Uma variante só domina o original se melhorar pontos líquidos, não",
      "piorar MDD, manter >=80 trades e continuar positiva com custo 1,2",
      "em cada bloco. São critérios descritivos predefinidos, não homologação.",
      "", "Modelos que satisfizeram: **"+
      (", ".join(results["all_blocks_better_than_original"]) or "nenhum")+"**.",
      "", "**Sem aprovação para conta real.** Requer feed/ticks e custos/swap",
      "reais e forward test com parâmetros congelados.",""]
    (OUT/"RELATORIO_2025PLUS.md").write_text("\n".join(lines))
    print("ENTRY_RISK_COMPLETE",json.dumps(dict(
        blocks=[(c["dataset"],c["windows"]) for c in results["cases"]],
        candidates=results["all_blocks_better_than_original"])),flush=True)


if __name__=="__main__":
    main()
