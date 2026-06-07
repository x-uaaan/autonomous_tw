"""Auto-illustration pipeline for daily summaries.

Extracts visual keywords from high-scoring content items, searches for
relevant images via Unsplash (no API key required for free tier), and
stores the best-matching image URL in the item's metadata for use by
the card-based UI.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import List, Optional
from urllib.parse import quote_plus, urlencode

import httpx

from ..models import ContentItem

logger = logging.getLogger(__name__)

UNSPLASH_API = "https://api.unsplash.com"
_UNSPLASH_ACCESS_KEY_ENV = "UNSPLASH_ACCESS_KEY"

# Fallback: Unsplash Source (no API key needed, but limited)
# https://source.unsplash.com/featured/?{keywords}
UNSPLASH_SOURCE = "https://source.unsplash.com"


class IllustrationPipeline:
    """Extracts visual keywords and fetches matching images for content items.

    Uses Unsplash API when UNSPLASH_ACCESS_KEY is set, otherwise falls back
    to Unsplash Source (free, no key required, but less control).
    """

    def __init__(self, http_client: httpx.AsyncClient, languages: List[str] | None = None):
        self.client = http_client
        self.languages = languages or ["zh", "en"]
        self.access_key = os.environ.get(_UNSPLASH_ACCESS_KEY_ENV)

    # ── Public API ──────────────────────────────────────────

    async def illustrate_hero(self, item: ContentItem) -> None:
        """Fetch an illustration image for the Hero item.

        If the item already has an illustration, this is a no-op.
        The image URL is stored in item.metadata["hero_image"].

        Args:
            item: The highest-scored ContentItem to illustrate
        """
        if item.metadata.get("hero_image"):
            return

        keywords = await self._extract_keywords(item)
        if not keywords:
            keywords = self._fallback_keywords(item)

        image_url = await self._search_image(keywords)
        if image_url:
            item.metadata["hero_image"] = image_url
            item.metadata["hero_image_keywords"] = keywords
            item.add_provenance("illustrated", f"hero_image keywords={keywords[:80]}")
            logger.info(f"Illustrated hero: {item.title[:60]} -> {keywords[:60]}")

    async def illustrate_batch(self, items: List[ContentItem]) -> None:
        """Fetch illustrations for all items (limited concurrency).

        Only the Hero item gets a full-resolution image; Featured items
        get thumbnail-sized images.

        Args:
            items: Content items to illustrate (modified in-place)
        """
        if not items:
            return

        # Hero item: full illustration
        await self.illustrate_hero(items[0])

        # Remaining items: thumbnail search (limited to 4, bounded concurrency)
        sem = asyncio.Semaphore(3)

        async def _illustrate_thumb(item: ContentItem, idx: int) -> None:
            async with sem:
                try:
                    keywords = await self._extract_keywords(item)
                    if not keywords:
                        keywords = self._fallback_keywords(item)
                    url = await self._search_image(keywords, thumb=True)
                    if url:
                        item.metadata["thumb_image"] = url
                        logger.debug(f"Thumbnail [{idx}]: {item.title[:40]}")
                except Exception as exc:
                    logger.debug(f"Thumbnail failed for item {idx}: {exc}")

        tasks = [_illustrate_thumb(item, i) for i, item in enumerate(items[1:6])]
        await asyncio.gather(*tasks, return_exceptions=True)

    # ── Keyword Extraction ─────────────────────────────────

    async def _extract_keywords(self, item: ContentItem) -> str:
        """Extract visual keywords from a content item.

        Strategy:
        1. Use AI tags as primary signal (already domain-classified)
        2. Combine with title for specificity
        3. Remove generic/abstract terms that won't produce good images

        Returns a space-separated keyword string for image search.
        """
        tags = item.ai_tags or []
        title = item.title or ""

        # Filter out overly abstract tags
        abstract = {
            "ai-tech", "taiwan-affairs", "intl-politics", "sports",
            "knowledge-mgmt", "trending", "research", "news", "theory",
            "tools", "testing", "systems", "performance", "security",
        }
        concrete_tags = [t for t in tags if t.lower() not in abstract]

        # Build keyword string: concrete tags first, then title nouns
        parts = concrete_tags[:3]

        # Extract key noun phrases from title (simple heuristic)
        title_words = title.replace(",", " ").replace(":", " ").replace("-", " ").split()
        significant = [w for w in title_words if len(w) > 3 and w.lower() not in abstract]
        # Add up to 2 significant title words
        for w in significant:
            if w.lower() not in [p.lower() for p in parts]:
                parts.append(w)
                if len(parts) >= 4:
                    break

        if not parts and title_words:
            # Fallback: just use the first 2-3 meaningful title words
            parts = title_words[:3]

        return " ".join(parts)

    def _fallback_keywords(self, item: ContentItem) -> str:
        """Generate fallback keywords when AI tags are unavailable.

        Uses the source type and title to guess a reasonable search query.
        """
        source_keywords = {
            "github": "open source code programming",
            "hackernews": "technology startup innovation",
            "reddit": "discussion community",
            "rss": "news headlines",
            "telegram": "social media communication",
            "twitter": "social media news",
            "threads": "social media discussion",
            "openbb": "finance business stock market",
            "ossinsight": "open source developer tools",
        }
        source = item.source_type.value
        base = source_keywords.get(source, "technology news")

        # Mix in the first 2-3 words from the title
        title_parts = item.title.split()[:3]
        title_str = " ".join([w for w in title_parts if len(w) > 3])

        return f"{title_str} {base}" if title_str else base

    # ── Image Search ────────────────────────────────────────

    async def _search_image(self, keywords: str, thumb: bool = False) -> Optional[str]:
        """Search for an image matching the given keywords.

        Args:
            keywords: Space-separated search keywords
            thumb: If True, request a thumbnail-sized image

        Returns:
            Image URL string, or None if no suitable image found
        """
        if self.access_key:
            return await self._search_unsplash_api(keywords, thumb)
        else:
            return self._unsplash_source_url(keywords, thumb)

    async def _search_unsplash_api(
        self, keywords: str, thumb: bool = False
    ) -> Optional[str]:
        """Search via Unsplash API (requires access key).

        Returns the raw image URL for direct embedding.
        """
        params = {
            "query": keywords,
            "per_page": 1,
            "orientation": "landscape",
            "content_filter": "high",
        }
        headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
        }

        try:
            resp = await self.client.get(
                f"{UNSPLASH_API}/search/photos",
                params=params,
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                urls = results[0].get("urls", {})
                # Return raw image, not the Unsplash page
                if thumb:
                    return urls.get("thumb") or urls.get("small")
                return urls.get("regular") or urls.get("full") or urls.get("raw", "")
        except Exception as exc:
            logger.debug(f"Unsplash API failed: {exc}")

        return None

    def _unsplash_source_url(self, keywords: str, thumb: bool = False) -> str:
        """Generate an Unsplash Source URL (no API key needed).

        Unsplash Source returns a random matching photo.
        https://source.unsplash.com/featured/?{keywords}
        """
        encoded = quote_plus(keywords)
        if thumb:
            return f"{UNSPLASH_SOURCE}/400x300/?{encoded}"
        return f"{UNSPLASH_SOURCE}/1200x630/?{encoded}"

    # ── UI Helpers ──────────────────────────────────────────

    @staticmethod
    def hero_image_html(item: ContentItem) -> str:
        """Generate HTML <img> tag for the hero image."""
        url = item.metadata.get("hero_image")
        if not url:
            return ""
        title = item.metadata.get("title_zh") or item.title
        return (
            f'<img src="{url}" alt="{title}" '
            f'class="hz-hero-image" loading="eager" '
            f'width="1200" height="630">'
        )

    @staticmethod
    def thumb_image_html(item: ContentItem) -> str:
        """Generate HTML <img> tag for a thumbnail."""
        url = item.metadata.get("thumb_image")
        if not url:
            return ""
        title = item.metadata.get("title_zh") or item.title
        return (
            f'<img src="{url}" alt="{title}" '
            f'class="hz-card-thumb" loading="lazy" '
            f'width="400" height="300">'
        )