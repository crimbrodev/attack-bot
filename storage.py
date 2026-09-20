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


# === General chat for warnings ===
GENERAL_FILE = STATE_DIR / "general.txt"


def get_general_chat() -> str:
    """ID чата куда слать предупреждения."""
    return _read_text(GENERAL_FILE)


def set_general_chat(chat_id: str) -> None:
    _write_text(GENERAL_FILE, chat_id)
    print(f"Чат для предупреждений: {chat_id}")


# === Warnings toggle ===
WARNINGS_FILE = STATE_DIR / "warnings_on.txt"


def is_warnings_on() -> bool:
    """Включены ли предупреждения о %% взвода."""
    val = _read_text(WARNINGS_FILE)
    if val == "":
        return True  # по умолчанию включены
    return val != "off"


def set_warnings(on: bool) -> None:
    _write_text(WARNINGS_FILE, "on" if on else "off")
    print(f"Предупреждения: {'вкл' if on else 'выкл'}")


# ═══════════════════════════════════════
#  НАСТРОЙКИ ЗАЗЫВАЛЫ (call_settings.json)
# ═══════════════════════════════════════

CALL_SETTINGS_FILE = STATE_DIR / "call_settings.json"

# Дефолты настроек зазывалы
CALL_DEFAULTS = {
    "who_can_mute": "all",        # кто может мутить себя: all / admins
    "who_can_call": "all",        # кто может делать /callall: all / admins
    "who_can_settings": "admins", # кто может открывать настройки: all / admins
    "auto_delete": False,         # автоудаление сообщений созыва
    "delete_delay": 0,            # задержка удаления (сек), 0 = не удалять
    "msg_delay": 0.5,             # задержка между сообщениями созыва (сек)
    "mentions_per_msg": 5,        # количество упоминаний в одном сообщении
}


def _load_call_settings() -> dict:
    """Загружает настройки зазывалы с дефолтами."""
    data = _read_json(CALL_SETTINGS_FILE)
    result = dict(CALL_DEFAULTS)
    result.update(data)
    return result


def _save_call_settings(data: dict) -> None:
    _write_json(CALL_SETTINGS_FILE, data)


def get_call_setting(key: str):
    """Получить настройку зазывалы по ключу."""
    return _load_call_settings().get(key, CALL_DEFAULTS.get(key))


def set_call_setting(key: str, value) -> None:
    """Установить настройку зазывалы."""
    data = _load_call_settings()
    data[key] = value
    _save_call_settings(data)
