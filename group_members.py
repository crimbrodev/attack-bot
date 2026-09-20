"""Сбор участников группы через Telethon для обновления users.json."""
import asyncio
from telethon import TelegramClient
from config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION
from storage import load_users, save_users


async def fetch_group_members(group_id: int) -> dict:
    """Получает всех участников группы через Telethon (aggressive=True для полного списка).

    Returns: {user_id: {"name": "...", "username": "..."}}
    """
    if not USERBOT_API_ID or not USERBOT_API_HASH or not USERBOT_SESSION:
        return {}

    client = TelegramClient(
        USERBOT_SESSION,
        USERBOT_API_ID,
        USERBOT_API_HASH,
    )

    try:
        await client.start()
        entity = await client.get_entity(group_id)

        members = {}
        async for user in client.iter_participants(entity, aggressive=True):
            if user.bot:
                continue
            name = (user.first_name or '') + ' ' + (user.last_name or '')
            name = name.strip() or str(user.id)
            members[str(user.id)] = {
                "name": name[:60],
                "username": (user.username or '').strip(),
            }

        return members

    except Exception as e:
        print(f"fetch_group_members error: {e}")
        return {}

    finally:
        await client.disconnect()


async def update_group_members(group_id: int) -> int:
    """Обновляет участников группы в users.json.

    Returns: количество участников после обновления
    """
    members = await fetch_group_members(group_id)
    if not members:
        return 0

    users = load_users()
    cid = str(group_id)
    existing = users.get(cid, {})

    # Обновляем: добавляем новых, обновляем существующих
    for uid, info in members.items():
        if uid not in existing:
            existing[uid] = info
        else:
            # Обновляем username если изменился
            if info.get("username") and not existing[uid].get("username"):
                existing[uid]["username"] = info["username"]

    users[cid] = existing
    save_users(users)
    return len(existing)


if __name__ == "__main__":
    count = asyncio.run(update_group_members(-1004365297986))
    print(f"Updated: {count} members")
