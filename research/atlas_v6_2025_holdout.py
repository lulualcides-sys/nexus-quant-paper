"""ATLAS V6 falsification on earlier, unused WINFUT M5 history (research only).

2025 WINFUT is a CONTINUOUS Profit series: contract mapping and roll gaps
are undocumented, so it cannot prove fills, WINV26 M1 or Tracker equivalence.
The noon veto was chosen using 2026 data, never recalibrated on this input.
2025 is a retrospective backward holdout for that filter, NOT forward testing.
"""
from __future__ import annotations

import csv
import json
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from research.atlas_v5_loss_ranking import (
    _fetch_pinned, _month_cut, _coverage, RESEARCH_CAPITAL_BRL
)
from research.atlas_v6_noon_probe import PROBES, probe_signal
from research.win_price_data import _number, _tick_check, read_win_csv, local_day, win_session
from research import atlas_win_backtest as simulator

SOURCE_REPO = "wesleyzilva/tradetech"
SOURCE_COMMIT = "0e6f28524cfcda661ad042f1cbacb2948db614f7"
SOURCE_PATH = "dados/candles/2024-2025/WINFUT_F_0_5min.csv"
SOURCE_BLOB = "bc064fbc3d2b4ab22fe84561e19d46b9b1da6d1d"
SOURCE_URL = "https://raw.githubusercontent.com/" + SOURCE_REPO + "/" + SOURCE_COMMIT + "/" + SOURCE_PATH

# Fixed before reading the outcome. These months were not used to choose V6.
PERIODS = (
    ("2025-09", "2025-09-01", "2025-10-01"),
    ("2025-10", "2025-10-01", "2025-11-01"),
    ("2025-11", "2025-11-01", "2025-12-01"),
    ("2025-12", "2025-12-01", "2026-01-01"),
)
TICKS = (0, 1, 2)
FEE_BRL = 4.0
MIN_ACTIVE_DAYS = 14
MIN_BARS_PER_ACTIVE_DAY = 65

def parse_profit_continuous(raw):
    """Return normalized OHLC + CONTRACT QUANTITY; never financial volume.

    Do not infer the underlying expiry from the continuous WINFUT symbol.
    A duplicate timestamp, foreign symbol or off-grid price is fatal.
    """
    rows = []
    with Path(raw).open("r", encoding="latin-1", newline="") as stream:
        for line_number, fields in enumerate(csv.reader(stream, delimiter=";"), 1):
            if not fields or not any(x.strip() for x in fields):
                continue
            if fields[0].strip().lower() == "ativo":
                continue
            if len(fields) != 9 or fields[0].strip().upper() != "WINFUT":
                raise ValueError(f"line {line_number}: exact WINFUT and nine fields required")
            try:
                stamp = datetime.strptime(
                    fields[1].strip() + " " + fields[2].strip(),
                    "%d/%m/%Y %H:%M:%S"
                )
                o, h, lo, c = [_number(x) for x in fields[3:7]]
                financial_volume, qty = _number(fields[7]), _number(fields[8])
            except (ValueError, IndexError) as exc:
                raise ValueError(f"line {line_number}: malformed Profit candle") from exc
            if stamp.weekday() > 4:
                raise ValueError(f"line {line_number}: weekend timestamp")
            for price in (o, h, lo, c):
                _tick_check(price)
            if lo > min(o, c) or h < max(o, c) or lo > h:
                raise ValueError(f"line {line_number}: impossible OHLC")
            if financial_volume <= 0 or qty <= 0 or int(qty) != qty:
                raise ValueError(f"line {line_number}: invalid volume/quantity")
            if stamp.minute % 5 or stamp.second:
                raise ValueError(f"line {line_number}: not native aligned M5")
            rows.append((stamp, o, h, lo, c, int(qty)))
    rows.sort(key=lambda x: x[0])
    if any(rows[i][0] == rows[i-1][0] for i in range(1, len(rows))):
        raise ValueError("Duplicate M5 timestamps")
    return rows

def audit_tick_grid(raw):
    """Count native trade-tick violations before ANY financial simulation.

    Replacing bad prices with rounded prices would manufacture market data.
    In that case decline the source and keep the prior simulator unchanged.
    """
    failures = []
    n_rows = n_bad_rows = n_bad_prices = 0
    with Path(raw).open("r", encoding="latin-1", newline="") as stream:
        for line_number, fields in enumerate(csv.reader(stream, delimiter=";"), 1):
            if not fields or fields[0].strip().lower() == "ativo":
                continue
            n_rows += 1
            if len(fields) != 9 or fields[0].strip().upper() != "WINFUT":
                raise ValueError(f"source schema/symbol mismatch at {line_number}")
            invalid = []
            for column, value in zip(("open", "high", "low", "close"), fields[3:7]):
                price = _number(value)
                if price <= 0 or abs(price / 5 - round(price / 5)) > 1e-7:
                    invalid.append((column, price))
            if invalid:
                n_bad_rows += 1
                n_bad_prices += len(invalid)
                if len(failures) < 12:
                    failures.append({
                        "line": line_number, "market_date": fields[1],
                        "market_time": fields[2], "off_tick": invalid
                    })
    return {
        "scanned_rows": n_rows, "off_tick_rows": n_bad_rows,
        "off_tick_price_fields": n_bad_prices, "first_12": failures,
        "rejected": bool(n_bad_rows)
    }

def normalize(raw, normalized):
    rows = parse_profit_continuous(raw)
    if len(rows) < 10000:
        raise ValueError("Insufficient history for independent four-month test")
    with Path(normalized).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["Ativo", "Data", "Hora", "Open", "High", "Low", "Close", "Volume"])
        for stamp, o, h, lo, c, qty in rows:
            writer.writerow([
                "WINFUT", stamp.strftime("%d/%m/%Y"), stamp.strftime("%H:%M:%S"),
                int(o), int(h), int(lo), int(c), qty
            ])
    series = read_win_csv(normalized, expected_symbol="WINFUT")
    if series["timeframe_seconds"] != 300 or len(series["bars"]) != len(rows):
        raise ValueError("Unexpected frequency, missing or duplicated bars")
    if not any(local_day(b["time"]).startswith("2025-12") for b in series["bars"]):
        raise ValueError("December 2025 missing from source")
    return series

def _summarize(sim):
    ledger = sim.get("closed_ledger", [])
    return {
        "status": sim["status"],
        "signals_are_not_fills": True,
        "entries": sim["entries"],
        "closed": sim["closed"],
        "unfilled_or_cancelled": sim["unfilled_or_cancelled"],
        "wins": sim["wins"],
        "winrate_pct": sim["winrate_pct"],
        "net_brl": sim["net_brl"],
        "profit_factor": sim["profit_factor"],
        "max_realized_drawdown_pct": sim["max_realized_drawdown_pct"],
        "uncertain_same_bar_exits": sim["uncertain_same_bar_exits"],
        "open_at_end": sim["open_at_end"],
        "pending_at_end": sim["pending_at_end"],
        "estimated_transaction_cost_brl": round(sum(t["estimated_cost_brl"] for t in ledger), 2),
        "gross_before_cost_brl": round(sum(t["net_brl"] + t["estimated_cost_brl"] for t in ledger), 2),
    }

def run_study(series, provenance):
    bars = series["bars"]
    out = {
        "research_only": True,
        "not_tracker": True,
        "not_winv26": True,
        "contract_identity_unknown": True,
        "rollover_gaps_possible": True,
        "no_broker_fills_or_orderbook": True,
        "v6_filter_frozen_prior_to_this_evaluation": True,
        "backward_holdout_relative_to_2026_tuning": True,
        "prospective_forward_test": False,
        "approved_for_paper_or_live": False,
        "source": provenance,
        "source_ticker": series["symbol"],
        "native_timeframe": "M5",
        "capital_reset_per_month_brl": RESEARCH_CAPITAL_BRL,
        "risk_fraction": simulator.RISK,
        "max_contracts": simulator.MAX_CONTRACTS,
        "fee_brl_per_contract_roundtrip": FEE_BRL,
        "slippage_ticks_per_side": list(TICKS),
        "models_predeclared": list(PROBES),
        "periods_predeclared": [name for name, _, _ in PERIODS],
        "periods": {},
    }
    for name, start, end in PERIODS:
        quality = _coverage(bars, start, end)
        cut = _month_cut(bars, start, end)
        period = {"coverage": quality, "status": "INSUFFICIENT_DATA", "models": {}}
        out["periods"][name] = period
        if cut is None or quality["days_with_65_m5"] < MIN_ACTIVE_DAYS:
            continue
        eligible = [start <= local_day(bar["time"]) < end for bar in cut]
        period["status"] = "RESEARCH_BACKTEST_CONTINUOUS_UNVERIFIED_ROLL"
        for variant in PROBES:
            signals = [probe_signal(cut, i, variant) if i >= 100 and eligible[i] else 0
                       for i in range(len(cut))]
            with patch.object(simulator, "CAPITAL_BRL", RESEARCH_CAPITAL_BRL):
                with patch.object(simulator, "candidate",
                                  side_effect=lambda b, i, v, seq=signals: seq[i]):
                    tests = {
                        str(k): _summarize(simulator.simulate(
                            cut, timeframe="M5", variant="original",
                            fee_brl=FEE_BRL, slip_ticks=k))
                        for k in TICKS
                    }
            period["models"][variant] = {
                "signals": sum(1 for x in signals if x != 0),
                "cost_scenarios": tests
            }
    out["aggregate_stress"] = {}
    for variant in PROBES:
        valid = [period["models"][variant]["cost_scenarios"]["2"]
                 for period in out["periods"].values()
                 if period["status"].startswith("RESEARCH_BACKTEST")]
        out["aggregate_stress"][variant] = {
            "nmonths": len(valid),
            "closed": sum(x["closed"] for x in valid),
            "net_brl": round(sum(x["net_brl"] for x in valid), 2),
            "positive_months": sum(x["net_brl"] > 0 for x in valid),
            "estimated_cost_brl": round(sum(x["estimated_transaction_cost_brl"] for x in valid), 2),
            "uncertain_same_bar_exits": sum(x["uncertain_same_bar_exits"] for x in valid)
        }
    # No qualification while continuous contract/roll mapping and independent
    # execution evidence are unknown. A positive retrospective number is NOT a gate.
    out["decision"] = "REJECT_PROMOTION_MISSING_CONTRACT_AND_FILL_AUDIT"
    return out

def render(result):
    lines = [
        "# ATLAS V6: validação retrospectiva em período de 2025 não usado no filtro",
        "",
        "**NÃO é Tracker nem WINV26. WINFUT é série contínua com mudanças de vencimento não identificadas por linha.**",
        "Hipótese de veto 12h–15h fixada usando dados de 2026, confrontada com setembro a dezembro de 2025.",
        "Holdout retrospectivo anterior ao período de ajuste; não é forward prospectivo nem auditoria de execução.",
        "Banca virtual de R$30.000 reiniciada por mês, risco de 0,75%, até 3 contratos, R$4/contrato ida/volta e 0, 1 e 2 ticks por lado.",
        "Uma seta gera uma ordem pendente; nem toda seta é preenchimento ou operação encerrada.",
        "",
        "| Mês | Modelo | Sinais | Entradas (2t) | Encerradas (2t) | Líquido 0t | Líquido 1t | Líquido 2t | DD realizado 2t % |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for month, entry in result["periods"].items():
        if entry["status"] == "INSUFFICIENT_DATA":
            lines.append(f"| {month} | SEM COBERTURA SUFICIENTE | — | — | — | — | — | — | — |")
            continue
        for model in PROBES:
            m = entry["models"][model]
            sims = m["cost_scenarios"]
            lines.append(f"| {month} | {model} | {m['signals']} | {sims['2']['entries']} | "
                         f"{sims['2']['closed']} | {sims['0']['net_brl']} | "
                         f"{sims['1']['net_brl']} | {sims['2']['net_brl']} | "
                         f"{sims['2']['max_realized_drawdown_pct']} |")
    lines += ["", "## Agregado descritivo com 2 ticks por lado",
              "| Modelo | Meses avaliados | Operações fechadas | Meses positivos | Líquido R$ |",
              "|---|---:|---:|---:|---:|"]
    for model, a in result["aggregate_stress"].items():
        lines.append(f"| {model} | {a['nmonths']} | {a['closed']} | "
                     f"{a['positive_months']} | {a['net_brl']} |")
    lines += [
        "", "## Regra de decisão",
        "- Rejeitar promoção mesmo se lucro retrospectivo: contrato subjacente e rolagem de WINFUT não auditados.",
        "- Esta série é independente da janela de ajuste de V6, mas anterior a ela; não constitui forward/walk-forward.",
        "- Não comparar números deste contrato contínuo diretamente com as supostas 27 setas Tracker em WINV26 M1.",
        "- Intrabar: simulador privilegia stop em barra ambígua; ainda não possui book, fila ou fills de corretora.",
        "- Faltam série WINV26 M1 de 13/10/2026 e vídeo contínuo das setas com timestamp de mercado.",
        "- Nenhum código operacional, risco ou outro robô foi alterado.", ""
    ]
    return "\n".join(lines)

def main():
    with tempfile.TemporaryDirectory() as td:
        raw, normalized = Path(td)/"source.csv", Path(td)/"normalized.csv"
        provenance = _fetch_pinned(SOURCE_URL, SOURCE_BLOB, raw)
        grid = audit_tick_grid(raw)
        if grid["rejected"]:
            result = {
                "status": "SOURCE_REJECTED_OFF_TICK_CONTINUOUS_WIN",
                "source": provenance, "tick_grid_audit": grid,
                "source_ticker": "WINFUT", "periods_attempted": [x[0] for x in PERIODS],
                "contract_identity_unknown": True, "winv26_m1_verified": False,
                "financial_backtest_executed": False, "net_brl": None,
                "winrate_pct": None, "tracker_matched": False,
                "approved_for_paper_or_live": False,
                "decision": "REJECT_SOURCE_NO_PRICE_CORRECTION"
            }
            report = (
                "# ATLAS V6: fonte de 2025 REJEITADA por preços fora da grade WIN\n\n"
                "Backtest financeiro NÃO executado. Sem interpolar, arredondar nem trocar por candle sintético.\n\n"
                f"Arquivo {SOURCE_PATH}, Git blob verificado {SOURCE_BLOB}.\n\n"
                f"Linhas examinadas: {grid['scanned_rows']}; linhas com pelo menos um preço inválido: "
                f"{grid['off_tick_rows']}; campos de preço inválidos: {grid['off_tick_price_fields']}.\n\n"
                f"Primeiros exemplos (data/hora do mercado): {json.dumps(grid['first_12'], ensure_ascii=False)}\n\n"
                "WINFUT contínuo não identifica vencimento por candle e possui gaps de rolagem; "
                "sem reconstrução e auditoria do contrato real, rejeitar promoção.\n"
            )
        else:
            imported = normalize(raw, normalized)
            result = run_study(imported, provenance)
            report = render(result)
    folder = Path("research/results")
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"atlas_v6_2025_backward_holdout.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (folder/"atlas_v6_2025_backward_holdout.md").write_text(report+"\n", encoding="utf-8")
    print("ATLAS_2025_BACKWARD_HOLDOUT_START", flush=True)
    print(report, flush=True)
    print("ATLAS_2025_BACKWARD_HOLDOUT_END", flush=True)

if __name__ == "__main__":
    main()
