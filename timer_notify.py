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
    BOT_TOKEN, USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION,
    STATE_DIR,
)

# === Настройки ===
TIMER_GROUP = -5195152951  # "уведомления о таймере"
CHANNEL = "slay_awards"
POLL_INTERVAL = 30  # секунд между проверками
NOTIFY_BEFORE = 5  # уведомлять за N секунд до конца

log_file = STATE_DIR / "timer_notify.log"
handler = logging.FileHandler(log_file, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
log = logging.getLogger("timer")

tg = Bot(token=BOT_TOKEN)


async def get_slowmode_info(client: TelegramClient) -> dict:
    """Получает инфу о слаймоде в канале и связанном чате.

    Returns:
        {
            "enabled": bool,
            "slowmode_seconds": int | None,
            "next_send_date": datetime | None,
            "remaining": float,
            "source": str,  # откуда взята инфа
        }
    """
    entity = await client.get_entity(CHANNEL)
    full = await client(GetFullChannelRequest(entity))
    chat = full.full_chat

    slowmode_seconds = chat.slowmode_seconds or 0
    next_send = chat.slowmode_next_send_date
    source = "channel"

    # Если на канале нет слаймода — проверяем связанный чат (комментарии)
    if not slowmode_seconds and chat.linked_chat_id:
        try:
            linked = await client.get_entity(chat.linked_chat_id)
            full_linked = await client(GetFullChannelRequest(linked))
            lc = full_linked.full_chat
            if lc.slowmode_seconds:
                slowmode_seconds = lc.slowmode_seconds
                next_send = lc.slowmode_next_send_date
                source = "linked_chat"
        except Exception as e:
            log.debug(f"Не удалось проверить linked_chat: {e}")

    now = time.time()
    remaining = 0.0
    if next_send:
        remaining = max(0, next_send - now)

    return {
        "enabled": slowmode_seconds > 0,
        "slowmode_seconds": slowmode_seconds,
        "next_send_date": next_send,
        "remaining": remaining,
        "source": source,
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
        USERBOT_SESSION,
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
                # Слаймода нет — сбрасываем флаг
                if notified:
                    notified = False
                    log.info("Слаймод выключен, сброшен флаг")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            remaining = info["remaining"]

            if remaining <= 0:
                # Таймер кончился — можно писать!
                if not notified:
                    await notify_bot(
                        "✅ <b>Слаймод закончился!</b>\n"
                        "Можно писать комментарий 🚀"
                    )
                    notified = True
            else:
                # Таймер ещё идёт
                notified = False

                # Уведомляем за N секунд до конца
                if remaining <= NOTIFY_BEFORE and remaining > 0:
                    mins = int(remaining) // 60
                    secs = int(remaining) % 60
                    await notify_bot(
                        f"⏳ Слаймод заканчивается через {mins} мин {secs} сек..."
                    )

            log.debug(f"remaining={remaining:.0f}s, notified={notified}")

        except Exception as e:
            log.error(f"Ошибка: {e}")

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
