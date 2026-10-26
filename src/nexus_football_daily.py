"""Encaminha o fechamento esportivo NEXUS pelo bot Telegram JÁ conectado ao Nexus Quant."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from urllib import request
from zoneinfo import ZoneInfo

from .private_chat import load_chat
from .telegram_check import api
from .nexus_football_archive import summarize

SCORE_REPO = "https://raw.githubusercontent.com/lulualcides-sys/nexus-score-gratis"
BOT = "NexusQuantAlertasBot"
TZ = ZoneInfo("America/Sao_Paulo")


def load_summary(day, opener=request.urlopen):
    url = SCORE_REPO + "/market-telegram-data/market-history/" + day + ".json"
    req = request.Request(url, headers={"User-Agent": "NexusQuantDailyFootball/1.0"})
    with opener(req, timeout=20) as response:
        raw = response.read(40 * 1024 * 1024 + 1)
    if len(raw) > 40 * 1024 * 1024:
        raise ValueError("Histórico de odds excedeu 40 MiB")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("day") != day:
        raise ValueError("Arquivo NEXUS incompatível ou com data errada")
    if data.get("schema") == 1:
        return summarize(data, day)
    if data.get("schema") != 2:
        raise ValueError("Schema de arquivo NEXUS inesperado")
    for k in ("games", "finished", "quotes_verified", "games_with_verified_odds",
              "market_families_with_verified_prices", "market_families_catalogued"):
        if not isinstance(data.get(k), int) or data[k] < 0:
            raise ValueError("Contagem inválida no NEXUS: " + k)
    if not isinstance(data.get("results"), dict) or not isinstance(data.get("bookmakers"), dict):
        raise ValueError("Estrutura de mercados NEXUS incompleta")
    return data



def load_priority_coverage(opener=request.urlopen):
    url = SCORE_REPO + "/market-telegram-data/market-history/priority-coverage.json"
    req = request.Request(url, headers={"User-Agent": "NexusQuantDailyFootball/1.2"})
    with opener(req, timeout=12) as response:
        raw = response.read(600_001)
    if len(raw) > 600_000:
        raise ValueError("Coverage report exceeds safe size")
    doc = json.loads(raw)
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        raise ValueError("Invalid priority-coverage report")
    updated = datetime.fromisoformat(str(doc.get("checked_at", "")).replace("Z","+00:00"))
    if updated.tzinfo is None:
        raise ValueError("Coverage timestamp unverified")
    # Do not present a stale report as recent data in the next midnight message.
    age = (datetime.now(timezone.utc) - updated).total_seconds()
    if not -120 <= age <= 6*3600:
        raise ValueError("Coverage report is stale")
    for key in ("important_games","verified_bookmaker_games",
                "indicative_only_games","missing_bookmaker_price_games"):
        if not isinstance(doc.get(key),int) or doc[key] < 0:
            raise ValueError("Coverage counters invalid")
    return doc


def format_football(data, coverage=None):
    """Relatório Telegram curto, em HTML nativo e sem resultados/odds inventados."""
    from html import escape

    qualified = data.get("qualified_results")
    has_qualified = (
        isinstance(qualified, dict)
        and data.get("liquidity_qualified_games", 0) > 0
    )
    results = qualified if has_qualified else data["results"]

    def outcome(key):
        return (f"{results.get(key + '_yes', 0)} sim"
                f" · {results.get(key + '_no', 0)} não")

    def name(value, limit=40):
        return escape(str(value or "")[:limit])

    try:
        display_day = datetime.strptime(data["day"], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (KeyError, TypeError, ValueError):
        display_day = name(data.get("day", "sem data"), 15)

    lines = [
        "<b>⚽ NEXUS FUTEBOL | FECHAMENTO</b>",
        f"📅 {display_day}",
        "",
        "<b>📌 Resumo do dia</b>",
        f"• <b>{data['finished']}</b> jogos encerrados"
        f" · {data['games']} no arquivo",
        f"• Odds verificadas: <b>{data['quotes_verified']}</b>"
        f" em <b>{data['games_with_verified_odds']} jogos</b>",
        f"• Liquidez ≥ R$ 3 mil comprovada: "
        f"<b>{data.get('liquidity_qualified_games', 0)} jogos</b>",
        "",
        "<b>📊 Resultados "
        + ("com liquidez comprovada" if has_qualified else "gerais")
        + "</b>",
    ]
    if not has_qualified:
        lines.append("<i>Sem comprovação de liquidez nesta amostra.</i>")

    lines.extend([
        "1X2: "
        f"Casa {results.get('1x2_home', 0)} · "
        f"Empate {results.get('1x2_draw', 0)} · "
        f"Fora {results.get('1x2_away', 0)}",
        f"Over 2.5: {outcome('over_2_5')}",
        f"Ambas marcam: {outcome('btts')}",
        f"Escanteios +9.5: {outcome('corners_9_5')}",
        f"Amarelos +4.5: {outcome('cards_4_5')}",
        f"Chutes no alvo +7.5: {outcome('sot_7_5')}",
    ])

    if isinstance(coverage, dict):
        lines.extend([
            "",
            "<b>🏆 Jogos importantes · próximas 48h</b>",
            f"• Monitorados: <b>{coverage.get('important_games', 0)}</b>"
            f" · com odds: <b>{coverage.get('verified_bookmaker_games', 0)}</b>",
            f"• Só indicativas: {coverage.get('indicative_only_games', 0)}"
            f" · sem cotação: {coverage.get('missing_bookmaker_price_games', 0)}",
        ])

        pinnacle = coverage.get("pinnacle_guest") or {}
        if (isinstance(pinnacle, dict) and pinnacle.get("status") == "checked"
                and isinstance(pinnacle.get("offers"), int)
                and pinnacle["offers"] > 0):
            lines.append(
                f"• Pinnacle pública: <b>{pinnacle['offers']}</b> odds"
                f" em {pinnacle.get('matched', 0)} jogos"
            )

        quality = coverage.get("book_quality") or {}
        if isinstance(quality, dict) and quality.get("status") == "fresh":
            complete = quality.get("complete_market_lines", 0)
            if isinstance(complete, int) and complete > 0:
                lines.append(f"• Linhas completas: {complete}")
            ft = (quality.get("families") or {}).get("match_odds") or {}
            margin = ft.get("median_overround_pct") if isinstance(ft, dict) else None
            if (isinstance(margin, (int, float)) and not isinstance(margin, bool)
                    and 0 <= margin < 100):
                lines.append(f"• Margem mediana 1X2: {margin:.2f}% <i>(não é ROI)</i>")

        official = coverage.get("official_corners_cards") or {}
        if isinstance(official, dict) and official.get("status") == "checked":
            corners = official.get("verified_corners_quotes", 0)
            cards = official.get("verified_cards_quotes", 0)
            if (isinstance(corners, int) and isinstance(cards, int)
                    and (corners > 0 or cards > 0)):
                lines.append(
                    f"• Odds de casa: escanteios {corners} · cartões {cards}"
                )

        moves = coverage.get("price_movements") or {}
        if isinstance(moves, dict) and moves.get("status") == "fresh":
            count = moves.get("selections_with_changes")
            if isinstance(count, int) and count > 0:
                lines.append(f"• Movimentos de odds: {count}")
            tops = moves.get("top_changes") or []
            if isinstance(tops, list) and tops and isinstance(tops[0], dict):
                top = tops[0]
                delta = top.get("implied_probability_change_pp")
                if (isinstance(delta, (int, float)) and not isinstance(delta, bool)
                        and abs(delta) <= 100 and top.get("home") and top.get("away")):
                    lines.extend([
                        "",
                        "<b>📈 Maior variação observada</b>",
                        f"{name(top['home'], 30)} x {name(top['away'], 30)}",
                        f"{name(top.get('market_family'), 35)}: "
                        f"{delta:+.2f} p.p. de prob. implícita",
                    ])

        missing = coverage.get("top_missing") or []
        names = []
        if isinstance(missing, list):
            for item in missing[:3]:
                if isinstance(item, dict) and item.get("home") and item.get("away"):
                    names.append(f"• {name(item['home'], 28)} x {name(item['away'], 28)}")
        if names:
            lines.extend(["", "<b>⏳ Jogos aguardando odds</b>", *names])

    lines.extend([
        "",
        "⚠️ <i>Odds observadas não comprovam volume negociado,"
        " preço de entrada nem lucro.</i>",
        '🔗 <a href="https://nexus-score-gratis.pages.dev/">Abrir NEXUS</a>',
    ])
    message = "\n".join(lines)
    if len(message) > 4096:
        # Telegram limita sendMessage a 4096 caracteres. Preserve o essencial.
        essentials = lines[:]
        marker = "<b>⏳ Jogos aguardando odds</b>"
        if marker in essentials:
            essentials = essentials[:essentials.index(marker)] + essentials[-3:]
        message = "\n".join(essentials)
    if len(message) > 4096:
        raise ValueError("Resumo Telegram excedeu o limite seguro de 4096 caracteres")
    return message


def deliver(day, marker_folder=Path("state/nexus_football_reports"), fetch=load_summary,
            messenger=api, priority_fetch=None):
    marker_folder.mkdir(parents=True, exist_ok=True)
    marker = marker_folder / (day + ".json")
    if marker.exists():
        print("Relatório esportivo deste dia já enviado; nenhum Telegram repetido.")
        return False
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Token do bot existente não disponível neste GitHub Action")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or load_chat(token)
    if not chat:
        raise RuntimeError("Chat do Telegram não encontrado no Nexus Quant")
    me = messenger(token, "getMe")
    if str(me.get("username") or "").casefold() != BOT.casefold():
        raise RuntimeError("Token não pertence ao bot NexusQuantAlertasBot")
    try:
        data = fetch(day)
        coverage = None
        if priority_fetch is not None:
            try:
                coverage = priority_fetch()
            except (OSError, ValueError, KeyError, TypeError, TimeoutError):
                print("Radar de jogos importantes indisponível; relatório normal preservado.")
        message = format_football(data, coverage)
    except (OSError, ValueError, KeyError, TimeoutError) as exc:
        # Uma coleta atrasada NÃO envia mensagem de zeros nem marca o dia
        # como concluído. O workflow agenda tentativas de recuperação.
        # A primeira mensagem válida deste dia é a ÚNICA enviada.
        print("Arquivo esportivo ainda inválido/indisponível; sem envio, "
              "nova tentativa será feita no próximo agendamento: "
              + type(exc).__name__)
        raise RuntimeError("Dados do fechamento NEXUS indisponíveis; Telegram não enviado") from exc
    result = messenger(token, "sendMessage", {"chat_id": chat, "text": message,
                                              "parse_mode": "HTML",
                                              "disable_web_page_preview": True})
    if not isinstance(result, dict) or not result.get("message_id"):
        raise RuntimeError("Telegram não confirmou entrega do relatório esportivo")
    marker.write_text(json.dumps({"day": day, "sent_at": datetime.now(timezone.utc).isoformat(),
                                  "kind": "nexus_football_daily"}, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print("Relatório diário de futebol confirmado pelo Telegram existente.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day")
    args = parser.parse_args()
    day = args.day or (datetime.now(TZ).date() - timedelta(days=1)).isoformat()
    datetime.strptime(day, "%Y-%m-%d")
    deliver(day, priority_fetch=load_priority_coverage)


if __name__ == "__main__":
    main()
