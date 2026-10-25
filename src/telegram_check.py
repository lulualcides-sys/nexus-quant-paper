"""One-time Telegram connection check; never prints or exposes secrets."""
import json
import os
import sys
import urllib.error
import urllib.request

EXPECTED_USERNAME = "NexusQuantAlertasBot"

def api(token,method,payload=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    raw = json.dumps(payload,ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url,data=raw,headers={"Content-Type":"application/json"} if raw else {})
    try:
        with urllib.request.urlopen(req,timeout=18) as response:
            out=json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:raise RuntimeError("Token inválido ou revogado (erro 401).") from None
        if exc.code == 409:raise RuntimeError("Existe um webhook ou outra leitura de atualizações em conflito (409).") from None
        raise RuntimeError(f"Falha na API Telegram (HTTP {exc.code}).") from None
    except Exception as exc:
        raise RuntimeError(f"Telegram indisponível: {type(exc).__name__}") from None
    if not out.get("ok"):
        raise RuntimeError(f"Telegram recusou {method}.")
    return out["result"]

def main():
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    if not token:raise RuntimeError("Secret TELEGRAM_BOT_TOKEN ausente ou vazio no GitHub Actions.")
    me=api(token,"getMe")
    username=me.get("username","")
    if username.casefold()!=EXPECTED_USERNAME.casefold():
        raise RuntimeError("Este token pertence a outro bot. Confirme que é do @NexusQuantAlertasBot.")
    print(f"✅ Token válido e pertence a @{username}")
    chat=os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not chat:
        updates=api(token,"getUpdates")
        chats=set()
        for update in updates:
            message=update.get("message") or {}
            dest=message.get("chat") or {}
            # A private message to the bot is sufficient to opt in; only use
            # automatic discovery when exactly one private conversation exists.
            if dest.get("type")=="private" and dest.get("id"):
                chats.add(str(dest.get("id")))
        print(f"Atualizações disponíveis: {len(updates)}; conversas privadas: {len(chats)}")
        if len(chats)==0:
            raise RuntimeError("Telegram não devolveu uma conversa privada recente. Envie /start novamente ao bot e repita o teste.")
        if len(chats)>1:
            raise RuntimeError("Há vários chats iniciados; configure TELEGRAM_CHAT_ID para identificar seu chat.")
        chat=next(iter(chats))
    msg=("✅ Nexus Quant conectado ao Telegram!\n"
         "🤖 Monitor: 5 robôs × 5 mercados.\n"
         "📌 Este é um teste de conexão, não um resultado de trading.\n"
         "⚠️ Nenhuma operação foi executada na FBS.")
    reply=api(token,"sendMessage",{"chat_id":chat,"text":msg,"disable_notification":False})
    if not reply.get("message_id"):raise RuntimeError("API não confirmou a mensagem.")
    print("✅ Telegram confirmou o envio da mensagem de teste ao chat privado.")
if __name__=="__main__":
    try:main()
    except Exception as error:
        print("❌ "+str(error),file=sys.stderr)
        sys.exit(1)
