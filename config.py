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
USERBOT_API_ID = int(os.environ.get("USERBOT_API_ID", "0"))
USERBOT_API_HASH = os.environ.get("USERBOT_API_HASH", "")
USERBOT_SESSION = os.environ.get("USERBOT_SESSION", "")

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
