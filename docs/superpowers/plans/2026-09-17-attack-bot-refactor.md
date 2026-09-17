# Attack Bot Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Модульная рефструктуризация attack_bot + attack_watch: конфигурация из .env, общее хранилище, автоочистка мёртвых групп, ротация логов, безопасность.

**Architecture:** Выносим конфигурацию в `config.py`, хранилище данных в `storage.py`, подключаем `.env` через `python-dotenv`. Бот и следилка используют общие модули. Добавляем автоочистку групп с ошибками и ротацию логов.

**Tech Stack:** Python 3.11+, aiogram, python-dotenv, logging.handlers

---

## File Structure

| File | Responsibility |
|------|---------------|
| `config.py` (create) | Все настройки из .env, константы, пути |
| `storage.py` (create) | Load/save для groups, users, muted, last, attack, callall, remind |
| `attack_bot.py` (modify) | Хендлеры команд, использует config + storage |
| `attack_watch.py` (modify) | Следилка, использует config + storage |
| `.env.example` (create) | Шаблон переменных окружения |
| `.gitignore` (create) | Исключения из git |
| `requirements.txt` (create) | Зависимости |

---

### Task 1: Создать `.env.example` и `.gitignore`

**Files:**
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Создать `.env.example`**

```env
# Telegram Bot Token (от @BotFather)
BOT_TOKEN=

# Каналы для слежки через запятую
CHANNELS=slay_awards,streaminside,BotovodX

# Директория для хранения состояния ( groups.json, last.json и т.д.)
# По умолчанию — текущая директория
# ATTACK_STATE_DIR=/path/to/state

# Userbot (Telethon) — опционально
USERBOT_API_ID=YOUR_API_ID
USERBOT_API_HASH_FILE=
USERBOT_SESSION_DIR=

# Логирование
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=3
```

- [ ] **Step 2: Создать `.gitignore`**

```
.env
*.log
users.json
__pycache__/
*.pyc
*.session
last.json
last_*.json
groups.json
muted.json
attack.txt
callall.txt
remind.txt
```

- [ ] **Step 3: Проверить что .env.example и .gitignore созданы**

Run: `cat .env.example && echo "---" && cat .gitignore`
Expected: содержимое обоих файлов

- [ ] **Step 4: Коммит**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example and .gitignore"
```

---

### Task 2: Создать `config.py`

**Files:**
- Create: `config.py`

- [ ] **Step 1: Создать `config.py`**

```python
"""Конфигурация attack bot — все настройки из .env с дефолтами."""
import os
from pathlib import Path

# Загружаем .env если есть python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent
STATE_DIR = Path(os.environ.get("ATTACK_STATE_DIR", str(BASE_DIR)))

# Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNELS = [c.strip() for c in os.environ.get("CHANNELS", "slay_awards").split(",") if c.strip()]

# Paths
GROUPS_FILE = STATE_DIR / "groups.json"
USERS_FILE = STATE_DIR / "users.json"
LAST_FILE_PREFIX = STATE_DIR / "last"
ATTACK_FILE = STATE_DIR / "attack.txt"
CALLALL_FILE = STATE_DIR / "callall.txt"
REMIND_FILE = STATE_DIR / "remind.txt"
MUTED_FILE = STATE_DIR / "muted.json"

# Defaults
DEFAULT_COUNT = 5
DEFAULT_REMIND_MIN = 5
POLL_SEC = 60
MAX_GROUP_ATTEMPTS = 3  # автоудаление группы после N ошибок подряд

# Userbot (Telethon)
USERBOT_API_ID = int(os.environ.get("USERBOT_API_ID", "YOUR_API_ID"))
USERBOT_API_HASH_FILE = os.environ.get("USERBOT_API_HASH_FILE", "")
USERBOT_SESSION_DIR = os.environ.get("USERBOT_SESSION_DIR", "")

# Logging
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "3"))


def last_file(channel: str = "slay_awards") -> Path:
    """Путь к файлу последнего поста для канала."""
    if channel == "slay_awards":
        return STATE_DIR / "last.json"
    return STATE_DIR / f"last_{channel}.json"


def channel_file(channel: str) -> Path:
    """Путь к файлу состояния канала (on/off)."""
    return STATE_DIR / f"{channel}.txt"
```

- [ ] **Step 2: Проверить импорт**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import config; print('STATE_DIR:', config.STATE_DIR); print('CHANNELS:', config.CHANNELS)"`
Expected: STATE_DIR и CHANNELS выводятся без ошибок

- [ ] **Step 3: Коммит**

```bash
git add config.py
git commit -m "feat: add config.py — all settings from .env"
```

---

### Task 3: Создать `storage.py`

**Files:**
- Create: `storage.py`

- [ ] **Step 1: Создать `storage.py`**

```python
"""Хранилище данных attack bot — все load/save функции в одном месте."""
import json
import html as htmlmod
from pathlib import Path
from typing import Optional

from config import (
    GROUPS_FILE, USERS_FILE, MUTED_FILE, ATTACK_FILE,
    CALLALL_FILE, REMIND_FILE, STATE_DIR,
    DEFAULT_COUNT, DEFAULT_REMIND_MIN, MAX_GROUP_ATTEMPTS,
)


def _read_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _read_text(path: Path, default: str = "") -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


def _write_text(path: Path, value: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(value)


# === Groups ===

def load_groups() -> dict:
    return _read_json(GROUPS_FILE)


def save_groups(g: dict) -> None:
    _write_json(GROUPS_FILE, g)


def increment_group_errors(cid: str) -> int:
    """Увеличить счётчик ошибок группы. Возвращает новое значение."""
    g = load_groups()
    cfg = g.get(cid, {})
    cfg["consecutive_errors"] = cfg.get("consecutive_errors", 0) + 1
    g[cid] = cfg
    save_groups(g)
    return cfg["consecutive_errors"]


def reset_group_errors(cid: str) -> None:
    """Сбросить счётчик ошибок группы."""
    g = load_groups()
    if cid in g:
        g[cid]["consecutive_errors"] = 0
        save_groups(g)


def remove_group(cid: str) -> None:
    """Удалить группу из реестра."""
    g = load_groups()
    if cid in g:
        title = g[cid].get("title", cid)
        del g[cid]
        save_groups(g)
        print(f"Группа {cid} ({title}) удалена из-за ошибок.")


# === Users ===

def load_users() -> dict:
    return _read_json(USERS_FILE)


def save_users(u: dict) -> None:
    try:
        _write_json(USERS_FILE, u)
    except Exception as err:
        print(f"users-save: {err}")


def remember_user(chat_id: int, user) -> None:
    """Запоминаем всех, кто пишет в группе."""
    try:
        if not user or getattr(user, "is_bot", False):
            return
        u = load_users()
        cid = str(chat_id)
        grp = u.setdefault(cid, {})
        name = (user.full_name or user.username or str(user.id))[:60]
        grp[str(user.id)] = {
            "name": name,
            "username": (getattr(user, "username", "") or "").strip(),
        }
        save_users(u)
    except Exception as err:
        print(f"remember: {err}")


def build_tags_from_users(cid: str) -> list[str]:
    """Собирает теги по ZazyvalaTag2Bot-стилю."""
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


# === Muted ===

def load_muted() -> dict:
    return _read_json(MUTED_FILE)


def save_muted(d: dict) -> None:
    _write_json(MUTED_FILE, d)


def is_muted(chat_id, user_id: int) -> bool:
    m = load_muted().get(str(chat_id), [])
    return int(user_id) in [int(x) for x in m]


def set_muted(chat_id, user_id: int, on: bool) -> bool:
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


# === Last post ===

def load_last(channel: str = "slay_awards") -> dict:
    from config import last_file
    return _read_json(last_file(channel))


def save_last(channel: str, d: dict) -> None:
    from config import last_file
    _write_json(last_file(channel), d)


# === Attack on/off ===

def is_attack_on(channel: str = "") -> bool:
    """Проверяет глобальный + конкретный канал."""
    global_on = _read_text(ATTACK_FILE, "on") != "off"
    if not channel:
        return global_on
    from config import channel_file
    channel_on = _read_text(channel_file(channel), "on") != "off"
    return global_on and channel_on


def set_attack(on: bool) -> None:
    _write_text(ATTACK_FILE, "on" if on else "off")
    print(f"Атаки: {'ВКЛ' if on else 'ВЫКЛ'}")


def set_channel_on(channel: str, on: bool) -> None:
    from config import channel_file
    _write_text(channel_file(channel), "on" if on else "off")
    print(f"Канал {channel}: {'ВКЛ' if on else 'ВЫКЛ'}")


# === Callall ===

def is_callall_on() -> bool:
    return _read_text(CALLALL_FILE).lower() == "on"


def set_callall(on: bool) -> None:
    _write_text(CALLALL_FILE, "on" if on else "off")
    print(f"Авто-callall при атаке: {'ВКЛ' if on else 'ВЫКЛ'}")


# === Remind ===

def get_remind_minutes() -> int:
    raw = _read_text(REMIND_FILE)
    if not raw:
        return DEFAULT_REMIND_MIN
    try:
        val = int(raw)
        return val if val > 0 else DEFAULT_REMIND_MIN
    except ValueError:
        return DEFAULT_REMIND_MIN


def set_remind_minutes(minutes: int) -> None:
    _write_text(REMIND_FILE, str(minutes))
    print(f"Интервал напоминалок: {minutes} мин")
```

- [ ] **Step 2: Проверить импорт и базовые функции**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "from storage import load_groups, is_attack_on, get_remind_minutes; print('groups:', load_groups()); print('attack:', is_attack_on()); print('remind:', get_remind_minutes())"`
Expected: вывод без ошибок, дефолтные значения

- [ ] **Step 3: Коммит**

```bash
git add storage.py
git commit -m "feat: add storage.py — shared load/save functions"
```

---

### Task 4: Переписать `attack_bot.py` на config + storage

**Files:**
- Modify: `attack_bot.py`

- [ ] **Step 1: Заменить импорты и удалить дублированные функции**

Удалить из `attack_bot.py`:
- `sys.path.insert(0, "/root/kazahstanos/projects/slay4242bot")` (оставить если нужен `base`)
- `TOKEN = "..."` — заменить на `from config import BOT_TOKEN`
- Все `load_groups`, `save_groups`, `load_users`, `save_users`, `remember_user`, `build_tags_from_users`, `load_muted`, `save_muted`, `is_muted`, `set_muted`, `is_attack_on`, `set_attack`, `set_channel_on`, `is_callall_on`, `set_callall`, `get_remind_minutes`, `set_remind_minutes`, `last_info` — удалить, заменить импортами из `storage`

Новые импорты в начале файла:

```python
"""Боевой бот (объединённый): следит за каналами, командует атакой в группах."""
import asyncio
import html as htmlmod
import logging
import random
import re
import sys

sys.path.insert(0, "/root/kazahstanos/projects/slay4242bot")
import bot as base

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message, ChatMemberUpdated

from config import BOT_TOKEN, DEFAULT_COUNT, MAX_GROUP_ATTEMPTS, USERBOT_API_ID, USERBOT_API_HASH_FILE, USERBOT_SESSION_DIR
from storage import (
    load_groups, save_groups, load_users, remember_user,
    build_tags_from_users, load_muted, save_muted, is_muted, set_muted,
    is_attack_on, set_attack, set_channel_on,
    is_callall_on, set_callall,
    get_remind_minutes, set_remind_minutes,
    increment_group_errors, reset_group_errors, remove_group,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
```

- [ ] **Step 2: Добавить автоочистку мёртвых групп в `on_added`**

В хендлере `on_added` добавить обработку `ChatMemberUpdated` — при статусе `left` или `kicked` удалять группу. При ошибке `Not Found` при отправке приветствия — `increment_group_errors`.

Заменить блок отправки приветствия:

```python
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
        reset_group_errors(cid)
    except Exception as err:
        if "Not Found" in str(err):
            errors = increment_group_errors(cid)
            if errors >= MAX_GROUP_ATTEMPTS:
                remove_group(cid)
        print(f"Привет в {cid} не ушёл: {err}")
```

- [ ] **Step 3: Заменить `TOKEN` на `BOT_TOKEN` везде**

Найти все использования `TOKEN` в файле и заменить на `BOT_TOKEN`. Основное место: `bot = Bot(token=TOKEN)` → `bot = Bot(token=BOT_TOKEN)`.

- [ ] **Step 4: Заменить `STATE_DIR` пути на импорты из config/storage**

Найти все хардкоды `STATE_DIR` и заменить:
- `f"{STATE_DIR}/last.json"` → вызовы `load_last(channel)` / `save_last(channel, data)`
- `f"{STATE_DIR}/attack.txt"` → `is_attack_on()` / `set_attack()`
- `f"{STATE_DIR}/callall.txt"` → `is_callall_on()` / `set_callall()`
- `f"{STATE_DIR}/remind.txt"` → `get_remind_minutes()` / `set_remind_minutes()`

- [ ] **Step 5: Удалить неиспользуемые переменные**

Удалить: `STATE_DIR`, `GROUPS_FILE`, `LAST_FILE`, `USERS_FILE`, `ATTACK_FILE`, `REMIND_FILE`, `CALLALL_FILE`, `MUTED_FILE` — всё теперь в config/storage.

- [ ] **Step 6: Проверить что файл парсится**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import ast; ast.parse(open('attack_bot.py').read()); print('Синтаксис OK')"`
Expected: `Синтаксис OK`

- [ ] **Step 7: Коммит**

```bash
git add attack_bot.py
git commit -m "refactor: attack_bot.py uses config.py + storage.py"
```

---

### Task 5: Переписать `attack_watch.py` на config + storage

**Files:**
- Modify: `attack_watch.py`

- [ ] **Step 1: Заменить импорты и удалить дублированные функции**

Новые импорты:

```python
"""Следилка боевого бота: новый пост → атака (N черновиков)."""
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

from config import BOT_TOKEN, CHANNELS, POLL_SEC, DEFAULT_REMIND_MIN, MAX_GROUP_ATTEMPTS
from storage import (
    load_groups, load_last, save_last,
    is_attack_on, get_remind_minutes, is_callall_on,
    increment_group_errors, reset_group_errors, remove_group,
    build_tags_from_users, load_muted, load_users,
)

CHANNEL = os.environ.get("HERMES_CHANNEL", _WATCH_CHANNEL)

tg = Bot(token=BOT_TOKEN)
```

Удалить все дублированные функции: `load_groups`, `load_last`, `save_last`, `is_attack_on`, `get_remind_minutes`, `is_callall_on`.

- [ ] **Step 2: Добавить автоочистку в функцию `attack`**

В функции `attack()` при ошибке `Not Found` — увеличивать счётчик и удалять при превышении лимита:

```python
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
            # ... (остальная логика отправки паст и callall)
        except Exception as err:
            if "Not Found" in str(err):
                errors = increment_group_errors(cid)
                if errors >= MAX_GROUP_ATTEMPTS:
                    remove_group(cid)
                    continue
            print(f"Атака в {cid} не ушла: {err}")
```

- [ ] **Step 3: Добавить автоочистку в функцию `remind`**

Аналогично — при `Not Found` увеличивать счётчик:

```python
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
```

- [ ] **Step 4: Удалить неиспользуемые переменные**

Удалить: `STATE_DIR`, `GROUPS_FILE`, `LAST_FILE`, `POLL_SEC`, `DEFAULT_REMIND_MIN`, `CALLALL_FILE`, `REMIND_FILE`.

- [ ] **Step 5: Проверить синтаксис**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import ast; ast.parse(open('attack_watch.py').read()); print('Синтаксис OK')"`
Expected: `Синтаксис OK`

- [ ] **Step 6: Коммит**

```bash
git add attack_watch.py
git commit -m "refactor: attack_watch.py uses config.py + storage.py + dead group cleanup"
```

---

### Task 6: Настроить ротацию логов

**Files:**
- Modify: `attack_bot.py`
- Modify: `attack_watch.py`

- [ ] **Step 1: Добавить ротацию в `attack_bot.py`**

В функции `main()` заменить `logging.basicConfig` на:

```python
import logging
from logging.handlers import RotatingFileHandler
from config import STATE_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT

def setup_logging(name: str = "bot") -> None:
    log_file = STATE_DIR / f"{name}.log"
    handler = RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
```

В `main()` вызвать: `setup_logging("bot")`

- [ ] **Step 2: Добавить ротацию в `attack_watch.py`**

В начале `main()` вызвать:

```python
setup_logging(f"watcher_{CHANNEL}")
```

(функцию `setup_animation` импортировать из общего места или продублировать — для простоты продублировать в обоих файлах, т.к. она маленькая)

- [ ] **Step 3: Проверить создание лог-файла**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "from config import STATE_DIR; from logging.handlers import RotatingFileHandler; import logging; h = RotatingFileHandler(STATE_DIR / 'test.log', maxBytes=1024, backupCount=1); print('RotatingFileHandler OK')"`
Expected: без ошибок

- [ ] **Step 4: Коммит**

```bash
git add attack_bot.py attack_watch.py
git commit -m "feat: add RotatingFileHandler for log rotation"
```

---

### Task 7: Создать `requirements.txt`

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Создать `requirements.txt`**

```
aiogram>=3.0,<4.0
python-dotenv>=1.0
```

(telethon не включаем — он опциональный, используется только на сервере)

- [ ] **Step 2: Проверить установку**

Run: `cd "/home/sasha42/vscode/atack bot" && pip install -r requirements.txt 2>&1 | tail -5`
Expected: установка без ошибок

- [ ] **Step 3: Коммит**

```bash
git add requirements.txt
git commit -m "chore: add requirements.txt"
```

---

### Task 8: Финальная проверка

**Files:** Все файлы проекта

- [ ] **Step 1: Проверить что все импорты работают**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import config; import storage; print('config OK, storage OK')"`
Expected: `config OK, storage OK`

- [ ] **Step 2: Проверить синтаксис обоих основных файлов**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import ast; ast.parse(open('attack_bot.py').read()); ast.parse(open('attack_watch.py').read()); print('All syntax OK')"`
Expected: `All syntax OK`

- [ ] **Step 3: Проверить что .env.example содержит все переменные**

Run: `cd "/home/sasha42/vscode/atack bot" && grep -c "=" .env.example`
Expected: `8` (BOT_TOKEN, CHANNELS, ATTACK_STATE_DIR, USERBOT_API_ID, USERBOT_API_HASH_FILE, USERBOT_SESSION_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT)

- [ ] **Step 4: Проверить что .gitignore исключает нужные файлы**

Run: `cd "/home/sasha42/vscode/atack bot" && cat .gitignore`
Expected: содержит `.env`, `*.log`, `users.json`, `__pycache__/`

- [ ] **Step 5: Финальный коммит (если есть незакоммиченное)**

```bash
git add -A && git status
```

Проверить что все файлы закоммичены.
