"""Threads.net scraper — keyword/trend monitoring for Taiwan community.

Threads.net has no public API. This scraper uses web scraping via httpx
to fetch public profile feeds and keyword-search pages, then extracts
structured content from the embedded JSON-LD and HTML metadata.

Strategy:
- For keyword monitoring: fetch threads.net/search?q=<keyword>
- For profile monitoring: fetch threads.net/@<username>
- Parse embedded <script type="application/ld+json"> for structured data
- Fall back to HTML <meta> tags and visible text extraction
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import List, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models import ContentItem, SourceType

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Threads trends are most active in Taiwan — default keywords to monitor
_DEFAULT_KEYWORDS: List[str] = [
    "台灣", "Taiwan",
    "threads 熱門",
]


class ThreadsScraper(BaseScraper):
    """Fetch Threads.net posts by keyword or from public profiles."""

    def __init__(self, config: dict, http_client: httpx.AsyncClient):
        super().__init__(config, http_client)
        self.keywords: List[str] = config.get("keywords", _DEFAULT_KEYWORDS)
        self.fetch_limit: int = config.get("fetch_limit", 15)

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.keywords:
            logger.debug("No Threads keywords configured, skipping.")
            return []

        logger.info(f"Fetching Threads for keywords: {self.keywords}")

        # Fan out: one search per keyword
        tasks = [self._search_keyword(kw, since) for kw in self.keywords]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: List[ContentItem] = []
        seen_ids: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Threads keyword search failed: {result}")
            elif isinstance(result, list):
                for item in result:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)

        logger.info(f"Fetched {len(all_items)} unique Threads posts.")
        return all_items

    async def _search_keyword(
        self, keyword: str, since: datetime
    ) -> List[ContentItem]:
        """Search Threads.net for a keyword and return matching posts.

        Uses the public search endpoint and extracts embedded JSON-LD data,
        falling back to HTML parsing.
        """
        encoded = quote_plus(keyword)
        url = f"https://www.threads.net/search?q={encoded}&serp_type=default"

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

        try:
            resp = await self.client.get(
                url, headers=headers, timeout=15.0, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"Threads HTTP error for '{keyword}': {exc}")
            return []

        return self._parse_search_response(resp.text, keyword, since)

    def _parse_search_response(
        self, html: str, keyword: str, since: datetime
    ) -> List[ContentItem]:
        """Extract post data from the Threads search page HTML.

        Threads pages embed data in multiple locations:
        1. JSON-LD <script type="application/ld+json"> blocks
        2. <meta> tags in <head>
        3. Visible post text in the main body

        We try all three and return whatever we can extract.
        """
        soup = BeautifulSoup(html, "html.parser")
        items: List[ContentItem] = []

        # Strategy 1: Extract JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and data.get("@type") == "SocialMediaPosting":
                    item = self._parse_ld_json(data, since)
                    if item:
                        items.append(item)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        # Strategy 2: Extract from <meta> tags and visible text
        if not items:
            items = self._parse_from_meta(soup, keyword, since)

        # Enforce fetch limit
        return items[: self.fetch_limit]

    def _parse_ld_json(
        self, data: dict, since: datetime
    ) -> Optional[ContentItem]:
        """Parse a JSON-LD SocialMediaPosting into a ContentItem."""
        try:
            url = data.get("url", "") or data.get("@id", "")
            if not url:
                return None

            # Extract Threads post ID from URL
            post_id = self._extract_post_id(url)
            if not post_id:
                return None

            # Parse date
            date_str = data.get("datePublished", "") or data.get("dateCreated", "")
            published_at = self._parse_date(date_str)
            if not published_at or published_at < since:
                return None

            author_data = data.get("author", {})
            author = (
                author_data.get("name", "")
                if isinstance(author_data, dict)
                else str(author_data)
            )

            text = data.get("text", "") or data.get("articleBody", "") or ""
            text = unescape(text)

            title_body = text[:60].replace("\n", " ").strip()
            if len(text) > 60:
                title_body += "..."

            return ContentItem(
                id=self._generate_id(SourceType.THREADS.value, "post", post_id),
                source_type=SourceType.THREADS,
                title=title_body or f"Threads post by {author}",
                url=url,
                content=text,
                author=author or "unknown",
                published_at=published_at,
                metadata={
                    "post_id": post_id,
                    "platform": "threads",
                    "interaction_count": data.get("interactionStatistic", []),
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse Threads JSON-LD: {exc}")
            return None

    def _parse_from_meta(
        self, soup: BeautifulSoup, keyword: str, since: datetime
    ) -> List[ContentItem]:
        """Fallback: extract post data from HTML <meta> tags and visible content.

        Threads pages typically include Open Graph and Twitter Card meta tags
        that carry basic post information even when JSON-LD is unavailable.
        """
        items: List[ContentItem] = []

        # Look for post URLs in the page
        post_url_pattern = re.compile(
            r'https?://(?:www\.)?threads\.net/@([^/]+)/post/([A-Za-z0-9_-]+)'
        )

        # Check all links on the page
        seen_urls: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("/"):
                href = f"https://www.threads.net{href}"

            match = post_url_pattern.search(href)
            if not match:
                continue

            username = match.group(1)
            post_id = match.group(2)

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Extract any nearby text as the post body
            parent_text = link.get_text(strip=True) or ""
            # Try to get more context from parent elements
            for parent in link.parents:
                if parent.name in ("article", "div", "section"):
                    text = parent.get_text(separator="\n", strip=True)
                    if len(text) > 20:
                        break
            else:
                text = parent_text

            if not text:
                continue

            title_body = text[:60].replace("\n", " ").strip()
            if len(text) > 60:
                title_body += "..."

            now = datetime.now(timezone.utc)
            if now < since:
                continue

            items.append(
                ContentItem(
                    id=self._generate_id(SourceType.THREADS.value, "post", post_id),
                    source_type=SourceType.THREADS,
                    title=title_body or f"Threads post by @{username}",
                    url=href,
                    content=text,
                    author=f"@{username}",
                    published_at=now,  # best-effort; actual date requires detail page fetch
                    metadata={
                        "post_id": post_id,
                        "platform": "threads",
                        "username": username,
                        "keyword_matched": keyword,
                    },
                )
            )

        return items

    @staticmethod
    def _extract_post_id(url: str) -> Optional[str]:
        """Extract the Threads post ID from a URL.

        Threads URL formats:
        - https://www.threads.net/@user/post/CxAbCdEfGhI
        - https://www.threads.net/t/CxAbCdEfGhI
        """
        patterns = [
            r"/post/([A-Za-z0-9_-]+)",
            r"/t/([A-Za-z0-9_-]+)",
        ]
        for pat in patterns:
            match = re.search(pat, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Parse a date string from Threads metadata into a datetime."""
        if not date_str:
            return None

        # Try ISO 8601 first
        try:
            from dateutil.parser import isoparse
            dt = isoparse(date_str)
        except Exception:
            # Try common formats
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
            ):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt