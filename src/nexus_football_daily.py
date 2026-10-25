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


def format_football(data):
    # Com arquivo bruto, o painel principal mostra SÓ jogos com volume comprovado.
    # Resumos legados sem separação explícita mantêm o rótulo geral.
    qualified = data.get("qualified_results")
    r = qualified if isinstance(qualified, dict) else data["results"]
    def line(key):
        return f"{r.get(key + '_yes', 0)} sim / {r.get(key + '_no', 0)} não"
    houses = ", ".join(k for k in list(data["bookmakers"])[:4]) or "sem cotações confirmadas"
    markets = ", ".join(k for k in list(data.get("market_families_quoted") or {})[:6]) or "nenhum com preço verificado"
    return (
        f"⚽ NEXUS FUTEBOL — FECHAMENTO {data['day']}\n"
        f"Jogos {data['games']} | Encerrados {data['finished']}\n"
        f"Odds verificadas {data['quotes_verified']} em {data['games_with_verified_odds']} jogos\n"
        f"🎯 Odds em jogos com liquidez comprovada: {data.get('qualified_game_quotes_verified', 0)}\n"
        f"💰 Liquidez comprovada ≥ R$ 3 mil: {data.get('liquidity_qualified_games', 0)} jogos\n"
        f"⚪ Volume abaixo: {data.get('liquidity_below_games', 0)} | "
        f"Sem comprovação: {data.get('liquidity_unknown_games', data['games'])}\n"
        f"Famílias com preço {data['market_families_with_verified_prices']}/{data['market_families_catalogued']}\n"
        f"Mercados: {markets}\n"
        f"Casas: {houses}\n\n"
        f"📊 Resultados {'com liquidez ≥ R$ 3 mil' if isinstance(qualified, dict) else 'gerais'}\n"
        f"1X2: Casa {r.get('1x2_home', 0)} | Empate {r.get('1x2_draw', 0)} | Fora {r.get('1x2_away', 0)}\n"
        f"Over 2.5: {line('over_2_5')}\n"
        f"BTTS: {line('btts')}\n"
        f"Escanteios >9.5: {line('corners_9_5')}\n"
        f"Cartões amarelos >4.5: {line('cards_4_5')}\n"
        f"Chutes no alvo >7.5: {line('sot_7_5')}\n"
        f"📋 Amostra geral: {data['finished']} partidas encerradas | "
        f"1X2 casa {data['results'].get('1x2_home',0)}, empate {data['results'].get('1x2_draw',0)}, "
        f"fora {data['results'].get('1x2_away',0)}\n"
        f"⛔ Dados esportivos; sem lucros ou entradas comprovados.\n"
        f"https://nexus-score-gratis.pages.dev/"
    )


def deliver(day, marker_folder=Path("state/nexus_football_reports"), fetch=load_summary,
            messenger=api):
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
        message = format_football(data)
    except (OSError, ValueError, KeyError, TimeoutError) as exc:
        # Falta de arquivo ou falha de rede NÃO vira dados zero inventados.
        print("Relatório esportivo não disponível: " + type(exc).__name__)
        message = (f"⚠️ NEXUS FUTEBOL | {day}\n"
                   "A coleta diária ainda não está disponível/validada. "
                   "Nenhum resultado ou lucro foi estimado.\n"
                   "https://nexus-score-gratis.pages.dev/")
    result = messenger(token, "sendMessage", {"chat_id": chat, "text": message})
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
    deliver(day)


if __name__ == "__main__":
    main()
