"""Локальный watcher — парсит посты из Telegram-канала через публичный превью."""
import httpx
import re
from typing import Optional

DEFAULT_CHANNEL = "slay_awards"


def fetch_preview(channel: str = "") -> str:
    """Загружает HTML превью канала (t.me/s/...)."""
    ch = channel or DEFAULT_CHANNEL
    url = f"https://t.me/s/{ch}"
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"fetch_preview {ch}: {e}")
        return ""


def parse_posts(html: str) -> list[tuple[int, str]]:
    """Извлекает (post_id, text) из HTML превью канала."""
    posts = []
    # Ищем div с class="tgme_widget_message_wrap" — каждый такой это пост
    pattern = re.compile(
        r'data-post="([^"]+)/(\d+)".*?'
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        channel_name = match.group(1)
        post_id = int(match.group(2))
        text_html = match.group(3)
        # Убираем HTML теги, оставляем текст
        text = re.sub(r'<[^>]+>', ' ', text_html)
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            posts.append((post_id, text))
    return posts


def make_comment(post_text: str) -> str:
    """Генерирует комментарий к посту через base.chat_with_failover."""
    import base
    reply = base.chat_with_failover(
        messages=[
            {"role": "system", "content": (
                "Ты активный комментатор в Telegram. "
                "Прочитай пост и напиши живой короткий комментарий к нему (1-2 предложения). "
                "Пиши ЕСТЕСТВЕННО, как обычный живой человек — без штампов. "
                "Засыпай текст смайликами и эмодзи — минимум 6 штук. "
                "Текст должен выглядеть ярко и живо. "
                "Отвечай ТОЛЬКО текстом комментария."
            )},
            {"role": "user", "content": post_text},
        ],
        max_tokens=1500,
        temperature=1.1,
    )
    if not reply:
        reply = "Залетел пост — вайб годный, читается на одном дыхании."
    return reply
