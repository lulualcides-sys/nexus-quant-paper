"""Compare 27 actual paper engines on precisely identical immutable Yahoo OHLC.

No strategy changes, broker trading, state mutation or hindsight filtering.
The frozen tape is a GitHub Actions artifact captured *before* the fix;
both historical code revisions receive that exact same immutable tape.

Usage:
  python research/compare_frozen_27.py replay baseline tape.json.gz output.json
  python research/compare_frozen_27.py replay corrected tape.json.gz output.json
  python research/compare_frozen_27.py compare baseline.json corrected.json report.md report.json
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


def fingerprint(rows):
    return hashlib.sha256(json.dumps(
        rows, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def read_tape(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        d = json.load(handle)
    if d.get("schema") != 1 or d.get("paper_only") is not True:
        raise ValueError("Invalid tape format")
    prices = d["datasets"]
    if not prices or set(prices) != set(d["price_data"]):
        raise ValueError("Incomplete frozen tape")
    for market, rows in prices.items():
        if fingerprint(rows) != d["price_data"][market]["sha256"]:
            raise ValueError(f"SHA256 mismatch for {market}")
    return d


def replay(checkout, tape_path, output):
    root = Path(checkout).resolve()
    if not (root / "research/backtest_27.py").is_file():
        raise ValueError("Not a Nexus Quant checkout")
    tape = read_tape(tape_path)
    # Import code from *only* this specified historical checkout.
    sys.path.insert(0, str(root))
    from research import backtest_27 as bt
    if (bt.HIST_START != tape["hist_start"]
            or bt.HIST_END != tape["hist_end_exclusive"]):
        raise ValueError("The old and new engines must use identical time bounds")
    datasets = {k: copy.deepcopy(v) for k, v in tape["datasets"].items()
                if k != "USDCAD_M15"}
    m15 = copy.deepcopy(tape["datasets"].get("USDCAD_M15"))
    result = bt.run(datasets=datasets, m15rows=m15, obtain=False, stress=True)
    if result["analyzed"] != 27 or result["unavailable"] != 0:
        raise RuntimeError("Incomplete 27-bot replay: abort comparison")
    for market, meta in tape["price_data"].items():
        if result["price_data"][market]["sha256"] != meta["sha256"]:
            raise RuntimeError(f"Unexpected price mutation: {market}")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("FROZEN_PAIRED_REPLAY", root.name, output, flush=True)


def compare(baseline_path, corrected_path, report_md, report_json):
    base = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    new = json.loads(Path(corrected_path).read_text(encoding="utf-8"))
    assert base["planned"] == new["planned"] == 27
    assert base["analyzed"] == new["analyzed"] == 27
    if base["price_data"] != new["price_data"]:
        raise ValueError("Different OHLC input hashes; invalid A/B comparison")
    if set(base["robots"]) != set(new["robots"]):
        raise ValueError("Different robot universes")
    rows = []
    for key, old in base["robots"].items():
        after = new["robots"][key]
        if (old["status"] != "historical_replay_not_validated"
                or after["status"] != "historical_replay_not_validated"):
            raise ValueError(f"Unavailable robot {key}")
        rows.append({
            "robot": key, "group": old["group"],
            "before_usd": old["net_realized_usd"],
            "after_usd": after["net_realized_usd"],
            "delta_usd": round(after["net_realized_usd"] - old["net_realized_usd"], 2),
            "before_trades": old["closed_trades"],
            "after_trades": after["closed_trades"],
            "before_2x_cost_usd": old["double_cost_net_usd"],
            "after_2x_cost_usd": after["double_cost_net_usd"],
            "before_pf": old["profit_factor"],
            "after_pf": after["profit_factor"],
            "before_dd_realized_pct": old["closed_only_drawdown_pct"],
            "after_dd_realized_pct": after["closed_only_drawdown_pct"],
        })
    groups = []
    for group in sorted({r["group"] for r in rows}):
        selected = [r for r in rows if r["group"] == group]
        groups.append({
            "group": group, "robots": len(selected),
            "before_usd": round(sum(r["before_usd"] for r in selected), 2),
            "after_usd": round(sum(r["after_usd"] for r in selected), 2),
            "delta_usd": round(sum(r["delta_usd"] for r in selected), 2),
            "before_trades": sum(r["before_trades"] for r in selected),
            "after_trades": sum(r["after_trades"] for r in selected),
            "before_2x_cost_usd": round(sum(r["before_2x_cost_usd"] for r in selected), 2),
            "after_2x_cost_usd": round(sum(r["after_2x_cost_usd"] for r in selected), 2),
        })
    summary = {
        "comparison": "same_candles_same_historical_window_code_change_only",
        "source": base["source"],
        "paper_only": True,
        "not_independent_out_of_sample": True,
        "not_portfolio_equity": True,
        "periods_differ_by_market": True,
        "analysis_note": ("This verifies the change in paper P&L caused by fixing "
                          "first-entry-candle exit checks. Negative delta is not "
                          "proof of worsening strategy quality: prior replay skipped "
                          "some legitimate stops/targets."),
        "price_data": base["price_data"],
        "before_total_usd": round(sum(x["before_usd"] for x in rows), 2),
        "after_total_usd": round(sum(x["after_usd"] for x in rows), 2),
        "delta_total_usd": round(sum(x["delta_usd"] for x in rows), 2),
        "before_closed": sum(x["before_trades"] for x in rows),
        "after_closed": sum(x["after_trades"] for x in rows),
        "groups": groups,
        "robots": rows,
    }
    lines = [
        "# Nexus Quant: antes vs depois (MESMOS candles — 27 robôs)",
        "",
        "Fonte: Yahoo OHLC histórico congelado em artifact com SHA-256. "
        "Simulação virtual, sem BID/ASK FBS, sem ordens reais e sem OOS independente.",
        "Períodos não idênticos entre mercados; soma de bancas independentes NÃO é carteira.",
        "",
        "| Grupo | Antes US$ | Depois US$ | Diferença US$ | Fechadas antes/depois |",
        "|---|---:|---:|---:|---:|"
    ]
    for g in groups:
        lines.append(
            f"| {g['group']} | {g['before_usd']:+.2f} | {g['after_usd']:+.2f} "
            f"| {g['delta_usd']:+.2f} | {g['before_trades']}/{g['after_trades']} |"
        )
    lines += [
        f"| **TOTAL virtual não-carteira** | **{summary['before_total_usd']:+.2f}** "
        f"| **{summary['after_total_usd']:+.2f}** "
        f"| **{summary['delta_total_usd']:+.2f}** "
        f"| **{summary['before_closed']}/{summary['after_closed']}** |",
        "", "## Todos os robôs", "",
        "| Robô | Antes US$ | Depois US$ | Delta US$ | Fechadas antes/depois |",
        "|---|---:|---:|---:|---:|"
    ]
    for row in rows:
        lines.append(
            f"| {row['robot']} | {row['before_usd']:+.2f} "
            f"| {row['after_usd']:+.2f} | {row['delta_usd']:+.2f} "
            f"| {row['before_trades']}/{row['after_trades']} |"
        )
    lines += [
        "", "## Limitações",
        "- Stop e alvo tocados no mesmo candle: o motor prefere stop, conservador.",
        "- A entrada no candle OPEN só é simulada em OHLC completo; não há ticks de corretora.",
        "- Não houve troca da estratégia nem confirmação de lucro prospectivo.",
        "- Lucro ou prejuízo agregado é exclusivamente de livros de pesquisa independentes.",
        ""
    ]
    Path(report_md).write_text("\n".join(lines), encoding="utf-8")
    Path(report_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n",
                                 encoding="utf-8")
    print("PAIRED_FROZEN_COMPARISON", json.dumps({
        "before": summary["before_total_usd"],
        "after": summary["after_total_usd"],
        "delta": summary["delta_total_usd"],
        "closed_before": summary["before_closed"],
        "closed_after": summary["after_closed"],
        "groups": groups,
    }, ensure_ascii=False), flush=True)


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "replay":
        replay(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 6 and sys.argv[1] == "compare":
        compare(*sys.argv[2:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
