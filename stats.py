"""Сбор статистики по комментариям — медленно, чтобы не забанили."""
import asyncio
import json
import time
from pathlib import Path
from comments import get_post_commenters, calc_squad_percentage
from storage import load_users
from watcher import fetch_preview, parse_posts
from config import STATE_DIR

STATS_FILE = STATE_DIR / "comment_stats.json"
DELAY_BETWEEN_POSTS = 15  # секунд между постами
DELAY_BETWEEN_COMMENTS = 2  # задержка внутри поста (для Telethon)


async def collect_stats(channel: str, max_posts: int = 20) -> list[dict]:
    """Собирает статистику по последним постам канала."""
    print(f"Собираю статистику по {channel} (макс {max_posts} постов)...")
    print(f"Задержка: {DELAY_BETWEEN_POSTS}с между постами\n")

    posts = parse_posts(fetch_preview(channel))
    if not posts:
        print("Посты не найдены")
        return []

    # Берём последние N постов
    recent = posts[-max_posts:]
    squad_users = load_users()
    results = []

    for i, (pid, text) in enumerate(recent, 1):
        print(f"[{i}/{len(recent)}] Пост #{pid}...", end=" ", flush=True)

        try:
            commenters = await get_post_commenters(channel, pid)
            squad_count, total, pct = calc_squad_percentage(commenters, squad_users)

            result = {
                "post_id": pid,
                "text_preview": text[:100],
                "total_comments": total,
                "squad_comments": squad_count,
                "squad_pct": round(pct, 1),
            }
            results.append(result)

            print(f"{total} коммент., от взвода: {squad_count} ({pct:.0f}%)")
        except Exception as e:
            print(f"ошибка: {e}")
            results.append({"post_id": pid, "error": str(e)})

        # Задержка между постами
        if i < len(recent):
            print(f"  Жду {DELAY_BETWEEN_POSTS}с...")
            await asyncio.sleep(DELAY_BETWEEN_POSTS)

    # Сохраняем
    STATS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nСохранено в {STATS_FILE}")

    return results


def print_summary(results: list[dict]) -> None:
    """Выводит сводку."""
    valid = [r for r in results if "error" not in r]
    if not valid:
        print("Нет данных")
        return

    total_all = sum(r["total_comments"] for r in valid)
    squad_all = sum(r["squad_comments"] for r in valid)
    avg_pct = sum(r["squad_pct"] for r in valid) / len(valid)

    print("\n=== СВОДКА ===")
    print(f"Постов: {len(valid)}")
    print(f"Всего комментариев: {total_all}")
    print(f"От взвода: {squad_all} ({(squad_all/total_all*100):.1f}%)" if total_all else "От взвода: 0")
    print(f"Средний % взвода: {avg_pct:.1f}%")
    print("\nПо постам:")
    for r in valid:
        print(f"  #{r['post_id']}: {r['total_comments']} коммент., "
              f"взвод {r['squad_comments']} ({r['squad_pct']}%)")


if __name__ == "__main__":
    import sys
    channel = sys.argv[1] if len(sys.argv) > 1 else "slay_awards"
    max_posts = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    results = asyncio.run(collect_stats(channel, max_posts))
    print_summary(results)
