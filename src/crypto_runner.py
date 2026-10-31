"""Independent 24/7 crypto paper observer; only ONE daily Telegram digest."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from src.crypto_paper import SYMBOLS, FILE, fetch_klines, process, digest, local_day
from src.runner import telegram

REPORTS = Path("reports/crypto")
MARKER = Path("state/crypto_daily_sent.json")


def run(mode="scan", now=None, get=fetch_klines, send=telegram,
        state_path=FILE, reports=REPORTS, marker=MARKER):
    now = int(time.time() if now is None else now)
    datasets = {}
    errors = {}
    for symbol in SYMBOLS:
        try:
            datasets[symbol] = get(symbol, now)
        except Exception as exc:
            errors[symbol] = str(exc)[:130]
    if not datasets:
        raise RuntimeError("Cripto: nenhum feed validado; estado anterior preservado")
    state = process(datasets, state_path)
    print("Cripto H1: %s validos; indisponiveis: %s" %
          (", ".join(datasets), ", ".join(errors) or "nenhum"))
    if mode != "report":
        return state
    day = local_day(now)
    seen = json.loads(marker.read_text(encoding="utf8")) if marker.exists() else {}
    if seen.get("day") == day:
        return state
    message = digest(state, day)
    reports.mkdir(parents=True, exist_ok=True)
    (reports / (day + ".txt")).write_text(message + "\n", encoding="utf8")
    if send(message):
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"day": day}, indent=2) + "\n", encoding="utf8")
    return state


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("scan", "report"), default="scan")
    args = p.parse_args()
    try:
        run(mode=args.mode)
    except Exception as exc:
        print("CRIPTO: SEM DADOS FABRICADOS: " + str(exc), file=sys.stderr)
        sys.exit(1)
