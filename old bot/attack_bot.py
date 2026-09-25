"""Боевой бот (объединённый): следит за @slay_awards, командует атакой в группах
+ функции первого бота: лички, /ask, коммент с рекламой Magnum по пересланному посту."""
import asyncio
import html as htmlmod
import json
import logging
import os
import random
import re
import sys

sys.path.insert(0, "/root/kazahstanos/projects/slay4242bot")
import bot as base  # общий Groq-ключ, модели, whitelist своих

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message, ChatMemberUpdated

TOKEN = "BOT_TOKEN_REMOVED"
STATE_DIR = "/root/kazahstanos/projects/attack3v1r1b42pbot"
GROUPS_FILE = f"{STATE_DIR}/groups.json"
LAST_FILE = f"{STATE_DIR}/last.json"
USERS_FILE = f"{STATE_DIR}/users.json"
ATTACK_FILE = f"{STATE_DIR}/attack.txt"
DEFAULT_COUNT = 5

bot = Bot(token=TOKEN)
dp = Dispatcher()


def load_groups() -> dict:
    try:
        with open(GROUPS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_groups(g: dict) -> None:
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False)


def load_users() -> dict:
    """{chat_id_str: {uid_str: {name, username}}} — все кто писал в группе.
    ZazyvalaTag2Bot-стиль: тегаем всех по @username или tg://user?id=..."""
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_users(u: dict) -> None:
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(u, f, ensure_ascii=False)
    except Exception as err:
        print(f"users-save: {err}")


def remember_user(chat_id: int, user) -> None:
    """Запоминаем всех, кто писал в группе — потом тегаем в callall."""
    try:
        if not user or getattr(user, "is_bot", False):
            return
        u = load_users()
        cid = str(chat_id)
        grp = u.setdefault(cid, {})
        name = (user.full_name or user.username or str(user.id))[:60]
        grp[str(user.id)] = {"name": name, "username": (getattr(user, "username", "") or "").strip()}
        save_users(u)
    except Exception as err:
        print(f"remember: {err}")


def build_tags_from_users(cid: str) -> list[str]:
    """Собирает теги по ZazyvalaTag2Bot-стилю:
    если есть @username — тег текстом (прилетит уведом), иначе кликабельная ссылка с именем."""
    tags: list[str] = []
    users_here = load_users().get(cid, {})
    for uid, info in users_here.items():
        uname = (info.get("username") or "").strip()
        if uid.startswith("u_"):
            if uname:
                tags.append("@" + uname.lstrip("@"))
            continue
        if uname:
            tags.append("@" + uname.lstrip("@"))
        else:
            name = htmlmod.escape((info.get("name") or "боец")[:40], quote=False)
            tags.append(f'<a href="tg://user?id={uid}">{name}</a>')
    return tags


def is_attack_on() -> bool:
    """Атаки ВКЛ/ВЫКЛ. По умолчанию ВКЛ."""
    try:
        with open(ATTACK_FILE, encoding="utf-8") as f:
            return f.read().strip() != "off"
    except FileNotFoundError:
        return True


def set_attack(on: bool) -> None:
    with open(ATTACK_FILE, "w", encoding="utf-8") as f:
        f.write("on" if on else "off")
    print(f"Атаки: {'ВКЛ' if on else 'ВЫКЛ'}")


def is_channel_on(channel: str) -> bool:
    """Проверяет, включён ли конкретный канал. По умолчанию ВКЛ."""
    try:
        with open(f"{STATE_DIR}/{channel}.txt", encoding="utf-8") as f:
            return f.read().strip() != "off"
    except FileNotFoundError:
        return True


def set_channel_on(channel: str, on: bool) -> None:
    """Включает или выключает конкретный канал."""
    with open(f"{STATE_DIR}/{channel}.txt", "w", encoding="utf-8") as f:
        f.write("on" if on else "off")
    print(f"Канал {channel}: {'ВКЛ' if on else 'ВЫКЛ'}")


REMIND_FILE = f"{STATE_DIR}/remind.txt"
DEFAULT_REMIND_MIN = 5
USERBOT_API_ID = 0
USERBOT_API_HASH_FILE = "/root/kazahstanos/projects/slay_userbot/.api_hash"
USERBOT_SESSION_DIR = "/root/kazahstanos/projects/slay_userbot"


def get_remind_minutes() -> int:
    try:
        with open(REMIND_FILE, encoding="utf-8") as f:
            raw = f.read().strip()
        val = int(raw)
        return val if val > 0 else DEFAULT_REMIND_MIN
    except (FileNotFoundError, ValueError):
        return DEFAULT_REMIND_MIN


def set_remind_minutes(minutes: int) -> None:
    with open(REMIND_FILE, "w", encoding="utf-8") as f:
        f.write(str(minutes))
    print(f"Интервал напоминалок: {minutes} мин")


def last_info() -> dict:
    try:
        with open(LAST_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


MUTED_FILE = f"{STATE_DIR}/muted.json"


def load_muted() -> dict:
    """{chat_id_str: [user_id, ...]} — кто попросил не тегать."""
    try:
        with open(MUTED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_muted(d: dict) -> None:
    with open(MUTED_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def is_muted(chat_id: int | str, user_id: int) -> bool:
    m = load_muted().get(str(chat_id), [])
    return int(user_id) in [int(x) for x in m]


def set_muted(chat_id: int | str, user_id: int, on: bool) -> bool:
    """Поменять состояние мута. Возвращает итог: True если муть включён."""
    m = load_muted()
    cid = str(chat_id)
    arr = [int(x) for x in m.get(cid, [])]
    uid = int(user_id)
    if on:
        if uid not in arr:
            arr.append(uid)
        result = True
    else:
        arr = [x for x in arr if x != uid]
        result = False
    if arr:
        m[cid] = arr
    else:
        m.pop(cid, None)
    save_muted(m)
    return result


@dp.my_chat_member()
async def on_added(event: ChatMemberUpdated):
    """Бота кинули в группу — сразу регистрируем, без /start."""
    try:
        status = event.new_chat_member.status
    except Exception:
        return
    if status not in ("member", "administrator", "creator"):
        # бота выкинули/понизили — отписываем
        g = load_groups()
        if str(event.chat.id) in g:
            del g[str(event.chat.id)]
            save_groups(g)
            print(f"Бота убрали из {event.chat.id}, отписал.")
        return
    g = load_groups()
    cid = str(event.chat.id)
    if cid not in g:
        g[cid] = {"count": DEFAULT_COUNT, "title": event.chat.title or cid}
        save_groups(g)
        print(f"Бота добавили в группу {cid} ({event.chat.title}), зарегистрировал.")
    # собираем список каналов из всех крутящихся процессов следилок (по env HERMES_CHANNEL)
    # для универсального приветствия читаем процессы attack_watch.py
    channels = _watched_channels()
    if not channels:
        channels_str = "@slay_awards"
    elif len(channels) == 1:
        channels_str = f"@{channels[0]}"
    else:
        channels_str = ", ".join(f"@{c}" for c in channels)
    try:
        await bot.send_message(
            event.chat.id,
            "🔥 <b>Боевой бот на связи!</b>\n\n"
            f"Слежу за: {channels_str}.\n"
            f"На новый пост кидаю сюда пасты пачками (сейчас по {g[cid]['count']} шт).\n\n"
            "<b>Команды:</b>\n"
            "/setcount N — сколько черновиков (1–20).\n"
            "/call on|off — авто-зазывалка при атаке.\n"
            "/remind N — интервал напоминалок (мин).\n"
            "/setthread 1220 — привязка к теме форума.\n"
            "/status — что сейчас на прицеле.\n"
            "/stop — отписаться.",
            parse_mode="HTML",
        )
    except Exception as err:
        print(f"Привет в {cid} не ушёл: {err}")


def _watched_channels() -> list[str]:
    """Возвращает список каналов, за которыми следят запущенные процессы attack_watch.py.
    Достаём через psutil если есть, иначе перебираем known."""
    chans = ["slay_awards"]
    try:
        import os, subprocess
        out = subprocess.check_output(
            ["pgrep", "-af", "attack_watch.py"], text=True, timeout=5,
        )
        seen = set()
        for line in out.splitlines():
            if "HERMES_CHANNEL=" in line:
                kv = line.split("HERMES_CHANNEL=")[1].split()[0]
                if kv and kv not in seen:
                    seen.add(kv)
                    chans.append(kv)
    except Exception:
        pass
    return chans


@dp.message(CommandStart())
async def cmd_start(message: Message):
    # личка — как первый бот: подписка на черновики + помощь
    if message.chat.type == "private":
        if not base.is_allowed(message):
            await message.answer(base.REFUSE_TEXT)
            return
        base.save_sub(message.chat.id)
        await message.answer(
            "Здарова, бро! 👋\n"
            "Я штампую пасты по шаблону с созывом на атаку. 🔥\n\n"
            "• Кидай пост (или пересылай из канала) — дам готовую пасту.\n\n"
            "Для группы: добавь меня в группу и жми /start там — "
            "буду кидать туда пасты пачками на каждый новый пост @slay_awards. 👀\n"
            "• /setcount N — сколько паст кидать (1–20).\n"
            "• /status — что на прицеле. /stop — отписаться."
        )
        return
    # группа — регистрация на атаку
    g = load_groups()
    cid = str(message.chat.id)
    if cid not in g:
        g[cid] = {"count": DEFAULT_COUNT, "title": message.chat.title or message.chat.first_name or cid}
        save_groups(g)
        print(f"Новая группа на атаке: {cid}")
    await message.answer(
        "🔥 Боевой бот на связи!\n\n"
        "Как работаю:\n"
        "• Палю новые посты в @slay_awards.\n"
        f"• На новый пост кидаю сюда черновики (сейчас по {g[cid]['count']} шт) — разбирайте в комменты.\n"
        f"• Каждые {get_remind_minutes()} мин напоминаю: пора атаковать — пока не выйдет новый пост. Интервал меняется через /remind N.\n\n"
        "Команды:\n"
        "/setcount N — сколько черновиков кидать (1–20, только свои).\n"
        "/remind N — интервал напоминалок в минутах (1–1440).\n"
        "/status — что сейчас на прицеле.\n"
        "/stop — отписаться."
    )


@dp.message(Command("setcount"))
async def cmd_setcount(message: Message):
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit() or not (1 <= int(parts[1]) <= 20):
        await message.answer("Пиши так: /setcount 5 (от 1 до 20).")
        return
    g = load_groups()
    cid = str(message.chat.id)
    if cid not in g:
        g[cid] = {"count": DEFAULT_COUNT, "title": message.chat.title or cid}
    g[cid]["count"] = int(parts[1])
    save_groups(g)
    await message.answer(f"Принято, бро! Теперь кидаю по {parts[1]} черновиков на пост. 🔥")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    g = load_groups()
    cid = str(message.chat.id)
    count = g.get(cid, {}).get("count", DEFAULT_COUNT)
    remind_min = get_remind_minutes()
    import time
    channels = ["slay_awards", "streaminside", "BotovodX"]
    lines = []
    for ch in channels:
        fn = f"{STATE_DIR}/last_{ch}.json" if ch != "slay_awards" else f"{STATE_DIR}/last.json"
        try:
            with open(fn, encoding="utf-8") as f:
                info = json.load(f)
        except (FileNotFoundError, ValueError):
            info = {}
        if not info.get("post_id"):
            lines.append(f"• @{ch}: постов пока не было.")
            continue
        ago = int((time.time() - info.get("post_time", time.time())) // 60)
        state = "🔥" if is_channel_on(ch) else "🔴"
        lines.append(
            f"{state} @{ch}: https://t.me/{ch}/{info.get('post_id')} "
            f"({ago} мин назад, напоминалок: {info.get('reminders', 0)})")
    await message.answer(
        "🎯 Последние посты:\n" + "\n".join(lines) + "\n\n"
        f"Черновиков на пост: {count}.\n"
        f"Напоминалка каждые: {remind_min} мин (/remind N — поменять).\n"
        f"Атаки: {'🔥 ВКЛ' if is_attack_on() else '🔴 ВЫКЛ'}.\n"
        f"Авто-тег всех: {'📢 ВКЛ' if is_callall_on() else '🔕 ВЫКЛ'} (/autocall)."
    )


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    g = load_groups()
    cid = str(message.chat.id)
    if cid in g:
        del g[cid]
        save_groups(g)
    await message.answer("Отписал, атак больше не будет. Возвращайся через /start. 🤝")


@dp.message(Command("mute"))
async def cmd_mute(message: Message):
    """Выйти из призыва: /mute. Тебя больше не будут тегать @all и в авто-callall."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда для групп — тут и мьючу. 👥")
        return
    if not message.from_user:
        return
    uid = message.from_user.id
    now_muted = set_muted(message.chat.id, uid, True)
    if now_muted:
        await message.answer("🔕 Готово, мьючу тебя. Тебя больше не тегаю в призывах (@callall, авто-callall).\n"
                             "Вернуться: /unmute")
    else:
        await message.answer("Ты уже в муте. Вернуться: /unmute")


@dp.message(Command("muted"))
async def cmd_muted_list(message: Message):
    """Список тех, кто попросил не тегать (только владельцу/админу для контроля)."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда для групп. 👥")
        return
    # простая защита: только админы чата или владелец из whitelist
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    cid = str(message.chat.id)
    muted_ids = [int(x) for x in load_muted().get(cid, [])]
    if not muted_ids:
        await message.answer("✅ Никто не в муте — всех тегаю в призывах.")
        return
    # пытаемся достать имена по user_id
    lines = []
    for uid in muted_ids:
        try:
            m = await bot.get_chat_member(message.chat.id, uid)
            u = m.user
            name = (u.full_name or u.username or "боец")[:40]
            lines.append(f"• {name} (id <code>{uid}</code>)")
        except Exception:
            lines.append(f"• id <code>{uid}</code> (не в чате?)")
    await message.answer(
        f"🔕 В муте в этом чате: {len(muted_ids)} чел.\n\n" + "\n".join(lines),
        parse_mode="HTML",
    )


@dp.message(Command("unmute"))
async def cmd_unmute(message: Message):
    """Вернуться в призыв: /unmute. Снова будешь в @callall и авто-callall."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда для групп. 👥")
        return
    if not message.from_user:
        return
    uid = message.from_user.id
    now_muted = set_muted(message.chat.id, uid, False)
    if not now_muted:
        await message.answer("🔔 Снова в строю. Теперь тебя тегаю в призывах.\n"
                             "Отписаться: /mute")
    else:
        await message.answer("Ты и так не в муте. Отписаться: /mute")


# === КОРОТКИЕ АЛИАСЫ ДЛЯ МОДА ===

@dp.message(Command("call"))
async def cmd_call_short(message: Message):
    """Короткий алиас /autocall: /call on|off — рубильник авто-зазывалки при атаке."""
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    parts = (message.text or "").split()
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_callall(on)
    else:
        on = not is_callall_on()
        set_callall(on)
    await message.answer(
        "📢 Зазывалка ВКЛ — на новый пост сразу сбор всех." if on
        else "🔕 Зазывалка ВЫКЛ — только ручной /callall. Включить: /call on")


async def _resolve_target_user(message: Message) -> tuple[int, str] | None:
    """Достаём user_id и имя из реплая, аргумента @username или числового id."""
    # 1) реплай
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        if not u.is_bot:
            return u.id, u.full_name or u.username or str(u.id)
    # 2) число в аргументе
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) >= 2:
        arg = parts[1].strip()
        if arg.isdigit():
            uid = int(arg)
            try:
                m = await bot.get_chat_member(message.chat.id, uid)
                if m.user and not m.user.is_bot:
                    return uid, m.user.full_name or m.user.username or str(uid)
                return uid, str(uid)
            except Exception:
                return uid, str(uid)
    return None


@dp.message(Command("muteuser"))
async def cmd_muteuser(message: Message):
    """Мод: замутить юзера — не тегать в призывах. /muteuser (реплай) или /muteuser 123456789."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда для групп. 👥")
        return
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    target = await _resolve_target_user(message)
    if not target:
        await message.answer("Кинь реплай на сообщение юзера или /muteuser 123456789 (id).")
        return
    uid, name = target
    set_muted(message.chat.id, uid, True)
    await message.answer(f"🔕 Замутил <b>{htmlmod.escape(name, quote=False)}</b> — не тегаю в призывах.\n"
                         f"Вернуть: /unmuteuser (реплай или id)", parse_mode="HTML")


@dp.message(Command("unmuteuser"))
async def cmd_unmuteuser(message: Message):
    """Мод: снять мут с юзера. /unmuteuser (реплай) или /unmuteuser 123456789."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда для групп. 👥")
        return
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    target = await _resolve_target_user(message)
    if not target:
        await message.answer("Кинь реплай на сообщение юзера или /unmuteuser 123456789 (id).")
        return
    uid, name = target
    set_muted(message.chat.id, uid, False)
    await message.answer(f"🔔 Снял мут с <b>{htmlmod.escape(name, quote=False)}</b> — снова в призывах.",
                         parse_mode="HTML")


@dp.message((F.text | F.caption), (F.text.regexp(r'^(?!/)') | F.caption.regexp(r'^(?!/)')))
async def handle_text(message: Message):
    """Только пасты по шаблону с созывом на атаку. Текст НЕ должен начинаться с /.
    Регексп '^(?!/)' отсекает команды — /remind и прочие уйдут в свои хендлеры."""
    if message.chat.type != "private":
        return
    if not base.is_allowed(message):
        await message.reply(base.REFUSE_TEXT)
        return
    post_text = message.text or message.caption
    if not post_text:
        await message.reply("⚠️ Пустое сообщение, кинь текст поста. 🤔")
        return
    base.save_sub(message.chat.id)
    # пост (пересланный или длинный) -> коммент-паста как в первом боте
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        ai_reply = base.chat_with_failover(
            messages=[
                {"role": "system", "content": (
                    "Ты активный комментатор в Telegram. "
                    "Прочитай пост и напиши живой короткий комментарий к нему (1-2 предложения). "
                    "Пиши ЕСТЕСТВЕННО, как обычный живой человек — без штампов 'кстати/в тему/а раз уж заговорили'. "
                    "Не подводи к рекламе и не заканчивай фразой про музыку — коммент и реклама склеятся снаружи. "
                    "Засыпай текст смайликами и эмодзи — минимум 6 штук, в каждом предложении. "
                    "Текст должен выглядеть ярко и живо. "
                    "Отвечай ТОЛЬКО текстом комментария, без вводных фраз и без оформления.")},
                {"role": "user", "content": post_text},
            ],
            max_tokens=1500,
            temperature=1.1,
        )
        if not ai_reply:
            ai_reply = "Залетел пост — вайб годный, читается на одном дыхании."
        final_text = f"{ai_reply}{random.choice(base.AD_VARIANTS)}{base.SIGN}"
        await message.reply(
            f"<pre>{htmlmod.escape(final_text, quote=False)}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.reply(f"Произошла ошибка при обращении к ИИ: {e}")


@dp.message(Command("attack"))
async def cmd_attack(message: Message):
    """Рубильник атак: /attack, /attack on, /attack off."""
    parts = (message.text or "").split()
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_attack(on)
    else:
        on = not is_attack_on()
        set_attack(on)
    await message.answer(
        "🔥 Атаки ВКЛЮЧЕНЫ — бью по новым постам." if on
        else "🔴 Атаки ВЫКЛЮЧЕНЫ — молчу, только слежу.")


@dp.message(Command("slayattack"))
async def cmd_slayattack(message: Message):
    """Рубильник атак от @slay_awards: /slayattack, /slayattack on, /slayattack off."""
    parts = (message.text or "").split()
    channel = "slay_awards"
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_channel_on(channel, on)
    else:
        on = not is_channel_on(channel)
        set_channel_on(channel, on)
    await message.answer(
        f"🔥 Атаки от @slay_awards ВКЛЮЧЕНЫ — бью по новым постам." if on
        else f"🔴 Атаки от @slay_awards ВЫКЛЮЧЕНЫ — молчу, только слежу.")


@dp.message(Command("siattack"))
async def cmd_siattack(message: Message):
    """Рубильник атак от @streaminside: /siattack, /siattack on, /siattack off."""
    parts = (message.text or "").split()
    channel = "streaminside"
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_channel_on(channel, on)
    else:
        on = not is_channel_on(channel)
        set_channel_on(channel, on)
    await message.answer(
        f"🔥 Атаки от @streaminside ВКЛЮЧЕНЫ — бью по новым постам." if on
        else f"🔴 Атаки от @streaminside ВЫКЛЮЧЕНЫ — молчу, только слежу.")


@dp.message(Command("botovattack"))
async def cmd_botovattack(message: Message):
    """Рубильник атак от @BotovodX: /botovattack, /botovattack on, /botovattack off."""
    parts = (message.text or "").split()
    channel = "BotovodX"
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_channel_on(channel, on)
    else:
        on = not is_channel_on(channel)
        set_channel_on(channel, on)
    await message.answer(
        f"🔥 Атаки от @BotovodX ВКЛЮЧЕНЫ — бью по новым постам." if on
        else f"🔴 Атаки от @BotovodX ВЫКЛЮЧЕНЫ — молчу, только слежу.")


@dp.message(Command("attackmode"))
async def cmd_attackmode(message: Message):
    """Общий рубильник атак: /attackmode, /attackmode on, /attackmode off."""
    parts = (message.text or "").split()
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_attack(on)
        # также включаем/выключаем все каналы
        set_channel_on("slay_awards", on)
        set_channel_on("streaminside", on)
        set_channel_on("BotovodX", on)
    else:
        on = not is_attack_on()
        set_attack(on)
        set_channel_on("slay_awards", on)
        set_channel_on("streaminside", on)
        set_channel_on("BotovodX", on)
    await message.answer(
        "🔥 Общий режим атак ВКЛЮЧЕН — бью по всем новым постам." if on
        else "🔴 Общий режим атак ВЫКЛЮЧЕН — молчу, только слежу.")


@dp.message(Command("remind"))
async def cmd_remind(message: Message):
    """Интервал напоминалок в минутах: /remind, /remind N (1-1440)."""
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            f"Сейчас напоминаю каждые {get_remind_minutes()} мин. "
            "Поменять: /remind N (от 1 до 1440 мин). 0 — вырубить напоминалки.")
        return
    if not parts[1].isdigit():
        await message.answer("Пиши число минут, например: /remind 10")
        return
    n = int(parts[1])
    if n < 0 or n > 1440:
        await message.answer("Давай от 0 до 1440 (это сутки). /remind 10")
        return
    if n == 0:
        # удаляем файл = дефолт (5 мин). Чтобы реально вырубить, пишем 999999 или юзаем /attack off
        set_remind_minutes(1)  # минимум = 1 мин, по сути прижато к полу
        await message.answer("Напоминалки прижаты к минимуму (1 мин). Чтобы вырубить совсем — /attack off.")
        return
    set_remind_minutes(n)
    await message.answer(f"✅ Принято, напоминаю каждые {n} мин. Следилка подхватит на следующем цикле (≤60 сек).")


CALLALL_FILE = f"{STATE_DIR}/callall.txt"


def is_callall_on() -> bool:
    """Авто-тег всех при новой атаке. По дефолту ВЫКЛ."""
    try:
        with open(CALLALL_FILE, encoding="utf-8") as f:
            return f.read().strip().lower() == "on"
    except FileNotFoundError:
        return False


def set_callall(on: bool) -> None:
    with open(CALLALL_FILE, "w", encoding="utf-8") as f:
        f.write("on" if on else "off")
    print(f"Авто-callall при атаке: {'ВКЛ' if on else 'ВЫКЛ'}")


@dp.message(Command("autocall"))
async def cmd_autocall(message: Message):
    """Рубильник авто-тега всех при новой атаке: /autocall, /autocall on, /autocall off.
    ВКЛ = на КАЖДЫЙ новый пост в @slay_awards бот сразу пингует ВСЕХ участников группы."""
    if not base.is_allowed(message):
        await message.answer(base.REFUSE_TEXT)
        return
    parts = (message.text or "").split()
    if len(parts) >= 2 and parts[1].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
        on = parts[1].lower() in ("on", "вкл", "1")
        set_callall(on)
    else:
        on = not is_callall_on()
        set_callall(on)
    await message.answer(
        "📢 Авто-тег ВСЕХ при атаке ВКЛЮЧЁН — на новый пост сразу сбор всех." if on
        else "🔕 Авто-тег ВЫКЛЮЧЁН — только ручной /callall. Используй /autocall когда надо.")


@dp.message(Command("setthread"))
async def cmd_setthread(message: Message):
    """Привязка к теме форума: /setthread 1220 или /setthread https://t.me/c/4365297986/1220. /setthread general — обратно в общую."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда только для групп. 👥")
        return
    import re as _re
    arg = (message.text or "").split(maxsplit=1)
    g = load_groups()
    cid = str(message.chat.id)
    cfg = g.setdefault(cid, {"count": DEFAULT_COUNT, "title": message.chat.title or cid})
    if len(arg) < 2 or arg[1].lower() in ("general", "общая", "0"):
        cfg.pop("thread", None)
        save_groups(g)
        await message.answer("Пишу в общую тему (General). ✅")
        return
    m = _re.search(r"(\d{1,10})", arg[1])
    if not m:
        await message.answer("Пиши так: /setthread 1220 или кинь ссылку на тему. ✅")
        return
    cfg["thread"] = int(m.group(1))
    save_groups(g)
    await message.answer(f"Привязал к теме {m.group(1)} ✅ Атаки полетят туда.")


async def userbot_get_members(chat_id: int) -> list[int] | None:
    """Достаём ВСЕХ участников группы через юзербот (Telethon). None = юзербот не настроен."""
    try:
        import os
        # импортируем telethon из venv юзербота
        import sys
        sys.path.insert(0, "/root/kazahstanos/projects/slay_userbot/venv/lib/python3.11/site-packages")
        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsSearch
        if not os.path.exists(USERBOT_API_HASH_FILE):
            return None
        # ищем любую .session в папке юзербота
        sess = None
        for fn in os.listdir(USERBOT_SESSION_DIR):
            if fn.endswith(".session"):
                sess = os.path.join(USERBOT_SESSION_DIR, fn[:-len(".session")])
                break
        if not sess:
            return None
        with open(USERBOT_API_HASH_FILE) as f:
            api_hash = f.read().strip()
        client = TelegramClient(sess, USERBOT_API_ID, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        try:
            entity = await client.get_entity(chat_id)
            result = await client(GetParticipantsRequest(
                channel=entity,
                filter=ChannelParticipantsSearch(""),
                offset=0,
                limit=200,
                hash=0,
            ))
            uids = [u.user_id for u in result.users if not getattr(u, "bot", False)]
            while len(uids) < result.count and len(uids) < 1000:
                result = await client(GetParticipantsRequest(
                    channel=entity,
                    filter=ChannelParticipantsSearch(""),
                    offset=len(uids),
                    limit=200,
                    hash=0,
                ))
                uids += [u.user_id for u in result.users if not getattr(u, "bot", False)]
        except Exception as e:
            print(f"userbot_get_members {chat_id}: {e}")
            await client.disconnect()
            return None
        await client.disconnect()
        return uids
    except Exception as e:
        print(f"userbot init: {e}")
        return None


@dp.message(Command("callall"))
async def cmd_callall(message: Message):
    """Cobot-style @all по ZazyvalaTag2Bot: тегает всех кто когда-либо писал в группе.
    Если есть @username — тег текстом (прилетит уведом), иначе кликабельная ссылка."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команда только для групп — там и зову всех. 👥")
        return
    remember_user(message.chat.id, message.from_user)
    cid = str(message.chat.id)
    parts = (message.text or "").split(maxsplit=1)
    extra = parts[1].strip() if len(parts) > 1 else "Все на атаку! 🔥"

    # 1) пытаемся юзербота — он видит ВСЕХ
    uids_full = await userbot_get_members(message.chat.id)
    if uids_full:
        # юзербот оффлайн → но юзербот видел их. В этом случае у нас нет имён/username,
        # поэтому лучше fallback на базу users.json
        source = f"юзербот видит {len(uids_full)} чел. (но без имён — беру базу)"
    else:
        source = "база users.json"

    # 2) собираем теги по базе
    tags = build_tags_from_users(cid)
    if not tags:
        await message.answer(
            "Пока некого звать — никто не писал в группе при мне. "
            "Попроси людей кинуть любое сообщение, или подними юзербот."
        )
        return

    # 3) выкидываем мьютнутых по @username (если uid есть в muted.json)
    muted_now = [int(x) for x in load_muted().get(cid, [])]
    users_here = load_users().get(cid, {})
    # получаем uid для каждого тега чтобы фильтровать мутнутых
    # проще: перестроим tags уже с учётом мута
    final_tags: list[str] = []
    for tag, uid_key in zip(tags, users_here.keys()):
        try:
            uid_int = int(uid_key) if not uid_key.startswith("u_") else None
        except ValueError:
            uid_int = None
        if uid_int and uid_int in muted_now:
            continue
        final_tags.append(tag)
    skipped = len(tags) - len(final_tags)

    if not final_tags:
        await message.answer("Все замучены. Сними мут через /unmuteuser.")
        return

    # 4) разбиваем по 25 (лимит Telegram на теги в одном сообщении)
    CHUNK = 25
    chunks = [final_tags[i:i + CHUNK] for i in range(0, len(final_tags), CHUNK)]
    sent = 0
    for i, chunk in enumerate(chunks, 1):
        if i == 1:
            text = f"📢 <b>{extra}</b>\n\n" + " ".join(chunk)
        else:
            text = " ".join(chunk)
        try:
            await bot.send_message(message.chat.id, text, parse_mode="HTML")
            sent += len(chunk)
            import asyncio as _a
            await _a.sleep(0.5)
        except Exception as e:
            print(f"callall chunk {i}: {e}")
            break

    diag = f"✅ Позвал {sent} чел. ({source}). Сообщений: {len(chunks)}."
    if skipped:
        diag += f" Пропустил {skipped} (в муте)."
    await message.reply(diag)





async def main():
    logging.basicConfig(level=logging.INFO)
    me = await bot.get_me()
    print(f"🚀 Боевой бот запущен: @{me.username} id={me.id}")
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Старт / подключить группу"),
            BotCommand(command="attack", description="Атаки вкл/выкл: /attack"),
            BotCommand(command="slayattack", description="Slay атаки вкл/выкл: /slayattack"),
            BotCommand(command="siattack", description="Streaminside атаки вкл/выкл: /siattack"),
            BotCommand(command="botovattack", description="BotovodX атаки вкл/выкл: /botovattack"),
            BotCommand(command="attackmode", description="Общий режим атак: /attackmode on/off"),
            BotCommand(command="setcount", description="Сколько паст: /setcount N"),
            BotCommand(command="remind", description="Интервал напоминалок: /remind N"),
            BotCommand(command="call", description="Зазывалка при атаке: /call on/off"),
            BotCommand(command="setthread", description="Тема: /setthread 1220"),
            BotCommand(command="callall", description="Cobot @all: /callall текст"),
            BotCommand(command="mute", description="Выйти из призыва @all"),
            BotCommand(command="unmute", description="Вернуться в призыв @all"),
            BotCommand(command="muted", description="Кто в муте (для админа)"),
            BotCommand(command="muteuser", description="Мод: замутить юзера"),
            BotCommand(command="unmuteuser", description="Мод: снять мут"),
            BotCommand(command="status", description="Что на прицеле"),
            BotCommand(command="stop", description="Отписаться"),
        ])
    except Exception as err:
        print(f"Меню не встало: {err}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


# === Запоминание юзеров в группе — В САМОМ КОНЦЕ, чтоб команды шли первыми ===
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def record_group_user(message: Message):
    """ZazyvalaTag2Bot-стиль: запоминаем всех кто пишет в группе — потом тегаем в callall.
    Стоит самым последним, чтоб команды (/remind, /attack и т.д.) обрабатывались раньше."""
    if message.from_user:
        remember_user(message.chat.id, message.from_user)
