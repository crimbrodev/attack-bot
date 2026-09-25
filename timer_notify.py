"""Уведомление о конце слаймода в канале.

Через Telethon проверяет slowmode_next_send_date в slay_awards.
Когда таймер кончается — шлёт уведомление через бота в группу "уведомления о таймере".

Запуск: python timer_notify.py
Ничего не меняет в существующих модулях."""
import asyncio
import time
import logging

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest

from aiogram import Bot

from config import (
    BOT_TOKEN, USERBOT_API_ID, USERBOT_API_HASH,
    STATE_DIR,
)
from logging.handlers import RotatingFileHandler

USERBOT_SESSION_TIMER = "timer_session"  # отдельная сессия чтобы не конфликтовать с comments.py

# === Настройки ===
TIMER_GROUP = -5195152951  # "уведомления о таймере"
CHANNEL = "slay_awards"
POLL_INTERVAL = 30  # секунд между проверками
NOTIFY_BEFORE = 5  # уведомлять за N секунд до конца

log = logging.getLogger("timer")
log.setLevel(logging.DEBUG)

# Файл с ротацией
fh = RotatingFileHandler(
    STATE_DIR / "timer_notify.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
log.addHandler(fh)

# Консоль
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
log.addHandler(ch)

tg = Bot(token=BOT_TOKEN)


async def get_slowmode_info(client: TelegramClient) -> dict:
    """Получает инфу о слаймоде в связанном чате (комментарии)."""
    entity = await client.get_entity(CHANNEL)
    full = await client(GetFullChannelRequest(entity))
    chat = full.full_chat

    if not chat.linked_chat_id:
        return {"enabled": False, "slowmode_seconds": 0, "next_send_date": None, "remaining": 0.0}

    linked = await client.get_entity(chat.linked_chat_id)
    full_linked = await client(GetFullChannelRequest(linked))
    lc = full_linked.full_chat

    slowmode_seconds = lc.slowmode_seconds or 0
    next_send = lc.slowmode_next_send_date

    now = time.time()
    if next_send:
        # Telegram API отдаёт datetime, конвертируем в timestamp
        if hasattr(next_send, 'timestamp'):
            next_ts = next_send.timestamp()
        else:
            next_ts = float(next_send)
        remaining = max(0, next_ts - now)
    else:
        remaining = 0.0

    return {
        "enabled": slowmode_seconds > 0,
        "slowmode_seconds": slowmode_seconds,
        "next_send_date": next_send,
        "remaining": remaining,
    }


async def notify_bot(text: str) -> None:
    """Шлёт сообщение через бота в группу уведомлений."""
    try:
        await tg.send_message(TIMER_GROUP, text, parse_mode="HTML")
        log.info(f"Уведомление отправлено: {text[:80]}")
    except Exception as e:
        log.error(f"Ошибка отправки: {e}")


async def main() -> None:
    log.info("Запуск timer_notify...")

    client = TelegramClient(
        USERBOT_SESSION_TIMER,
        USERBOT_API_ID,
        USERBOT_API_HASH,
    )
    await client.start()
    log.info("Telethon подключён")

    notified = False  # уже отправили уведомление?

    while True:
        try:
            info = await get_slowmode_info(client)

            if not info["enabled"]:
                if notified:
                    notified = False
                    log.info("Слаймод выключен, сброшен флаг")
                log.debug("Слаймода нет")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            remaining = info["remaining"]
            sm = info["slowmode_seconds"]

            if remaining <= 0:
                if not notified:
                    await notify_bot(
                        "✅ <b>Слаймод закончился!</b>\n"
                        "Можно писать комментарий 🚀"
                    )
                    notified = True
                    log.info(f"Слаймод ({sm}с) закончился — уведомление отправлено")
            else:
                notified = False
                mins = int(remaining) // 60
                secs = int(remaining) % 60
                log.debug(f"Слаймод {sm}с, осталось {mins}м {secs}с")

                if remaining <= NOTIFY_BEFORE and remaining > 0:
                    await notify_bot(
                        f"⏳ Слаймод заканчивается через {mins} мин {secs} сек..."
                    )
                    log.info(f"Предупреждение: осталось {mins}м {secs}с")

        except Exception as e:
            log.error(f"Ошибка: {e}")

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
