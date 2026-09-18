"""Получение комментариев к посту канала через Telethon."""
import asyncio
from telethon import TelegramClient
from config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION

DELAY_BETWEEN_COMMENTS = 2  # секунды между пачками комментариев


async def get_post_commenters(channel: str, post_id: int) -> list[dict]:
    """Возвращает список авторов комментариев к посту.

    Returns: [{"user_id": 123, "username": "xxx", "name": "XXX"}, ...]
    """
    if not USERBOT_API_ID or not USERBOT_API_HASH or not USERBOT_SESSION:
        return []

    client = TelegramClient(
        USERBOT_SESSION,
        USERBOT_API_ID,
        USERBOT_API_HASH,
    )

    try:
        await client.start()

        entity = await client.get_entity(channel)
        message = await client.get_messages(entity, ids=post_id)
        if not message:
            return []

        if not message.replies or not message.replies.comments:
            return []

        all_comments = []
        offset_id = 0
        while True:
            batch = await client.get_messages(
                entity,
                reply_to=post_id,
                limit=100,
                offset_id=offset_id,
            )
            if not batch:
                break
            all_comments.extend(batch)
            offset_id = batch[-1].id
            if len(batch) < 100:
                break
            await asyncio.sleep(DELAY_BETWEEN_COMMENTS)

        commenters = []
        for comment in all_comments:
            if comment.sender_id:
                user = await comment.get_sender()
                commenters.append({
                    "user_id": comment.sender_id,
                    "username": getattr(user, "username", "") or "",
                    "name": getattr(user, "first_name", "") or "",
                })

        return commenters

    except Exception as e:
        print(f"get_post_commenters error: {e}")
        return []

    finally:
        await client.disconnect()


def calc_squad_percentage(commenters: list[dict], squad_users: dict) -> tuple[int, int, float]:
    """Считает процент комментариев от взвода.

    Args:
        commenters: список авторов комментариев
        squad_users: словарь users.json {chat_id: {user_id: {name, username}}}

    Returns: (squad_count, total_count, percentage)
    """
    all_squad_ids = set()
    for chat_id, users in squad_users.items():
        for uid in users.keys():
            try:
                all_squad_ids.add(int(uid))
            except ValueError:
                pass

    total = len(commenters)
    if total == 0:
        return 0, 0, 0.0

    squad_count = sum(
        1 for c in commenters
        if c["user_id"] in all_squad_ids
    )

    percentage = (squad_count / total) * 100
    return squad_count, total, percentage
