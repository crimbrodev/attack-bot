# Attack Bot Refactor — Design Spec

> **Goal:** Модульная рефструктуризация attack_bot + attack_watch: вынести конфигурацию, хранилище, убрать захардкоженные пути, починить атаки в мёртвые группы, добавить безопасность и инфраструктуру.

## Текущее состояние

- `attack_bot.py` (909 строк) — основной бот, все хендлеры + load/save функции
- `attack_watch.py` (229 строк) — следилка за каналами, дублирует load/save
- Токен захардкожен в `attack_bot.py:19`
- Все пути ведут на `/root/kazahstanos/projects/...`
- `groups.json` пуст `{}`, но атаки идут по старым ID → "Not Found" ошибки
- Логи не ротируются, бесконечно растут
- Нет `.gitignore`, `requirements.txt`, `.env`

## Целевая структура

```
attack bot/
├── attack_bot.py          # Хендлеры команд (aiogram)
├── attack_watch.py        # Следилка за каналами
├── config.py              # Конфигурация из .env
├── storage.py             # Load/save для всех данных
├── .env.example           # Шаблон переменных окружения
├── .gitignore             # Исключения из git
├── requirements.txt       # Зависимости
├── groups.json            # Состояние групп
├── users.json             # База пользователей
├── last.json              # Последний пост slay_awards
├── last_streaminside.json # Последний пост streaminside
├── last_BotovodX.json     # Последний пост BotovodX
└── watcher*.log           # Логи (ротируются)
```

## Секция 1: Конфигурация (`config.py`)

Все настройки из переменных окружений с дефолтами:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATE_DIR = Path(os.environ.get("ATTACK_STATE_DIR", str(BASE_DIR)))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNELS = os.environ.get("CHANNELS", "slay_awards").split(",")

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
MAX_GROUP_ATTEMPTS = 3  # сколько раз подряд "Not Found" допустимо перед удалением группы

# Userbot (Telethon)
USERBOT_API_ID = int(os.environ.get("USERBOT_API_ID", "YOUR_API_ID"))
USERBOT_API_HASH_FILE = os.environ.get("USERBOT_API_HASH_FILE", "")
USERBOT_SESSION_DIR = os.environ.get("USERBOT_SESSION_DIR", "")

# Logging
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5MB
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "3"))
```

## Секция 2: Хранилище (`storage.py`)

Все функции load/save в одном модуле. Принимают `STATE_DIR` из config.

Ключевые функции:
- `load_groups() -> dict` / `save_groups(g: dict)`
- `load_users() -> dict` / `save_users(u: dict)`
- `load_muted() -> dict` / `save_muted(d: dict)`
- `load_last(channel: str) -> dict` / `save_last(channel: str, d: dict)`
- `is_attack_on(channel: str) -> bool` — проверяет и глобальный attack.txt, и канал
- `get_remind_minutes() -> int`
- `is_callall_on() -> bool`
- `remember_user(chat_id, user)`
- `build_tags_from_users(cid: str) -> list[str]`
- `is_muted(chat_id, user_id) -> bool` / `set_muted(chat_id, user_id, on: bool) -> bool`

Все функции используют `config.py` для путей.

## Секция 3: Очистка мёртвых групп

В `attack_bot.py` при обработке `ChatMemberUpdated`:
- При `Not Found` от Telegram → увеличивать счётчик ошибок в `groups.json`
- Если счётчик >= `MAX_GROUP_ATTEMPTS` → удалять группу и логировать

В `attack_watch.py`:
- При `Not Found` при атаке/напоминании → аналогично увеличивать счётчик
- Автоочистка при превышении лимита

Структура группы в `groups.json`:
```json
{
  "chat_id": {
    "count": 5,
    "title": "Group Name",
    "thread": null,
    "consecutive_errors": 0
  }
}
```

## Секция 4: Безопасность

- Токен ТОЛЬКО в `.env`, в коде только `config.BOT_TOKEN`
- `.env` в `.gitignore`
- `.env.example` с шаблоном (без реального токена)
- `users.json` в `.gitignore` (содержит PII)

## Секция 5: Логирование

- `RotatingFileHandler` с `maxBytes=5MB`, `backupCount=3`
- Каждый процесс пишет в свой лог: `watcher.log`, `watcher_streaminside.log`, `watcher_BotovodX.log`
- Формат: `%(asctime)s %(levelname)s %(message)s`

## Секция 6: Инфраструктура

- `requirements.txt`: aiogram, telethon (опционально)
- `.gitignore`: `.env`, `*.log`, `users.json`, `__pycache__/`, `*.session`

## Что НЕ меняется

- Логика генерации паст (base.chat_with_failover) — не трогаем
- Внешний модуль `bot as base` (slay4242bot) — не трогаем
- Команды бота — набор и поведение сохраняются
- Telethon userbot логика — сохраняется, только пути из конфига

## Тестирование

- Бот запускается: `python attack_bot.py` (проверяем что импорты работают)
- Следилка запускается: `HERMES_CHANNEL=slay_awards python attack_watch.py`
- Проверяем что `.env` читается корректно
- Проверяем что группы с ошибками автоудаляются
