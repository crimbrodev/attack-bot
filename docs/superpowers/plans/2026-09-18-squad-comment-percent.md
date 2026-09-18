# Squad Comment % in Reminders — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** При напоминании показывать какой процент комментариев под постом написали люди из взвода.

**Architecture:** Telegram API не даёт получить комментарии к посту канала напрямую из бота. Используем Telethon (userbot) для получения комментариев через `get_discussion_thread`. Сравниваем авторов комментариев с базой `users.json` (взвод). Результат — процент и количество.

**Tech Stack:** Python, Telethon, aiogram

---

## Проблема

Telegram Bot API **не умеет** получать комментарии к посту канала. Комментарии хранятся в linked discussion group. Чтобы их достать, нужен Telethon (userbot) с авторизованной сессией.

**Есть два варианта:**

### Вариант A: Telethon (полноценный)
- Получаем реальные комментарии к посту
- Считаем точный процент
- Нужна .session файл и API ID/Hash

### Вариант B: Без Telethon (упрощённый)
- Считаем только комментарии которые бот САМ отправил (через attack_watch)
- Показываем "Наши черновики: X из Y" (сколько отправили vs сколько было до нас)
- Менее точно, но работает без userbot

---

## Вариант A: С Telethon

### Task 1: Добавить Telethon в проект

**Files:**
- Modify: `requirements.txt`
- Modify: `.env`
- Modify: `.env.example`
- Modify: `config.py`

- [ ] **Step 1: Добавить telethon в requirements.txt**

```
aiogram>=3.0,<4.0
python-dotenv>=1.0
httpx>=0.25
telethon>=1.36
```

- [ ] **Step 2: Добавить переменные в .env**

```
USERBOT_API_ID=YOUR_API_ID
USERBOT_API_HASH=your_api_hash_here
USERBOT_SESSION=session_name
```

- [ ] **Step 3: Добавить в config.py**

```python
USERBOT_API_ID = int(os.environ.get("USERBOT_API_ID", "0"))
USERBOT_API_HASH = os.environ.get("USERBOT_API_HASH", "")
USERBOT_SESSION = os.environ.get("USERBOT_SESSION", "")
```

- [ ] **Step 4: Коммит**

```bash
git add requirements.txt .env .env.example config.py
git commit -m "chore: add telethon dependencies"
```

---

### Task 2: Создать модуль comments.py

**Files:**
- Create: `comments.py`

- [ ] **Step 1: Создать comments.py**

```python
"""Получение комментариев к посту канала через Telethon."""
import asyncio
from telethon import TelegramClient
from config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION


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
        
        # Получаем канал
        entity = await client.get_entity(channel)
        
        # Получаем сообщение (пост)
        message = await client.get_messages(entity, ids=post_id)
        if not message:
            return []
        
        # Получаем комментарии (discussion thread)
        if not message.comments:
            return []
        
        comments = await client.get_messages(
            entity,
            reply_to=post_id,
            limit=100,
        )
        
        commenters = []
        for comment in comments:
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
    # Собираем все ID из взвода
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
```

- [ ] **Step 2: Проверить импорт**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import comments; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Коммит**

```bash
git add comments.py
git commit -m "feat: add comments.py — fetch post commenters via Telethon"
```

---

### Task 3: Интегрировать в attack_watch.py

**Files:**
- Modify: `attack_watch.py`

- [ ] **Step 1: Добавить импорт в attack_watch.py**

Добавить в импорты:
```python
from comments import get_post_commenters, calc_squad_percentage
from storage import load_users
```

- [ ] **Step 2: Изменить функцию remind()**

Заменить текущую функцию `remind()`:

```python
async def remind(pid: int, minutes: int) -> None:
    groups = load_groups()
    
    # Получаем комментарии и считаем %
    squad_users = load_users()
    try:
        commenters = await get_post_commenters(CHANNEL, pid)
        squad_count, total, pct = calc_squad_percentage(commenters, squad_users)
    except Exception:
        squad_count, total, pct = 0, 0, 0
    
    # Формируем строку процента
    if total > 0:
        pct_text = f"\n\n💬 Комментариев: {total}, из них от взвода: {squad_count} ({pct:.0f}%)"
    else:
        pct_text = ""
    
    for cid, cfg in groups.items():
        thread = cfg.get("thread")
        kwargs = {"message_thread_id": thread} if thread else {}
        try:
            await tg.send_message(
                cid,
                f"⏰ Прошло {minutes} мин с поста — пора АТАКОВАТЬ!\n"
                f"{link(pid)}{pct_text}{base.SIGN}",
                parse_mode="HTML", **kwargs)
            reset_group_errors(cid)
        except Exception as err:
            if "Not Found" in str(err):
                errors = increment_group_errors(cid)
                if errors >= MAX_GROUP_ATTEMPTS:
                    remove_group(cid)
            print(f"Напоминалка в {cid} не ушла: {err}")
```

- [ ] **Step 3: Проверить синтаксис**

Run: `cd "/home/sasha42/vscode/atack bot" && python -c "import ast; ast.parse(open('attack_watch.py').read()); print('OK')"`

- [ ] **Step 4: Коммит**

```bash
git add attack_watch.py
git commit -m "feat: show squad comment percentage in reminders"
```

---

## Вариант B: Без Telethon (упрощённый)

Если Telethon не доступен — считаем только свои черновики.

### Task 1: Трекинг отправленных черновиков

**Files:**
- Create: `drafts_tracker.py`

- [ ] **Step 1: Создать drafts_tracker.py**

```python
"""Трекер отправленных черновиков — считает сколько наших паст под постом."""
import json
from pathlib import Path
from config import STATE_DIR

DRAFTS_FILE = STATE_DIR / "drafts.json"


def _load() -> dict:
    try:
        return json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save(data: dict) -> None:
    DRAFTS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def track_draft(channel: str, post_id: int, count: int = 1) -> None:
    """Запомнить что отправили черновики к посту."""
    data = _load()
    key = f"{channel}:{post_id}"
    data[key] = data.get(key, 0) + count
    _save(data)


def get_draft_count(channel: str, post_id: int) -> int:
    """Сколько черновиков мы отправили к этому посту."""
    data = _load()
    return data.get(f"{channel}:{post_id}", 0)
```

- [ ] **Step 2: Коммит**

```bash
git add drafts_tracker.py
git commit -m "feat: add drafts_tracker.py"
```

### Task 2: Интегрировать трекинг в attack_watch.py

**Files:**
- Modify: `attack_watch.py`

- [ ] **Step 1: Добавить импорт**

```python
from drafts_tracker import track_draft, get_draft_count
```

- [ ] **Step 2: В функции attack() после отправки всех черновиков добавить трекинг**

После цикла `for i in range(1, count + 1):` добавить:
```python
track_draft(CHANNEL, pid, count)
```

- [ ] **Step 3: В функции remind() добавить информацию**

```python
drafts_sent = get_draft_count(CHANNEL, pid)
drafts_text = f"\n\n✍️ Наших черновиков под постом: {drafts_sent}" if drafts_sent > 0 else ""
```

И добавить `drafts_text` в сообщение.

- [ ] **Step 4: Коммит**

```bash
git add attack_watch.py
git commit -m "feat: track and show draft count in reminders"
```

---

## Рекомендация

**Вариант B проще и не требует Telethon/userbot.** Для начала его хватит. Потом можно добавить Telethon для точного процента.
