"""Research provider — RSS/Atom feeds from official publishers (live) or demo samples (mock).

Live mode needs no credentials: it reads public RSS feeds of company blogs
listed in SOCIAL_RESEARCH_FEEDS. Everything fetched is untrusted DATA.
Mock mode returns clearly labelled demo records (is_demo=1).
"""

import datetime
import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from ..config import scfg

logger = logging.getLogger("core8.social.research")

_NS = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}


def _text(el, path, ns=None) -> str:
    found = el.find(path, ns or {})
    return (found.text or "").strip() if found is not None and found.text else ""


def _parse_date(value: str) -> str | None:
    if not value:
        return None
    for parser in (parsedate_to_datetime, datetime.datetime.fromisoformat):
        try:
            dt = parser(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return None


def parse_feed(xml_text: str, feed_url: str) -> list[dict]:
    """Parse RSS 2.0 or Atom into normalised records. Never raises on bad items."""
    out: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    publisher = ""
    channel = root.find("channel")
    if channel is not None:  # RSS 2.0
        publisher = _text(channel, "title")
        for item in channel.findall("item"):
            link = _text(item, "link") or (item.find("guid").text if item.find("guid") is not None else "")
            if not link:
                continue
            out.append({
                "title": _text(item, "title")[:300],
                "url": link.strip(),
                "publisher": publisher,
                "published_at": _parse_date(_text(item, "pubDate") or _text(item, "dc:date", _NS)),
                "summary": _strip_html(_text(item, "description"))[:1200],
                "feed_url": feed_url,
            })
    else:  # Atom
        publisher = _text(root, "atom:title", _NS)
        for entry in root.findall("atom:entry", _NS):
            link_el = entry.find("atom:link", _NS)
            link = link_el.get("href", "") if link_el is not None else ""
            if not link:
                continue
            out.append({
                "title": _text(entry, "atom:title", _NS)[:300],
                "url": link.strip(),
                "publisher": publisher,
                "published_at": _parse_date(_text(entry, "atom:published", _NS)
                                            or _text(entry, "atom:updated", _NS)),
                "summary": _strip_html(_text(entry, "atom:summary", _NS)
                                       or _text(entry, "atom:content", _NS))[:1200],
                "feed_url": feed_url,
            })
    return out


def _strip_html(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", text or "").replace("&nbsp;", " ").strip()


class ResearchProvider:
    def __init__(self):
        self.mode = "mock" if scfg.research_mode == "mock" else "live"
        self.feeds = scfg.research_feeds

    async def fetch(self, max_per_feed: int = 10) -> tuple[list[dict], list[str]]:
        """Returns (records, errors). In mock mode returns demo samples."""
        if self.mode == "mock":
            from ..demo_data import DEMO_SOURCES
            return [dict(s, is_demo=1) for s in DEMO_SOURCES], []
        records: list[dict] = []
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True,
                                     headers={"User-Agent": "Core8AI-SocialManager/0.1 (+https://core8-ai.com)"}) as client:
            for url in self.feeds:
                try:
                    r = await client.get(url)
                    if r.status_code >= 400:
                        errors.append(f"{url}: HTTP {r.status_code}")
                        continue
                    items = parse_feed(r.text, url)[:max_per_feed]
                    for it in items:
                        it["is_demo"] = 0
                        it["provider"] = "rss"
                    records.extend(items)
                except Exception as e:  # network blocked, DNS, TLS …
                    errors.append(f"{url}: {type(e).__name__}")
        return records, errors


research = ResearchProvider()
