"""Web tools — поиск в интернете и скачивание URL для агентского tool-loop.

Два инструмента, описанных в OpenAI tool-format:
  * web_search(query, max_results) — поиск через DuckDuckGo (без API-ключа)
  * fetch_url(url, max_chars)      — скачивание страницы как plain text

Используются в `chat_with_tools` `OpenAICompatLLMClient`. Все строки результата
безопасны для подстановки в role="tool" сообщение OpenAI-чата.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Импорт ddgs делаем лениво — клиент инициализирует tcp-пул при первом вызове.
_DDGS_AVAILABLE: bool | None = None


def _ddgs_available() -> bool:
    global _DDGS_AVAILABLE
    if _DDGS_AVAILABLE is None:
        try:
            import ddgs  # noqa: F401

            _DDGS_AVAILABLE = True
        except ImportError:
            logger.warning("ddgs not installed; web_search disabled")
            _DDGS_AVAILABLE = False
    return _DDGS_AVAILABLE


def web_search(query: str, max_results: int = 5) -> str:
    """Поиск в DuckDuckGo. Возвращает форматированный текст с топ-результатами.

    Лимиты: max_results кэпируется до 10 — модели достаточно, а ответ короткий.
    """
    if not _ddgs_available():
        return json.dumps({"error": "web_search недоступен (нет ddgs)"}, ensure_ascii=False)

    from ddgs import DDGS

    capped = max(1, min(int(max_results) if max_results else 5, 10))
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=capped))
    except Exception as e:
        logger.warning("web_search error: %s", e)
        return json.dumps({"error": f"Ошибка поиска: {e}", "query": query}, ensure_ascii=False)

    if not results:
        return json.dumps({"query": query, "results": []}, ensure_ascii=False)

    items: list[dict[str, str]] = []
    for r in results:
        items.append(
            {
                "title": (r.get("title") or "").strip(),
                "url": r.get("href") or r.get("url") or "",
                "snippet": (r.get("body") or "").strip()[:280],
            }
        )
    return json.dumps({"query": query, "results": items}, ensure_ascii=False)


# Простая очистка HTML — без зависимостей. Для серьёзного парсинга есть
# beautifulsoup, но для tool-output 4 КБ хватает регексп-стрипа.
_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    text = _SCRIPT_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def is_public_url(url: str) -> bool:
    """True, если хост URL резолвится только в публичные IP (защита от SSRF).

    Блокирует localhost и приватные/служебные диапазоны (10/8, 172.16/12,
    192.168/16, 169.254/16, ::1 и т.п.), чтобы нельзя было дёрнуть внутренние
    сервисы (например, llama-swap на 127.0.0.1:8090) через /ingest/url.
    """
    try:
        host = urlparse(url).hostname
        if not host:
            return False

        def _blocked(ip_str: str) -> bool:
            ip = ipaddress.ip_address(ip_str)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            )

        # Литеральный IP — проверяем напрямую (без DNS).
        try:
            return not _blocked(host)
        except ValueError:
            pass
        # Имя хоста — резолвим и проверяем все полученные адреса.
        addrs = socket.getaddrinfo(host, None)
        return bool(addrs) and not any(_blocked(info[4][0]) for info in addrs)
    except Exception:
        return False


def fetch_url(url: str, max_chars: int = 4000) -> str:
    """Скачать страницу и вернуть plain text.

    Лимит max_chars кэпируется до 8000 — большие куски засоряют контекст
    и редко нужны модели для ответа.
    """
    capped = max(200, min(int(max_chars) if max_chars else 4000, 8000))
    if not url or not isinstance(url, str):
        return json.dumps({"error": "url пустой или не строка"}, ensure_ascii=False)
    if not (url.startswith("http://") or url.startswith("https://")):
        return json.dumps({"error": "url должен начинаться с http(s)://"}, ensure_ascii=False)
    if not is_public_url(url):
        return json.dumps(
            {"error": "URL заблокирован: приватный или локальный адрес недопустим"},
            ensure_ascii=False,
        )

    try:
        # Анти-SSRF: редиректы обрабатываем вручную, перепроверяя каждый хоп —
        # иначе публичный URL может 302-нуть на 127.0.0.1 (llama-swap) или метадату.
        with httpx.Client(
            timeout=15.0,
            follow_redirects=False,
            headers={"User-Agent": "MITS-Tutor/1.0 (educational)"},
        ) as client:
            r = client.get(url)
            for _ in range(5):  # максимум 5 редиректов
                if not r.is_redirect:
                    break
                next_url = str(r.next_request.url) if r.next_request else ""
                if not next_url.startswith(("http://", "https://")) or not is_public_url(next_url):
                    return json.dumps(
                        {
                            "error": "Редирект заблокирован: приватный или локальный адрес недопустим"
                        },
                        ensure_ascii=False,
                    )
                r = client.get(next_url)
        r.raise_for_status()
    except Exception as e:
        logger.warning("fetch_url error: %s %s", url, e)
        return json.dumps({"error": f"Ошибка загрузки: {e}", "url": url}, ensure_ascii=False)

    ct = r.headers.get("content-type", "")
    text = _strip_html(r.text) if "html" in ct or not ct else r.text
    truncated = len(text) > capped
    payload: dict[str, Any] = {
        "url": str(r.url),
        "content_type": ct,
        "length": len(text),
        "text": text[:capped] + ("…" if truncated else ""),
    }
    return json.dumps(payload, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────
# OpenAI tool definitions
# ─────────────────────────────────────────────────────────────────────

WEB_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Поиск в интернете через DuckDuckGo. Используй для актуальной "
                "информации (новости, релизы, факты после обучающей выборки). "
                "Возвращает JSON со списком title/url/snippet. ВАЖНО: если "
                "первый запрос дал нерелевантные результаты — ПЕРЕФОРМУЛИРУЙ "
                "и попробуй ещё раз (убери лишние слова типа 'news', добавь "
                "конкретное имя/дату, попробуй английский и русский варианты). "
                "Минимум 2 попытки прежде чем сказать пользователю «не нашёл»."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "max_results": {
                        "type": "integer",
                        "description": "Сколько результатов (1-10, по умолчанию 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Скачать страницу по URL и вернуть как plain text (HTML удаляется). "
                "Используй после web_search, если нужны подробности из конкретной "
                "ссылки. Лимит ~8000 символов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Полный http(s) URL"},
                    "max_chars": {
                        "type": "integer",
                        "description": "Максимум символов в ответе (200-8000)",
                        "default": 4000,
                    },
                },
                "required": ["url"],
            },
        },
    },
]

WEB_FUNCTIONS: dict[str, Any] = {
    "web_search": web_search,
    "fetch_url": fetch_url,
}
