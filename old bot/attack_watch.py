"""Следилка боевого бота: новый пост -> атака (N черновиков).
Плюс напоминалка каждые N минут (настраивается в remind.txt, по умолчанию 5).
Теги убраны — бот молча шлёт черновики, никого не тегает.

CHANNEL читается из env HERMES_CHANNEL — можно запустить второй процесс под другой канал."""
import asyncio
import html as htmlmod
import json
import logging
import os
import sys
import time

sys.path.insert(0, "/root/kazahstanos/projects/slay4242bot")
import bot as base
# читаем тот же CHANNEL, что и watcher.py (по env)
from watcher import parse_posts, fetch_preview, make_comment, CHANNEL as _WATCH_CHANNEL

from aiogram import Bot

TOKEN = "8845089665:***"
STATE_DIR = "/root/kazahstanos/projects/attack3v1r1b42pbot"
GROUPS_FILE = f"{STATE_DIR}/groups.json"
CHANNEL = os.environ.get("HERMES_CHANNEL", _WATCH_CHANNEL)
LAST_FILE = f"{STATE_DIR}/last_{CHANNEL}.json" if CHANNEL != "slay_awards" else f"{STATE_DIR}/last.json"
POLL_SEC = 60
DEFAULT_REMIND_MIN = 5  # дефолт если remind.txt пуст/битый
REMIND_FILE = f"{STATE_DIR}/remind.txt"
CALLALL_FILE = f"{STATE_DIR}/callall.txt"  # если "on" — тегаем всех при новой атаке

tg = Bot(token=TOKEN)


def load_groups() -> dict:
    try:
        with open(GROUPS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def load_last() -> dict:
    try:
        with open(LAST_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_last(d: dict) -> None:
    with open(LAST_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def is_attack_on() -> bool:
    """Атаки ВКЛ/ВЫКЛ. По умолчанию ВКЛ."""
    try:
        with open(f"{STATE_DIR}/attack.txt", encoding="utf-8") as f:
            global_attack = f.read().strip() != "off"
    except FileNotFoundError:
        global_attack = True

    # Проверяем конкретный канал
    try:
        with open(f"{STATE_DIR}/{CHANNEL}.txt", encoding="utf-8") as f:
            channel_attack = f.read().strip() != "off"
    except FileNotFoundError:
        channel_attack = True

    return global_attack and channel_attack


def get_remind_minutes() -> int:
    """Интервал напоминалок в минутах. Хранится в remind.txt, дефолт 5."""
    try:
        with open(REMIND_FILE, encoding="utf-8") as f:
            raw = f.read().strip()
        val = int(raw)
        return val if val > 0 else DEFAULT_REMIND_MIN
    except (FileNotFoundError, ValueError):
        return DEFAULT_REMIND_MIN


def is_callall_on() -> bool:
    """Тегать ли всех при новой атаке. По умолчанию ВЫКЛ — только ручной /callall."""
    try:
        with open(CALLALL_FILE, encoding="utf-8") as f:
            return f.read().strip().lower() == "on"
    except FileNotFoundError:
        return False


def link(pid: int) -> str:
    return f"https://t.me/{CHANNEL}/{pid}"


async def attack(pid: int, post_text: str) -> None:
    groups = load_groups()
    if not groups:
        print(f"Пост {pid} есть, но групп нет — молчу.")
        return
    for cid, cfg in groups.items():
        count = max(1, min(20, int(cfg.get("count", 5))))
        thread = cfg.get("thread")  # тема форума, None = общая
        kwargs = {"message_thread_id": thread} if thread else {}
        try:
            await tg.send_message(
                cid,
                f"🔥 АТАКА! Новый пост: {link(pid)}\n\n"
                f"Кидаю {count} черновиков — разбирайте в комменты!{base.SIGN}",
                parse_mode="HTML", **kwargs)
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
                        # фильтруем мьютнутых
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
        except Exception as err:
            print(f"Напоминалка в {cid} не ушла: {err}")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    last = load_last()
    first = not last
    posts = parse_posts(fetch_preview())
    if first:
        ids = [pid for pid, _ in posts]
        last = {"post_id": max(ids) if ids else 0, "post_time": time.time(), "reminders": 0}
        save_last(last)
        print(f"👀 Боевая следилка стартовала, запомнил {len(ids)} постов, бью только по новым.")
    else:
        print(f"👀 Боевая следилка стартовала, последний пост {last.get('post_id')}.")
    while True:
        try:
            last = load_last()
            posts = parse_posts(fetch_preview())
            fresh = sorted([(pid, t) for pid, t in posts if pid > int(last.get("post_id", 0))])
            if fresh:
                for pid, post_text in fresh:
                    if not is_attack_on():
                        print(f"Пост {pid} новый, но атаки ВЫКЛ — молчу, только запоминаю.")
                    else:
                        print(f"НОВЫЙ ПОСТ {pid} — атака!")
                        await attack(pid, post_text)
                    last = {"post_id": pid, "post_time": time.time(), "reminders": 0}
                    save_last(last)
            else:
                # тихо: проверяем таймер напоминалки (настраивается через /remind N)
                if last.get("post_id"):
                    remind_min = get_remind_minutes()
                    elapsed = time.time() - last.get("post_time", time.time())
                    need = int(elapsed // (remind_min * 60))
                    sent = int(last.get("reminders", 0))
                    if need > sent:
                        if not is_attack_on():
                            print(f"Таймер {need * remind_min} мин, но атаки ВЫКЛ — молчу.")
                            last["reminders"] = need
                            save_last(last)
                        else:
                            minutes = need * remind_min
                            print(f"Таймер: {minutes} мин с поста {last['post_id']} — напоминаю.")
                            await remind(int(last["post_id"]), minutes)
                            last["reminders"] = need
                            save_last(last)
                    else:
                        print(f"Тихо ({time.strftime('%H:%M:%S')}), пост {last.get('post_id')}, ждём {remind_min} мин.")
                else:
                    print(f"Тихо ({time.strftime('%H:%M:%S')}), постов ещё не было.")
        except Exception as err:
            print(f"Цикл боевой следилки: {err}")
        await asyncio.sleep(POLL_SEC)


if __name__ == "__main__":
    asyncio.run(main())
