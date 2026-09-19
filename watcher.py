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
    reply = ""
    for attempt in range(3):
        reply = base.chat_with_failover(
            messages=[
                {"role": "system", "content": (
                    "Ты — подписчик Telegram-канала, комментируешь новый пост. "
                    "Напиши живой комментарий (2-3 предложения) к посту ниже. "
                    "Пиши ЕСТЕСТВЕННО, как обычный человек — с эмоциями и сленгом. "
                    "Засыпай текст смайликами и эмодзи — минимум 6 штук, в каждом предложении. "
                    "Сначала отреагируй на сам пост (что-то своё, живое). "
                    "Потом плавно подведи к альбому Magnum от Пятёрки и Меллшера — что он уже вышел, "
                    "треки на любой вкус, лайк в Яндекс Музыке. "
                    "Далее подведи к альбому Opus — он выходит 25 сентября, "
                    "поставь пресейв, это будет мясо. "
                    "Отвечай ТОЛЬКО текстом комментария, без кавычек и номеров.")},
                {"role": "user", "content": post_text},
            ],
            max_tokens=1500,
            temperature=1.1,
        )
        if reply:
            break
        import time
        time.sleep(2)
    if not reply:
        reply = "Залетел пост — вайб годный, читается на одном дыхании."
    return reply.strip()
