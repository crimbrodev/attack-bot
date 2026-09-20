"""Следилка боевого бота: новый пост → атака (N черновиков).
Плюс напоминалка каждые N минут (настраивается через remind.txt, по умолчанию 5).
Теги убраны — бот молча шлёт черновики, никого не тегает.

CHANNEL читается из env HERMES_CHANNEL — можно запустить второй процесс под другой канал."""
import asyncio
import html as htmlmod
import logging
import os
import random
import sys
import time

import base
from watcher import parse_posts, fetch_preview, make_comment, DEFAULT_CHANNEL as _WATCH_CHANNEL

from aiogram import Bot

from config import BOT_TOKEN, POLL_SEC, MAX_GROUP_ATTEMPTS, WARNING_THRESHOLD
from storage import (
    load_groups, load_last, save_last,
    is_attack_on, get_remind_minutes, is_callall_on,
    increment_group_errors, reset_group_errors, remove_group,
    build_tags_from_users, load_muted, load_users,
    get_general_chat, is_warnings_on,
)

CHANNEL = os.environ.get("HERMES_CHANNEL", _WATCH_CHANNEL)

def setup_logging(name: str = "watcher") -> None:
    """Настройка логирования с ротацией файлов."""
    from logging.handlers import RotatingFileHandler
    from config import STATE_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT
    log_file = STATE_DIR / f"{name}.log"
    handler = RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


tg = Bot(token=BOT_TOKEN)


def link(pid: int) -> str:
    return f"https://t.me/{CHANNEL}/{pid}"


async def attack(pid: int, post_text: str) -> None:
    groups = load_groups()
    if not groups:
        print(f"Пост {pid} есть, но групп нет — молчу.")
        return
    for cid, cfg in groups.items():
        count = max(1, min(20, int(cfg.get("count", 5))))
        thread = cfg.get("thread")
        kwargs = {"message_thread_id": thread} if thread else {}
        try:
            await tg.send_message(
                cid,
                f"🔥 АТАКА! Новый пост: {link(pid)}\n\n"
                f"Кидаю {count} черновиков — разбирайте в комменты!{base.SIGN}",
                parse_mode="HTML", **kwargs)
            reset_group_errors(cid)
            for i in range(1, count + 1):
                try:
                    comment = make_comment(post_text)
                    final_text = f"{comment}{base.SIGN}"
                except Exception as err:
                    print(f"Грок упал ({pid} #{i}): {err}")
                    continue
                safe = htmlmod.escape(final_text, quote=False)
                await tg.send_message(
                    cid,
                    f"✍️ Черновик №{i} (жми значок копирования):\n<pre>{safe}</pre>",
                    parse_mode="HTML", **kwargs)
                await asyncio.sleep(2)  # пауза между черновиками чтобы Groq не задdosили
            # если включён авто-callall — сразу пингуем всех (ZazyvalaStyle)
            if is_callall_on():
                try:
                    import random as _rnd
                    from storage import load_muted, load_users, get_call_setting
                    ALL_EMOJIS = ["🥢", "🧎🏿‍♂️", "👜", "🧚🏻‍♂️", "🐯", "👩🏽‍⚖️", "🫱🏼", "👨🏾‍🦳", "🤘🏼", "👨🏽‍⚕️",
                              "🧨", "⛄️", "😉", "🙍🏽‍♂️", "👩🏽‍🎤", "👩🏽‍🚒", "🙋🏽‍♂️", "🤩", "⛹🏻‍♂", "🚃",
                              "🏋🏻‍♀", "🦈", "🙋🏻‍♀️", "🏋‍♀", "👩🏻‍💻", "💏", "👨🏾‍✈️", "👴🏻", "🕵️‍♀️",
                              "🎉", "🔥", "💪", "⚡️", "🚀", "💣", "👀", "🎭", "🪅", "🎯",
                              "🎲", "🪩", "🧸", "🎀", "🎁", "🎄", "🎰", "🔮", "🧿", "🪬"]
                    muted_now = [int(x) for x in load_muted().get(cid, [])]
                    users_here = load_users().get(cid, {})
                    active = []
                    for uid, info in users_here.items():
                        try:
                            uid_int = int(uid) if not uid.startswith("u_") else None
                        except ValueError:
                            uid_int = None
                        if uid_int and uid_int in muted_now:
                            continue
                        active.append((uid, info))
                    if active:
                        _rnd.shuffle(active)
                        per_msg = get_call_setting("mentions_per_msg")
                        msg_delay = get_call_setting("msg_delay")
                        emoji_tags = []
                        for uid, info in active:
                            emoji = _rnd.choice(ALL_EMOJIS)
                            emoji_tags.append(f'<a href="tg://user?id={uid}">{emoji}</a>')
                        n_chunks = (len(emoji_tags) + per_msg - 1) // per_msg
                        for ci in range(n_chunks):
                            batch = emoji_tags[ci * per_msg : (ci + 1) * per_msg]
                            emojis_line = "  ".join(batch) + "\u200b"
                            text = f"📢 СБОР! Новый пост вышел, го атаковать!\n\n{emojis_line}"
                            await tg.send_message(int(cid), text, parse_mode="HTML", **kwargs)
                            await asyncio.sleep(msg_delay)
                        await tg.send_message(int(cid), "Призыв окончен.", **kwargs)
                        print(f"callall: позвал {len(active)} эмодзи-пингов в {cid}")
                except Exception as e:
                    print(f"callall {cid}: {e}")
            print(f"Атака ушла в {cid}: пост {pid}, {count} шт.")
        except Exception as err:
            if "Not Found" in str(err):
                errors = increment_group_errors(cid)
                if errors >= MAX_GROUP_ATTEMPTS:
                    remove_group(cid)
                    continue
            print(f"Атака в {cid} не ушла: {err}")

    # Через 2 мин проверяем % и кричим если мало
    # (только для основного канала, чтобы не дублировать от streaminside/BotovodX)
    await asyncio.sleep(120)
    if CHANNEL != "slay_awards":
        return
    try:
        from comments import get_post_commenters, calc_squad_percentage
        commenters = await get_post_commenters(CHANNEL, pid)
        squad_count, total, pct = calc_squad_percentage(commenters, load_users())
        if total > 0 and pct < WARNING_THRESHOLD and is_warnings_on():
            general = get_general_chat()
            if general:
                try:
                    await tg.send_message(
                        general,
                        f"⚠️ <b>ВНИМАНИЕ!</b> Под постом {link(pid)} "
                        f"взвод пишет только {pct:.0f}% комментариев ({squad_count}/{total})!\n\n"
                        f"Цель — минимум {WARNING_THRESHOLD}%! Поднажмите, ребят! 💪🔥",
                        parse_mode="HTML")
                except Exception:
                    pass
    except Exception:
        pass


async def remind(pid: int, minutes: int) -> None:
    from config import ALLOWED_GROUPS
    groups = load_groups()

    # Получаем комментарии и считаем % от взвода
    squad_users = load_users()
    try:
        from comments import get_post_commenters, calc_squad_percentage
        commenters = await get_post_commenters(CHANNEL, pid)
        squad_count, total, pct = calc_squad_percentage(commenters, squad_users)
    except Exception:
        squad_count, total, pct = 0, 0, 0

    pct_text = ""
    if total > 0:
        pct_text = f"\n\n💬 Комментариев: {total}, от взвода: {squad_count} ({pct:.0f}%)"

    for cid, cfg in groups.items():
        # Напоминалки только в разрешённых группах
        if cid not in ALLOWED_GROUPS:
            continue
        thread = cfg.get("thread")
        kwargs = {"message_thread_id": thread} if thread else {}
        try:
            await tg.send_message(
                cid,
                f"⏰ Прошло {minutes} мин с поста — пора АТАКОВАТЬ!\n{link(pid)}{pct_text}{base.SIGN}",
                parse_mode="HTML", **kwargs)
            reset_group_errors(cid)
            # Если взвод пишет меньше 42% — кричим в общий чат (только slay_awards)
            if total > 0 and pct < WARNING_THRESHOLD and is_warnings_on() and CHANNEL == "slay_awards":
                general = get_general_chat()
                if general:
                    try:
                        await tg.send_message(
                            general,
                            f"⚠️ <b>ВНИМАНИЕ!</b> Под постом {link(pid)} "
                            f"взвод пишет только {pct:.0f}% комментариев ({squad_count}/{total})!\n\n"
                            f"Цель — минимум {WARNING_THRESHOLD}%! Поднажмите, ребят! 💪🔥",
                            parse_mode="HTML")
                    except Exception:
                        pass
        except Exception as err:
            if "Not Found" in str(err):
                errors = increment_group_errors(cid)
                if errors >= MAX_GROUP_ATTEMPTS:
                    remove_group(cid)
            print(f"Напоминалка в {cid} не ушла: {err}")


async def main() -> None:
    setup_logging(f"watcher_{CHANNEL}")
    last = load_last(CHANNEL)
    first = not last
    posts = parse_posts(fetch_preview(CHANNEL))
    if first:
        ids = [pid for pid, _ in posts]
        last = {"post_id": max(ids) if ids else 0, "post_time": time.time(), "reminders": 0}
        save_last(CHANNEL, last)
        print(f"👀 Боевая следилка стартовала, запомнил {len(ids)} постов, бью только по новым.")
    else:
        print(f"👀 Боевая следилка стартовала, последний пост {last.get('post_id')}.")
    while True:
        try:
            last = load_last(CHANNEL)
            posts = parse_posts(fetch_preview(CHANNEL))
            fresh = sorted([(pid, t) for pid, t in posts if pid > int(last.get("post_id", 0))])
            if fresh:
                for pid, post_text in fresh:
                    if not is_attack_on(CHANNEL):
                        print(f"Пост {pid} новый, но атаки ВЫКЛ — молчу, только запоминаю.")
                    else:
                        print(f"НОВЫЙ ПОСТ {pid} — атака!")
                        await attack(pid, post_text)
                    last = {"post_id": pid, "post_time": time.time(), "reminders": 0}
                    save_last(CHANNEL, last)
            else:
                # тихо: проверяем таймер напоминалки (настраивается через /remind N)
                if last.get("post_id"):
                    remind_min = get_remind_minutes()
                    elapsed = time.time() - last.get("post_time", time.time())
                    need = int(elapsed // (remind_min * 60))
                    sent = int(last.get("reminders", 0))
                    if need > sent:
                        if not is_attack_on(CHANNEL):
                            print(f"Таймер {need * remind_min} мин, но атаки ВЫКЛ — молчу.")
                            last["reminders"] = need
                            save_last(CHANNEL, last)
                        else:
                            minutes = need * remind_min
                            print(f"Таймер: {minutes} мин с поста {last['post_id']} — напоминаю.")
                            await remind(int(last["post_id"]), minutes)
                            last["reminders"] = need
                            save_last(CHANNEL, last)
                    else:
                        print(f"Тихо ({time.strftime('%H:%M:%S')}), пост {last.get('post_id')}, ждём {remind_min} мин.")
                else:
                    print(f"Тихо ({time.strftime('%H:%M:%S')}), постов ещё не было.")
        except Exception as err:
            print(f"Цикл боевой следилки: {err}")
        await asyncio.sleep(POLL_SEC)


if __name__ == "__main__":
    asyncio.run(main())
