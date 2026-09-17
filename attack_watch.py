"""Следилка боевого бота: новый пост → атака (N черновиков).
Плюс напоминалка каждые N минут (настраивается через remind.txt, по умолчанию 5).
Теги убраны — бот молча шлёт черновики, никого не тегает.

CHANNEL читается из env HERMES_CHANNEL — можно запустить второй процесс под другой канал."""
import asyncio
import html as htmlmod
import logging
import os
import sys
import time

sys.path.insert(0, "/root/kazahstanos/projects/slay4242bot")
import bot as base
from watcher import parse_posts, fetch_preview, make_comment, CHANNEL as _WATCH_CHANNEL

from aiogram import Bot

from config import BOT_TOKEN, POLL_SEC, MAX_GROUP_ATTEMPTS
from storage import (
    load_groups, load_last, save_last,
    is_attack_on, get_remind_minutes, is_callall_on,
    increment_group_errors, reset_group_errors, remove_group,
    build_tags_from_users, load_muted, load_users,
)

CHANNEL = os.environ.get("HERMES_CHANNEL", _WATCH_CHANNEL)

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
                except Exception as err:
                    print(f"Грок упал ({pid} #{i}): {err}")
                    continue
                safe = htmlmod.escape(comment, quote=False)
                await tg.send_message(
                    cid,
                    f"✍️ Черновик №{i} (жми значок копирования):\n<pre>{safe}</pre>",
                    parse_mode="HTML", **kwargs)
            # если включён авто-callall — сразу пингуем всех по базе (ZazyvalaTag2Bot-стиль)
            if is_callall_on():
                try:
                    sys.path.insert(0, "/root/kazahstanos/projects/attack3v1r1b42pbot")
                    from attack_bot import build_tags_from_users, load_muted
                    tags = build_tags_from_users(cid)
                    if tags:
                        muted_now = [int(x) for x in load_muted().get(cid, [])]
                        from attack_bot import load_users
                        users_here = load_users().get(cid, {})
                        final_tags = []
                        for tag, uid_key in zip(tags, users_here.keys()):
                            try:
                                uid_int = int(uid_key) if not uid_key.startswith("u_") else None
                            except ValueError:
                                uid_int = None
                            if uid_int and uid_int in muted_now:
                                continue
                            final_tags.append(tag)
                        if final_tags:
                            CHUNK = 25
                            chunks = [final_tags[i:i + CHUNK] for i in range(0, len(final_tags), CHUNK)]
                            for i2, chunk in enumerate(chunks, 1):
                                if i2 == 1:
                                    text = f"📢 <b>СБОР! Новый пост вышел, го атаковать!</b>\n\n" + " ".join(chunk)
                                else:
                                    text = " ".join(chunk)
                                await tg.send_message(int(cid), text, parse_mode="HTML", **kwargs)
                                await asyncio.sleep(0.5)
                            print(f"callall: пинговано {len(final_tags)} чел. в {cid} (по базе)")
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


async def remind(pid: int, minutes: int) -> None:
    groups = load_groups()
    for cid, cfg in groups.items():
        thread = cfg.get("thread")
        kwargs = {"message_thread_id": thread} if thread else {}
        try:
            await tg.send_message(
                cid,
                f"⏰ Прошло {minutes} мин с поста — пора АТАКОВАТЬ!\n{link(pid)}{base.SIGN}",
                parse_mode="HTML", **kwargs)
            reset_group_errors(cid)
        except Exception as err:
            if "Not Found" in str(err):
                errors = increment_group_errors(cid)
                if errors >= MAX_GROUP_ATTEMPTS:
                    remove_group(cid)
            print(f"Напоминалка в {cid} не ушла: {err}")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    last = load_last(CHANNEL)
    first = not last
    posts = parse_posts(fetch_preview())
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
            posts = parse_posts(fetch_preview())
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
