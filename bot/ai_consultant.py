import logging
import os

import anthropic
import aiosqlite
import httpx

log = logging.getLogger(__name__)

# Читаем ключ при каждом вызове (не при импорте) — чтобы подхватить Railway Variables
def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


async def get_catalog_context(db_path: str, region: str = "UA", limit: int = 30) -> str:
    """
    Получить каталог для системного промпта.
    Сначала пробуем SQLite (бот и бэкенд в одном контейнере),
    при ошибке — fallback на HTTP API.
    """
    try:
        return await _catalog_from_sqlite(db_path, region, limit)
    except Exception as e:
        log.warning("SQLite catalog failed (%s), falling back to HTTP API", e)
        return await _catalog_from_api(region, limit)


async def _catalog_from_sqlite(db_path: str, region: str, limit: int) -> str:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """
            SELECT title, price_byn, discount_pct, platform, genre, id
            FROM products
            WHERE region=? AND product_type='game' AND is_active=1 AND price_byn > 0
            ORDER BY discount_pct DESC, price_byn ASC
            LIMIT ?
            """,
            (region, limit),
        ) as cur:
            games = await cur.fetchall()

        async with db.execute(
            """
            SELECT title, price_byn, id
            FROM products
            WHERE region=? AND product_type='subscription' AND is_active=1
            ORDER BY price_byn ASC
            LIMIT 20
            """,
            (region,),
        ) as cur:
            subs = await cur.fetchall()

    return _build_catalog(
        [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in games],
        [(r[0], r[1], r[2]) for r in subs],
    )


async def _catalog_from_api(region: str, limit: int) -> str:
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            gr = await client.get(
                f"{api_url}/api/v1/products",
                params={"region": region, "limit": limit, "product_type": "game"},
            )
            sr = await client.get(
                f"{api_url}/api/v1/products",
                params={"region": region, "limit": 20, "product_type": "subscription"},
            )
        games_raw = gr.json() if gr.status_code == 200 else []
        subs_raw  = sr.json() if sr.status_code == 200 else []
    except Exception as e:
        log.error("HTTP catalog fetch failed: %s", e)
        return "Каталог временно недоступен."

    games = [
        (p.get("title", ""), p.get("price_byn", 0),
         p.get("discount_pct", 0), p.get("platform", ""),
         p.get("genre", ""), p.get("id", ""))
        for p in (games_raw if isinstance(games_raw, list) else [])
    ]
    subs = [
        (p.get("title", ""), p.get("price_byn", 0), p.get("id", ""))
        for p in (subs_raw if isinstance(subs_raw, list) else [])
    ]
    return _build_catalog(games, subs)


def _build_catalog(games: list, subs: list) -> str:
    catalog = "КАТАЛОГ МАГАЗИНА GAME STORE:\n\nИГРЫ:\n"
    for title, price, discount, platform, genre, pid in games:
        if not price:
            continue
        discount_str = f" (-{discount}%)" if discount else ""
        genre_str    = f" [{genre}]"       if genre    else ""
        catalog += f"- {title}{genre_str}: {price} BYN{discount_str} | ID:{pid}\n"
    catalog += "\nПОДПИСКИ:\n"
    for title, price, pid in subs:
        catalog += f"- {title}: {price} BYN | ID:{pid}\n"
    return catalog


async def ask_consultant(
    user_message: str,
    conversation_history: list,
    region: str,
    db_path: str,
) -> tuple[str, list]:
    """
    Возвращает (ответ_строка, обновлённая_история).
    Никогда не поднимает исключений — ошибки возвращаются как текст.
    """
    log.info("AI consultant: message=%r region=%s", user_message[:60], region)

    api_key = _api_key()
    log.info("API key len=%d starts=%s", len(api_key), api_key[:10] if api_key else "EMPTY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY is not set")
        return "❌ AI консультант недоступен: не задан API ключ. Напишите @Sherenberg", []

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        # ── Шаг 1: минимальный тест без каталога ──────────────────────────
        test = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": "Привет"}],
        )
        log.info("Test OK: %s", test.content[0].text[:50])

        # ── Шаг 2: полный запрос с каталогом ──────────────────────────────
        try:
            catalog = await get_catalog_context(db_path, region, limit=20)
            log.info("Catalog: %d chars", len(catalog))
        except Exception as e:
            log.error("Catalog error: %s", e)
            catalog = ""

        catalog = catalog[:2000]
        system = f"""Ты опытный консультант игрового магазина GAME STORE для PlayStation.

НАШ КАТАЛОГ (есть в наличии с ценами):
{catalog}

ПРАВИЛА КОНСУЛЬТАЦИИ:

1. Если вопрос расплывчатый — задай уточняющие вопросы:
   - Какой жанр? (Экшн, RPG, Спорт, Гонки, Файтинг, Шутер, Аркада, Хоррор, Приключения)
   - Играете вдвоём на одном экране или онлайн?
   - Какой бюджет?
   - PS4 или PS5?

2. Рекомендуй игры из ДВУХ категорий:

   КАТЕГОРИЯ А — "Есть в наличии":
   Игры из нашего каталога выше — указывай точную цену в BYN и скидку.
   Добавляй тег: [ТОВАР:ID:название]

   КАТЕГОРИЯ Б — "Можем заказать":
   Любые другие популярные игры с PlayStation Store которых нет в каталоге.
   НЕ пиши цену — пиши "уточнить цену у менеджера @Sherenberg".
   НЕ добавляй тег [ТОВАР:...].

3. Формат ответа:
✅ Есть в наличии:
- Название — 150 BYN (-30%) [ТОВАР:123:Название]

📦 Можем заказать (уточнить цену у @Sherenberg):
- Название — краткое описание

4. Отвечай кратко и дружелюбно на русском языке.
5. Рекомендуй 2-4 игры из наличия и 2-4 на заказ.
6. Всегда в конце: "Для заказа или вопросов пишите @Sherenberg 🎮"
"""

        # Очищаем историю — только валидные пары, последние 10 сообщений
        clean_history = [
            msg for msg in conversation_history[-10:]
            if isinstance(msg, dict)
            and msg.get("role") in ("user", "assistant")
            and isinstance(msg.get("content"), str)
            and msg["content"].strip()
        ]
        messages = clean_history + [{"role": "user", "content": user_message}]

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system,
            messages=messages,
        )
        result = response.content[0].text
        log.info("Full response: %d chars", len(result))

        updated_history = messages + [{"role": "assistant", "content": result}]
        return result, updated_history

    except anthropic.BadRequestError as e:
        log.error("BadRequestError %s: %s", e.status_code, e.body)
        return f"❌ Ошибка запроса к AI: {e.body}. Напишите @Sherenberg", []
    except anthropic.AuthenticationError as e:
        log.error("AuthenticationError: %s", e)
        return "❌ Ошибка авторизации AI. Обратитесь к @Sherenberg", []
    except anthropic.RateLimitError as e:
        log.error("RateLimitError: %s", e)
        return "⏳ AI сейчас перегружен, попробуйте через минуту.", []
    except Exception as e:
        log.error("AI error: %s: %s", type(e).__name__, e)
        return f"❌ Ошибка: {type(e).__name__}. Напишите @Sherenberg", []
