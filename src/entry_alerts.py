"""Prospective virtual trade event alerts with a persisted Telegram retry queue.

Reads only differences between committed paper books. Never creates trades, changes
entries/stops, or treats indicative Yahoo prices as broker executions.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUTBOX = Path("state/entry_alerts.json")
TZ = ZoneInfo("America/Sao_Paulo")


def read_book(path):
    file = Path(path)
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else None


def _time(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).astimezone(TZ).strftime("%d/%m %H:%M")


def changes(before, after, names, group):
    """Return newly observed entries/exits, including trades closed between scans."""
    if before is None or after is None:
        return []  # first run never creates retroactive notifications
    events = []
    old_books = before.get("books", {})
    for key, new in after.get("books", {}).items():
        old = old_books.get(key, {})
        name = names.get(key, key)
        old_pos = old.get("position")
        old_entries = {int(t["entry_ts"]) for t in old.get("closed", [])}
        if old_pos is not None:
            old_entries.add(int(old_pos.get("start", old_pos.get("entry_ts"))))
        old_exits = {(int(t["entry_ts"]), int(t["exit_ts"]))
                     for t in old.get("closed", [])}
        new_closed = [t for t in new.get("closed", [])
                      if (int(t["entry_ts"]), int(t["exit_ts"])) not in old_exits]
        newly_opened = []
        pos = new.get("position")
        if pos is not None:
            newly_opened.append(pos)
        newly_opened.extend(new_closed)
        for trade in newly_opened:
            entry_ts = int(trade.get("start", trade.get("entry_ts")))
            if entry_ts in old_entries:
                continue
            old_entries.add(entry_ts)
            side = "COMPRA" if trade["side"] > 0 else "VENDA"
            events.append({
                "id": f"{group}:{key}:entry:{entry_ts}",
                "ts": entry_ts,
                "line": f"🟢 ENTRADA virtual | {name} | {side} | {_time(entry_ts)} | {float(trade['entry']):.5f}",
            })
        for trade in new_closed:
            end = int(trade["exit_ts"])
            pnl = float(trade["net_usd"])
            events.append({
                "id": f"{group}:{key}:exit:{int(trade['entry_ts'])}:{end}",
                "ts": end,
                "line": f"{'✅' if pnl >= 0 else '🔴'} SAÍDA virtual | {name} | {_time(end)} | US$ {pnl:+.2f} líquido estimado",
            })
    return events


def bb_changes(before, after):
    if before is None or after is None:
        return []
    return changes({"books": {"bb20": before}},
                   {"books": {"bb20": after}},
                   {"bb20": "BB20 H1/M15 USD/CAD"}, "usdcad")


def send_pending(events, send, path=OUTBOX):
    """Persist unsuccessful alerts and retry them on the next successful run.

    A crash after Telegram accepts a message but before GitHub commits the outbox
    may cause a duplicate. Event IDs make this auditable; never claim exactly once.
    """
    path = Path(path)
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
    else:
        state = {"schema": 1, "pending": [], "sent_ids": []}
    if state.get("schema") != 1:
        raise ValueError("Estado dos alertas incompatível; não zerar silenciosamente")
    pending = state["pending"]
    seen = set(state["sent_ids"]) | {e["id"] for e in pending}
    for event in sorted(events, key=lambda e: (e["ts"], e["id"])):
        if event["id"] not in seen:
            pending.append(event)
            seen.add(event["id"])
    pending.sort(key=lambda e: (e["ts"], e["id"]))
    # Keep all pending messages, even if the provider is unavailable.
    delivered = 0
    while pending:
        batch = pending[:10]
        message = ("📈 NEXUS QUANT — ALERTAS DE OPERAÇÕES VIRTUAIS\n"
                   "⛔ Simulação com preços públicos; NÃO é ordem FBS.\n\n"
                   + "\n".join(e["line"] for e in batch))
        try:
            ok = bool(send(message))
        except Exception as exc:
            print("Telegram: alerta virtual pendente para tentativa seguinte: " + type(exc).__name__)
            break
        if not ok:
            print("Telegram: alerta virtual pendente (chat não configurado).")
            break
        state["sent_ids"].extend(e["id"] for e in batch)
        state["sent_ids"] = state["sent_ids"][-1500:]
        del pending[:len(batch)]
        delivered += len(batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Alertas virtuais: {delivered} confirmados, {len(pending)} pendentes.")
    return delivered
