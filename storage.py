"""Хранилище данных attack bot — все load/save функции в одном месте."""
import json
import html as htmlmod
from pathlib import Path
from typing import Optional

from config import (
    GROUPS_FILE, USERS_FILE, MUTED_FILE, ATTACK_FILE,
    STATE_DIR,
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


# === Attack on/off (глобально — влияет на все watcher'ы) ===

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


# ═══════════════════════════════════════
#  НАСТРОЙКИ ПО ГРУППАМ (per-group в groups.json)
# ═══════════════════════════════════════

# Дефолты всех per-group настроек
_GROUP_DEFAULTS = {
    "count": DEFAULT_COUNT,          # черновиков на пост
    "thread": None,                  # тред
    "remind_minutes": DEFAULT_REMIND_MIN,  # интервал напоминалок (мин)
    "callall": False,                # авто-тег всех при атаке
    "warnings": True,                # предупреждения о % взвода
    "general_chat": "",              # чат для предупреждений
    # Настройки зазывалы
    "who_can_mute": "all",
    "who_can_call": "all",
    "who_can_settings": "admins",
    "auto_delete": False,
    "delete_delay": 0,
    "msg_delay": 0.5,
    "mentions_per_msg": 5,
}


def _get_group_cfg(cid: str) -> dict:
    """Получить конфиг группы с дефолтами."""
    g = load_groups()
    cfg = g.get(cid, {})
    result = dict(_GROUP_DEFAULTS)
    result.update(cfg)
    return result


def _set_group_cfg(cid: str, key: str, value) -> None:
    """Установить настройку группы."""
    g = load_groups()
    if cid not in g:
        g[cid] = {"count": DEFAULT_COUNT, "title": cid}
    g[cid][key] = value
    save_groups(g)


# --- Черновики ---

def get_count(cid: str) -> int:
    return _get_group_cfg(cid).get("count", DEFAULT_COUNT)


def set_count(cid: str, n: int) -> None:
    _set_group_cfg(cid, "count", n)


# --- Тред ---

def get_thread(cid: str):
    return _get_group_cfg(cid).get("thread")


def set_thread(cid: str, thread_id) -> None:
    _set_group_cfg(cid, "thread", thread_id)


# --- Напоминалки ---

def get_remind_minutes(cid: str = "") -> int:
    """Интервал напоминалок (мин) для группы. Без cid — дефолт из _GROUP_DEFAULTS."""
    return _get_group_cfg(cid).get("remind_minutes", DEFAULT_REMIND_MIN)


def set_remind_minutes(cid: str, minutes: int) -> None:
    _set_group_cfg(cid, "remind_minutes", minutes)
    print(f"Интервал напоминалок ({cid}): {minutes} мин")


# --- Авто-callall ---

def is_callall_on(cid: str = "") -> bool:
    """Включён ли авто-callall для группы. Без cid — дефолт из _GROUP_DEFAULTS."""
    return bool(_get_group_cfg(cid).get("callall", False))


def set_callall(cid: str, on: bool) -> None:
    _set_group_cfg(cid, "callall", on)
    print(f"Авто-callall ({cid}): {'ВКЛ' if on else 'ВЫКЛ'}")


# --- Предупреждения ---

def is_warnings_on(cid: str = "") -> bool:
    """Включены ли предупреждения для группы. Без cid — дефолт из _GROUP_DEFAULTS."""
    return bool(_get_group_cfg(cid).get("warnings", True))


def set_warnings(cid: str, on: bool) -> None:
    _set_group_cfg(cid, "warnings", on)
    print(f"Предупреждения ({cid}): {'вкл' if on else 'выкл'}")


# --- Чат для предупреждений ---

def get_general_chat(cid: str = "") -> str:
    """Чат для предупреждений группы. Без cid — дефолт из _GROUP_DEFAULTS."""
    return _get_group_cfg(cid).get("general_chat", "")


def set_general_chat(cid: str, chat_id: str) -> None:
    _set_group_cfg(cid, "general_chat", chat_id)
    print(f"Чат для предупреждений ({cid}): {chat_id}")


# --- Настройки зазывалы (per-group) ---

def get_call_setting(cid: str, key: str):
    """Получить настройку зазывалы по ключу для группы."""
    cfg = _get_group_cfg(cid)
    return cfg.get(key, _GROUP_DEFAULTS.get(key))


def set_call_setting(cid: str, key: str, value) -> None:
    """Установить настройку зазывалы для группы."""
    _set_group_cfg(cid, key, value)
