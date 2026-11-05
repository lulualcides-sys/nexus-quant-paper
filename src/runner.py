"""Scheduled observer with Telegram opt-in. Never trades."""
# Controlled PAPER-only forward scan retry after a queued-run cancellation; no trade alerts.
import argparse,json,os,sys,urllib.request
from html import escape
from datetime import datetime,timezone
from pathlib import Path
from .feed import MARKETS,get_bars
from .monitor import empty_state,scan_market,report,date_local
from .private_chat import load_chat, save_chat
from .gold_forward import process as process_gold
from .leveraged_gold import process as process_leveraged
from .daily_digest import digest as ten_bot_digest
from .bb_rebound_mtf import fetch_15m as fetch_usdcad_m15, process as process_bb20
from .experimental_h1 import process as process_h1, diagnostics as h1_diagnostics
from .h4_entry_audit import audit as audit_h4_entries, telegram_summary as h4_telegram_summary
from .momentum60_shadow import process as process_momentum60
from .atlas_vector import process as process_atlas, daily_line as atlas_daily_line, scorecard as atlas_scorecard
from .all_robots_audit import build as audit_all_27, telegram_line as audit_27_line
from .news_guard import upcoming as macro_upcoming
from .wti_channel10_shadow import process as process_wti_filtered
from .profit_watchlist import build as build_profit_watchlist, telegram_line as profit_watchlist_line

STATE=Path("state/market_monitor.json")
REPORTS=Path("reports")

def discover_private_chat(token):
    # Only auto-discover if exactly one private chat has explicitly started the bot.
    url=f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(urllib.request.Request(url),timeout=20) as res:
            response=json.load(res)
        if not response.get("ok"):return None
        chats=set()
        for u in response.get("result",[]):
            m=u.get("message") or {}
            chat=m.get("chat") or {}
            if chat.get("type")=="private" and (m.get("text") or "").strip().startswith("/start"):
                chats.add(str(chat.get("id")))
        return next(iter(chats)) if len(chats)==1 else None
    except Exception:
        return None

def telegram(message):
    token=os.environ.get("TELEGRAM_BOT_TOKEN","").strip()
    chat=os.environ.get("TELEGRAM_CHAT_ID","").strip()
    if not token:
        print("Bot sem token; relatório não enviado.")
        return False
    chat=chat or load_chat(token) or discover_private_chat(token)
    if not chat:
        print("Nenhuma conversa /start única; configure TELEGRAM_CHAT_ID no GitHub.")
        return False
    payload = {"chat_id": chat, "text": message}
    if message.startswith("<b>📊 NEXUS QUANT"):
        payload["parse_mode"] = "HTML"
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            result=json.load(response)
    except Exception:
        raise RuntimeError("Não foi possível enviar ao Telegram. Confira o bot e seu chat ID.") from None
    if not result.get("ok"):raise RuntimeError("Telegram não confirmou o envio")
    save_chat(token,chat)
    return True

def run(mode="scan",*,statefile=STATE,reports=REPORTS,fetch=get_bars,send=telegram,now=None):
    now=int(now if now is not None else datetime.now(timezone.utc).timestamp())
    day=date_local(now)
    if mode=="mtf":

        data_m15=fetch_usdcad_m15(now)
        bb_book=process_bb20(data_m15)

        print(f"USD/CAD BB20 M15: {len(data_m15)} candles; "+bb_book["last_reason"])
        return bb_book
    state=json.loads(statefile.read_text(encoding="utf-8")) if statefile.exists() else empty_state()
    datasets={};failed=[]
    for key,asset in MARKETS.items():
        try:
            bars=fetch(asset,now)
            datasets[key]=bars
            try:
                count=scan_market(state,key,bars)
                print(f"{key}: {len(bars)} candles; {count} sinais diagnósticos.")
            except Exception as error:
                # Old H1 research must never block all ten H4 paper books.
                failed.append(f"{key} H1: {error}")
        except Exception as error:
            failed.append(key)
    if "XAUUSD" not in datasets:
        raise RuntimeError("Sem candles verificados do ouro; os 10 robôs não serão atualizados.")

    gold_book=process_gold(datasets["XAUUSD"])
    leveraged_book=process_leveraged(datasets["XAUUSD"])

    # Isolated, experimental forward-only book; never impacts the 26 existing
    # models, their risk, balances, or their daily reporting if unavailable.
    momentum60_book=None;momentum60_error=None
    try:
        momentum60_book=process_momentum60(datasets["XAUUSD"])
        print("Momentum60 virtual H4: "+str(len(momentum60_book["entries"]))+" entradas observadas.")
    except Exception as error:
        momentum60_error=type(error).__name__
        print("Momentum60 experimental indisponível, demais robôs preservados: "+str(error)[:150])

    # ATLAS is robot #28: own paper state; errors NEVER affect the existing 27.
    atlas_book=None;atlas_error=None
    try:
        atlas_book=process_atlas(datasets["XAUUSD"])
        print("ATLAS #28 H4 virtual: "+str(len(atlas_book["entries"]))+" observed entries.")
    except Exception as error:
        atlas_error=type(error).__name__
        print("ATLAS indisponível; 27 robôs preservados: "+str(error)[:150])

    mtf_book=None;mtf_error=None
    try:

        data_m15=fetch_usdcad_m15(now)
        mtf_book=process_bb20(data_m15)

        print(f"USD/CAD BB20 M15: {len(data_m15)} candles; "+mtf_book["last_reason"])
    except Exception as error:
        mtf_error=str(error)
        print("USD/CAD BB20 indisponível (sem preencher dados): "+mtf_error)
    # New candidate runs in its own paper book and NEVER rewrites the 15 H1 books.
    wti_filtered=None;wti_filtered_error=None
    if "XTIUSD" in datasets:
        try:
            wti_filtered=process_wti_filtered(datasets["XTIUSD"])
            print("WTI Channel10 filtered shadow: "+str(len(wti_filtered["book"]["entries"]))+
                  " prospective virtual entries.")
        except Exception as error:
            wti_filtered_error=type(error).__name__
            print("WTI filtered candidate unavailable: "+str(error)[:150])
    else:
        wti_filtered_error="no_XTIUSD_feed"

    shadow_book=None
    try:

        shadow_book=process_h1(datasets)

        print(f"H1 experimental: {len(shadow_book['books'])} livros em {len(shadow_book['watermarks'])} mercados.")
    except Exception as error:
        failed.append("H1 experimental: "+str(error)[:130])
        print("H1 experimental indisponível (estado preservado): "+str(error))

    statefile.parent.mkdir(parents=True,exist_ok=True)
    statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if mode=="report" and state["last_report_day"]!=day:
        msg=ten_bot_digest(day,gold_book,leveraged_book,datasets,unavailable=failed,mtf=mtf_book,mtf_error=mtf_error,shadow=shadow_book,momentum60=momentum60_book,planned_robots=27)
        # ATLAS #28 is separate from the immutable 27-robot audit/cohort.
        # It reports only observed PAPER results; no invented win rate.
        atlas_line=atlas_daily_line(atlas_book,day)
        if atlas_book is None:
            atlas_line += " | erro: "+str(atlas_error or "sem dados")
        if len(msg)+len(atlas_line)+1<=4000:
            msg+="\n"+escape(atlas_line)
        # Read-only supervisory stage: an audit failure must not block the daily
        # recap or change existing positions, state schema, or entry rules.
        h4_observation=None; h4_error=None
        try:
            h4_observation=audit_h4_entries(datasets["XAUUSD"],gold_book,leveraged_book,now)
        except Exception as error:
            h4_error=type(error).__name__
            print("Diagnóstico H4 indisponível (robôs preservados): "+str(error)[:160])
        # Aggregation observes ONLY existing states and never changes their
        # books. In particular, unavailable cannot be reported as zero profit.
        complete_audit=None
        try:
            complete_audit=audit_all_27(
                now=now, conventional=gold_book, leveraged=leveraged_book,
                h4_result=h4_observation, h1_state=shadow_book,
                mtf_state=mtf_book, momentum_state=momentum60_book,
                errors={"h4": h4_error, "h1": "sem estado H1",
                        "mtf": type(mtf_error).__name__ if mtf_error else None,
                        "momentum60": momentum60_error})
            line=audit_27_line(complete_audit)
            if len(msg)+len(line)+1<=4000:
                msg+="\n"+escape(str(line))
        except Exception as error:
            print("Consolidação 27 indisponível; relatório tradicional mantido: "+str(error)[:160])
        try:
            macro=macro_upcoming(now)
            active=os.environ.get("NEXUS_NEWS_GUARD_ENABLED","0").strip()=="1"
            if macro["status"]=="known":
                event_count=len(macro["next"])
                macro_line=(f"📰 Agenda macro oficial: {event_count} evento(s) nos próximos 7 dias"
                            f" | bloqueio de novas entradas: {'ON' if active else 'OFF (teste)'}")
            else:
                macro_line=(f"📰 Agenda macro: desatualizada/indisponível"
                            f" | bloqueio de novas entradas: {'ON, fail-closed' if active else 'OFF'}")
            if len(msg)+len(macro_line)+1<=4000:
                msg+="\n"+escape(macro_line)
        except Exception as error:
            print("Resumo macro indisponível: "+type(error).__name__)
        # Prospective three-strategy profitability check, strictly read-only.
        # Failed/absent WTI observations never translate into false zero profit.
        profit_observation=None
        try:
            profit_observation=build_profit_watchlist(
                now=now,conventional=gold_book,wti=wti_filtered)
            line=profit_watchlist_line(profit_observation)
            if len(msg)+len(line)+1<=4000:
                msg+="\n"+escape(str(line))
        except Exception as error:
            print("Watchlist de lucro prospectivo indisponível: "+
                  type(error).__name__+" "+str(error)[:100])
        if len(msg)>4000:raise RuntimeError("Telegram: relatório excede o limite de mensagem")
        reports.mkdir(parents=True,exist_ok=True)
        atlas_path=reports/"atlas"/f"{day}.json"
        atlas_path.parent.mkdir(parents=True,exist_ok=True)
        atlas_report=({
            "date": day, "bot": "ATLAS", "slot": 28, "paper_only": True,
            "status": "available" if atlas_book is not None else "unavailable",
            "metrics": atlas_scorecard(atlas_book) if atlas_book is not None else None,
            "error_type": atlas_error if atlas_book is None else None,
            "signal_model": "independent_sweep_wick_relative_volume_v1",
            "notes": "Not proprietary Tracker; no real fills; winrate is net of estimated costs",
        })
        atlas_path.write_text(json.dumps(atlas_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if complete_audit is not None:
            full_path=reports/"robot_diagnostics"/f"{day}.json"
            full_path.parent.mkdir(parents=True,exist_ok=True)
            full_path.write_text(json.dumps(complete_audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if profit_observation is not None:
            profit_report=reports/"profit_watchlist"/f"{day}.json"
            profit_report.parent.mkdir(parents=True,exist_ok=True)
            profit_report.write_text(json.dumps(profit_observation,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if h4_observation is not None:
            entry_report=reports/"entry_audit"/f"{day}.json"
            entry_report.parent.mkdir(parents=True,exist_ok=True)
            entry_report.write_text(json.dumps(h4_observation,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (reports/f"{day}.txt").write_text(msg+"\n",encoding="utf-8")
        if shadow_book is not None:
            audit_path=reports/"experimental_h1"/f"{day}.json"
            audit_path.parent.mkdir(parents=True,exist_ok=True)
            audit_path.write_text(json.dumps({
                "day":day,"status":"experimental-unvalidated","paper_only":True,
                "source":"Yahoo H1 proxies (not executable FBS)",
                "market_data_unavailable":shadow_book.get("unavailable",[]),
                "robots":h1_diagnostics(shadow_book)
            },indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        if send(msg):
            state["last_report_day"]=day
            statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return state

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["scan","report","mtf"],default="scan")
    args=parser.parse_args()
    try:run(args.mode)
    except Exception as exc:
        print("ERRO SEM DADOS FABRICADOS: "+str(exc),file=sys.stderr)
        sys.exit(1)
