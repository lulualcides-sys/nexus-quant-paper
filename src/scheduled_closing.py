"""Fechamento Telegram do Nexus Quant por snapshot auditável, sem depender de feed ao vivo.

Preserva posições e resultados; NUNCA gera entradas, saídas ou ordens.
Agendamento financeiro: 19h30 BRT, dias úteis. O GitHub pode atrasar o início.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .daily_digest import digest
from .runner import telegram

TZ = ZoneInfo("America/Sao_Paulo")
ROOT = Path(".")


def report_day(now: int) -> str:
    local = datetime.fromtimestamp(now, timezone.utc).astimezone(TZ)
    # GitHub pode atrasar o cron de sexta até depois de meia-noite local.
    # Nesses casos o relatório ainda pertence ao dia útil anterior.
    if local.hour < 12:
        return (local.date() - timedelta(days=1)).isoformat()
    return local.date().isoformat()


def read_paper(root: Path, filename: str, *, optional: bool = False):
    path = root / "state" / filename
    if not path.is_file():
        if optional:
            return None
        raise RuntimeError("Estado de simulação ausente: " + filename)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("paper_only") is not True:
        raise RuntimeError("Estado virtual não verificado: " + filename)
    return data


def compose(day: str, root: Path = ROOT, now: int | None = None) -> str:
    """Somente leitura. Nenhum preço, resultado ou operação é reconstruído."""
    gold = read_paper(root, "selected_gold_v2.json")
    lev = read_paper(root, "leveraged_gold_v1.json")
    if len(gold.get("books", {})) != 5 or len(lev.get("books", {})) != 5:
        raise RuntimeError("Fechamento exige 5+5 livros originais completos")
    mtf = read_paper(root, "bb20_mtf_usdcad_v1.json", optional=True)
    h1 = read_paper(root, "experimental_h1_v1.json", optional=True)
    momentum = read_paper(root, "momentum60_shadow_v1.json", optional=True)
    message = digest(
        day, gold, lev, datasets=None, unavailable=None,
        mtf=mtf, mtf_error="snapshot M15 ausente" if mtf is None else None,
        shadow=h1, momentum60=momentum, planned_robots=27,
    )
    w_gold, w_lev = gold.get("h4_watermark"), lev.get("h4_watermark")
    if (not isinstance(w_gold, int) or not isinstance(w_lev, int)
            or w_gold <= 0 or w_lev <= 0):
        raise RuntimeError("Watermark H4 de ouro não verificável")
    # Não mascarar divergência entre os livros nem cotação desatualizada.
    stamp = datetime.fromtimestamp(min(w_gold, w_lev), timezone.utc).astimezone(TZ)
    message += ("\n🕒 Último candle ouro H4 no estado: "
                + stamp.strftime("%d/%m %H:%M") + " BRT (snapshot, sem preço ao vivo).")
    reference_now = int(now if now is not None else datetime.now(timezone.utc).timestamp())
    if reference_now - min(w_gold, w_lev) > 12 * 3600:
        message += "\n⚠️ Dados H4 antigos: nenhuma entrada nova foi presumida após o último candle."
    if w_gold != w_lev:
        message += "\n⚠️ Livros H4 com horários diferentes; resultados preservados sem reconciliação artificial."
    if len(message) > 4000:
        raise RuntimeError("Relatório snapshot excede 4000 caracteres")
    return message


def run(*, now: int | None = None, root: Path = ROOT, send=telegram):
    now = int(now if now is not None else datetime.now(timezone.utc).timestamp())
    day = report_day(now)
    state_path = root / "state" / "market_monitor.json"
    if not state_path.exists():
        raise RuntimeError("Marcador original de relatório financeiro não existe")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("last_report_day") == day:
        print("Fechamento financeiro já confirmado para " + day + "; sem duplicação.")
        return False
    message = compose(day, root, now)
    # Persistir o registro do texto sem alterar qualquer posição.
    target = root / "reports" / (day + ".txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(message + "\n", encoding="utf-8")
    if not send(message):
        raise RuntimeError("Telegram não confirmou o fechamento: preservar marcador para recuperação")
    state["last_report_day"] = day
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                     sort_keys=True) + "\n", encoding="utf-8")
    print("Fechamento financeiro virtual confirmado para " + day)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="Somente para testes; o cron seleciona a data local automaticamente")
    args = parser.parse_args()
    if args.day:
        raise SystemExit("Use a execução programática para datas de teste")
    run()
