"""Scheduled observer with Telegram opt-in. Never trades."""
import argparse,json,os,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from .feed import MARKETS,get_bars
from .monitor import empty_state,scan_market,report,date_local
from .private_chat import load_chat, save_chat
from .gold_forward import process as process_gold
from .leveraged_gold import process as process_leveraged
from .daily_digest import digest as ten_bot_digest
from .bb_rebound_mtf import fetch_15m as fetch_usdcad_m15, process as process_bb20

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
    data=json.dumps({"chat_id":chat,"text":message},ensure_ascii=False).encode("utf-8")
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
    mtf_book=None;mtf_error=None
    try:
        data_m15=fetch_usdcad_m15(now)
        mtf_book=process_bb20(data_m15)
        print(f"USD/CAD BB20 M15: {len(data_m15)} candles; "+mtf_book["last_reason"])
    except Exception as error:
        mtf_error=str(error)
        print("USD/CAD BB20 indisponível (sem preencher dados): "+mtf_error)
    statefile.parent.mkdir(parents=True,exist_ok=True)
    statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if mode=="report" and state["last_report_day"]!=day:
        msg=ten_bot_digest(day,gold_book,leveraged_book,datasets,unavailable=failed,mtf=mtf_book,mtf_error=mtf_error)
        if len(msg)>4000:raise RuntimeError("Telegram: relatório excede o limite de mensagem")
        reports.mkdir(parents=True,exist_ok=True)
        (reports/f"{day}.txt").write_text(msg+"\n",encoding="utf-8")
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
