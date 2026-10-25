"""Persist the private Telegram chat ID encrypted with the GitHub bot-token secret.

No identifying chat ID is committed in clear text to this public repository.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PATH = Path("state/telegram_chat.enc.json")
AAD = b"NexusQuant/TelegramChat/v1"

def _key(token):
    if not token: raise ValueError("Missing Telegram token")
    return hashlib.sha256(("nexus-private-chat-v1:"+token).encode("utf-8")).digest()

def save_chat(token, chat, path=PATH):
    raw=str(chat)
    if not raw.lstrip("-").isdigit(): raise ValueError("Chat ID must be numeric")
    nonce=os.urandom(12)
    cipher=AESGCM(_key(token)).encrypt(nonce,raw.encode("utf-8"),AAD)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({
        "version":1, "nonce":base64.b64encode(nonce).decode("ascii"),
        "sealed":base64.b64encode(cipher).decode("ascii")
    })+"\n",encoding="utf-8")

def load_chat(token,path=PATH):
    if not path.exists():return None
    try:
        obj=json.loads(path.read_text(encoding="utf-8"))
        if obj["version"]!=1:raise ValueError("Unknown chat-store version")
        nonce=base64.b64decode(obj["nonce"],validate=True)
        data=base64.b64decode(obj["sealed"],validate=True)
        result=AESGCM(_key(token)).decrypt(nonce,data,AAD).decode("utf-8")
        if not result.lstrip("-").isdigit():raise ValueError("Invalid decrypted chat")
        return result
    except Exception:
        raise RuntimeError("Encrypted Telegram chat could not be loaded; check bot token consistency.") from None
