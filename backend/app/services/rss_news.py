"""
RSS 资讯抓取服务 —— 定时拉取 AI/科技 RSS，内存缓存，供前端欢迎页使用。
"""

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

FEEDS: list[tuple[str, str]] = [
    ("量子位", "https://www.qbitai.com/feed"),
    ("InfoQ", "https://www.infoq.cn/feed"),
    ("36氪", "https://36kr.com/feed"),
]

CACHE_TTL = 30 * 60  # 30 分钟
MAX_ITEMS_PER_FEED = 8
MAX_TOTAL = 20

_STRIP_HTML = re.compile(r"<[^>]+>")


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    summary: str
    published: str  # ISO-8601


_cache: list[dict] = []
_cache_ts: float = 0
_lock = asyncio.Lock()


def _parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _clean_html(html: str, max_len: int = 100) -> str:
    text = _STRIP_HTML.sub("", html).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def _fetch_feed(source_name: str, url: str) -> list[NewsItem]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 MyGPT-RSS/1.0"})
        resp = urlopen(req, timeout=10)
        data = resp.read().decode("utf-8", errors="replace")
        root = ET.fromstring(data)
    except Exception as e:
        logger.warning("RSS fetch failed [%s]: %s", source_name, e)
        return []

    items: list[NewsItem] = []
    for el in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        title = (el.findtext("title") or "").strip()
        if not title:
            continue
        link = (el.findtext("link") or "").strip()
        desc = _clean_html(el.findtext("description") or "")
        pub_raw = el.findtext("pubDate") or ""
        dt = _parse_date(pub_raw)
        published = dt.isoformat() if dt else ""

        items.append(NewsItem(
            title=title,
            link=link,
            source=source_name,
            summary=desc,
            published=published,
        ))
    return items


def _fetch_all() -> list[dict]:
    all_items: list[NewsItem] = []
    for source_name, url in FEEDS:
        all_items.extend(_fetch_feed(source_name, url))

    # 有发布时间的按时间倒序，没有的放后面
    with_date = [i for i in all_items if i.published]
    without_date = [i for i in all_items if not i.published]
    with_date.sort(key=lambda i: i.published, reverse=True)
    result = with_date + without_date
    return [asdict(i) for i in result[:MAX_TOTAL]]


async def get_news() -> list[dict]:
    global _cache, _cache_ts
    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return _cache

    async with _lock:
        if _cache and (now - _cache_ts) < CACHE_TTL:
            return _cache
        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(None, _fetch_all)
        if items:
            _cache = items
            _cache_ts = time.time()
            logger.info("RSS cache refreshed: %d items", len(items))
        return _cache or items
