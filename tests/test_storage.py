"""Тесты storage: per-group настройки работают без легаси-файлов (remind.txt, callall.txt и т.д.)."""
import storage
from config import DEFAULT_REMIND_MIN


def test_remind_minutes_default_without_cid():
    assert storage.get_remind_minutes("") == DEFAULT_REMIND_MIN


def test_callall_default_without_cid():
    assert storage.is_callall_on("") is False


def test_warnings_default_without_cid():
    assert storage.is_warnings_on("") is True


def test_general_chat_default_without_cid():
    assert storage.get_general_chat("") == ""


def test_call_setting_default_without_cid():
    assert storage.get_call_setting("", "mentions_per_msg") == 5
