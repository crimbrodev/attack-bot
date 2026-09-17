"""Локальный base-модуль — вся логика без внешних зависимостей."""
import os
import json
import httpx
from pathlib import Path

# === Конфигурация ===
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
ALLOWED_USERS = [int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()]

SUBS_FILE = Path(__file__).parent / "subs.json"

# === Whitelist ===
REFUSE_TEXT = "❌ Ты не в whiteliste. Попроси админа добавить."

def is_allowed(message) -> bool:
    """Проверяет whitelist. Если ALLOWED_USERS пуст — пускает всех."""
    if not ALLOWED_USERS:
        return True
    if not message.from_user:
        return False
    return message.from_user.id in ALLOWED_USERS

def save_sub(chat_id: int) -> None:
    """Сохраняет подписку (chat_id) в subs.json."""
    try:
        subs = []
        if SUBS_FILE.exists():
            subs = json.loads(SUBS_FILE.read_text(encoding="utf-8"))
        if chat_id not in subs:
            subs.append(chat_id)
            SUBS_FILE.write_text(json.dumps(subs), encoding="utf-8")
    except Exception:
        pass

# === Groq API ===
def chat_with_failover(messages: list[dict], max_tokens: int = 1500, temperature: float = 1.1) -> str:
    """Вызов Groq API для генерации текста."""
    if not GROQ_API_KEY:
        return ""
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Groq API error: {e}")
        return ""

# === Реклама и подпись ===
AD_VARIANTS = [
    "\n\n🎧 Слушай лучшую музыку здесь: @MagnumMusicBot",
    "\n\n🎵 Топ треки每一天: @MagnumMusicBot",
    "\n\n🎶 Музыка без границ: @MagnumMusicBot",
    "\n\n🔊 Врубай музыку: @MagnumMusicBot",
]

SIGN = "\n\n— Боевой бот 🔥"
