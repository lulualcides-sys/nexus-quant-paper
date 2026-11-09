"""Recuperação de fechamentos Telegram pelo monitor cripto independente.

Executado somente após as janelas principais. Não cria operações nem
reconstrói resultados: chama os fechamentos existentes com marcadores próprios.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


def recover(now=None, football=None, financial=None):
    from .nexus_football_daily import deliver, load_priority_coverage
    from .scheduled_closing import report_day, run as financial_run

    now = int(now if now is not None else datetime.now(timezone.utc).timestamp())
    local = datetime.fromtimestamp(now, timezone.utc).astimezone(TZ)
    errors = []
    delivered = []

    # Cron principal 00h00; após 01h00, independente dos crons de futebol.
    if 1 <= local.hour < 12:
        day = (local.date() - timedelta(days=1)).isoformat()
        try:
            fun = football or (lambda d: deliver(d, priority_fetch=load_priority_coverage))
            if fun(day):
                delivered.append("futebol " + day)
        except Exception as exc:
            errors.append("futebol " + day + ": " + type(exc).__name__)
    # Relatório financeiro principal 19h30 nos dias úteis. Recupera na
    # mesma noite (20h+) ou manhã seguinte (até 11h59), inclusive sábado.
    if local.hour >= 20 or local.hour < 12:
        day = report_day(now)
        if datetime.strptime(day, "%Y-%m-%d").weekday() < 5:
            try:
                fun = financial or (lambda: financial_run(now=now))
                if fun():
                    delivered.append("financeiro " + day)
            except Exception as exc:
                errors.append("financeiro " + day + ": " + type(exc).__name__)
    for label in delivered:
        print("RECUPERAÇÃO TELEGRAM: enviado " + label)
    if errors:
        raise RuntimeError("Recuperação pendente; " + " / ".join(errors))
    return delivered


if __name__ == "__main__":
    recover()
