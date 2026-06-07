"""Specialist Agents — domain-specific content analysis.

Each specialist applies domain-tuned scoring criteria to items assigned
by the Dispatcher. Specialists run in parallel for efficiency.

Specialists:
- AITechSpecialist: AI/ML breakthroughs, tools, research
- TaiwanAffairsSpecialist: Local politics, cross-strait, economy
- IntlPoliticsSpecialist: Geopolitics, conflicts, diplomacy
- SportsSpecialist: International events, Taiwanese athletes
- KMSpecialist: Productivity, PKM, learning methods
"""

from __future__ import annotations

from typing import List

from ..ai.client import AIClient
from ..ai.utils import parse_json_response
from ..models import ContentItem

# ── Specialist System Prompts ─────────────────────────

AI_TECH_SYSTEM = """You are an AI Technology specialist evaluating news for Taiwanese readers.

Score on 0-10, emphasizing:
- Technical novelty and depth (+2 if genuinely novel)
- Relevance to Taiwan's AI ecosystem (+1 if Taiwan-related)
- Practical impact on developers/researchers
- Quality of technical discussion in comments

Return JSON: {"score": <float>, "reason": "<explanation>", "refined_tags": [...], "specialist_note": "<domain insight>"}"""

TAIWAN_AFFAIRS_SYSTEM = """You are a Taiwan Current Affairs specialist evaluating news for Taiwanese readers.

Score on 0-10, emphasizing:
- Direct relevance to Taiwan (politics, economy, society, cross-strait)
- Credibility and objectivity of the source
- Timeliness (breaking vs. background)
- Potential impact on Taiwanese society

Return JSON: {"score": <float>, "reason": "<explanation>", "refined_tags": [...], "specialist_note": "<domain insight>"}"""

INTL_POLITICS_SYSTEM = """You are an International Politics specialist evaluating news for Taiwanese readers.

Score on 0-10, emphasizing:
- Geopolitical significance, especially for the Indo-Pacific region
- Impact on Taiwan's international standing or security
- Quality of analysis (not just reporting)
- Multi-perspective coverage (does it present diverse viewpoints?)

Return JSON: {"score": <float>, "reason": "<explanation>", "refined_tags": [...], "specialist_note": "<domain insight>"}"""

SPORTS_SYSTEM = """You are a Sports specialist evaluating news for Taiwanese readers.

Score on 0-10, emphasizing:
- Taiwanese athlete/team involvement (+2 if Taiwan-related)
- Significance of the event (major international > domestic league)
- Human interest and story quality
- Esports relevance for Taiwan's gaming community

Return JSON: {"score": <float>, "reason": "<explanation>", "refined_tags": [...], "specialist_note": "<domain insight>"}"""

KM_SYSTEM = """You are a Knowledge Management specialist evaluating news for Taiwanese readers.

Score on 0-10, emphasizing:
- Practical utility for knowledge workers
- Novelty of the method or tool
- Applicability to common workflows (note-taking, research, learning)
- Quality of explanation/tutorial value

Return JSON: {"score": <float>, "reason": "<explanation>", "refined_tags": [...], "specialist_note": "<domain insight>"}"""

DOMAIN_SYSTEMS = {
    "ai-tech": AI_TECH_SYSTEM,
    "taiwan-affairs": TAIWAN_AFFAIRS_SYSTEM,
    "intl-politics": INTL_POLITICS_SYSTEM,
    "sports": SPORTS_SYSTEM,
    "knowledge-mgmt": KM_SYSTEM,
}

SPECIALIST_USER = """Evaluate this news item from your domain perspective.

Title: {title}
Source: {source}
Author: {author}
URL: {url}
Tags: {tags}
Summary: {summary}

{content_section}

Respond with valid JSON only:
{{
  "score": <float 0-10>,
  "reason": "<explanation>",
  "refined_tags": ["<tag1>", ...],
  "specialist_note": "<one-line domain insight>"
}}"""


class SpecialistAgent:
    """A single domain specialist that scores items from its perspective."""

    def __init__(self, domain: str, ai_client: AIClient):
        if domain not in DOMAIN_SYSTEMS:
            raise ValueError(f"Unknown domain: {domain}. Must be one of {list(DOMAIN_SYSTEMS)}")
        self.domain = domain
        self.client = ai_client
        self.system_prompt = DOMAIN_SYSTEMS[domain]

    async def evaluate(self, item: ContentItem) -> dict | None:
        """Score a single item from this specialist's domain perspective.

        Returns:
            dict with score, reason, refined_tags, specialist_note, or None on failure
        """
        content_section = ""
        if item.content:
            content_section = f"Content: {item.content[:1000]}"

        user_prompt = SPECIALIST_USER.format(
            title=item.title,
            source=item.source_type.value,
            author=item.author or "Unknown",
            url=str(item.url),
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            summary=item.ai_summary or item.title,
            content_section=content_section,
        )

        try:
            response = await self.client.complete(
                system=self.system_prompt,
                user=user_prompt,
            )
            result = parse_json_response(response)
            if result:
                result["domain"] = self.domain
                return result
        except Exception:
            pass

        return None

    async def evaluate_batch(self, items: List[ContentItem]) -> List[dict]:
        """Evaluate a batch of items (sequential within specialist, parallel across specialists)."""
        results = []
        for item in items:
            result = await self.evaluate(item)
            if result:
                result["item_id"] = items.index(item)
                results.append(result)
        return results