"""Dispatcher Agent — analyses full batch and routes to domain specialists.

The Dispatcher's job:
1. Quickly scan all items' titles, summaries, and tags
2. Assign each item to the most appropriate domain specialist
3. Identify cross-domain items that need multi-specialist review
4. Flag items that need enrichment before specialist analysis

This is intentionally lightweight — one AI call for the whole batch,
returning a structured routing plan.
"""

from __future__ import annotations

from typing import List

from ..ai.client import AIClient
from ..ai.utils import parse_json_response
from ..models import ContentItem

DISPATCHER_SYSTEM = """You are a news dispatcher for autonomous.tw, routing news items to domain specialist agents.

You have five specialist agents:
1. **AI Tech Specialist** — AI breakthroughs, LLMs, ML research, AI tools, AI policy/regulation
2. **Taiwan Affairs Specialist** — Local Taiwan politics, cross-strait relations, economy, society, culture
3. **International Politics Specialist** — Global geopolitics, major elections, conflicts, diplomacy, trade
4. **Sports Specialist** — International sports events, Taiwanese athletes, esports
5. **Knowledge Management Specialist** — Productivity, PKM tools, learning methods, workflow optimization

For each item, decide:
- Which ONE specialist is the primary owner (primary_domain)
- Whether any SECONDARY specialist should also review it (secondary_domains, 0-1 extra)
- Whether the item needs enrichment before specialist analysis (needs_enrichment)

Routing rules:
- Taiwan-related tech news → primary AI Tech, secondary Taiwan Affairs
- Cross-strait tech policy → primary Taiwan Affairs, secondary AI Tech
- Global AI policy with Taiwan impact → primary Intl Politics, secondary Taiwan Affairs
- Taiwanese athlete achievements → primary Sports, secondary Taiwan Affairs"""

DISPATCHER_USER = """Route the following {count} news items to domain specialists.

{items}

Return valid JSON only:
{{
  "routing": [
    {{
      "item_id": "<item index (0-based)>",
      "primary_domain": "<ai-tech|taiwan-affairs|intl-politics|sports|knowledge-mgmt>",
      "secondary_domains": ["<optional secondary domain>"],
      "needs_enrichment": false,
      "reason": "<one-line reasoning>"
    }},
    ...
  ]
}}"""


class DispatcherAgent:
    """Scans and routes items to domain specialists."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client

    async def route(self, items: List[ContentItem]) -> dict:
        """Route items to specialists and return a routing plan.

        Args:
            items: Content items to route

        Returns:
            dict with:
                routing: List of routing decisions (one per item)
                assignments: dict mapping domain -> list of item indices
        """
        if not items:
            return {"routing": [], "assignments": {}}

        items_text = self._format_items(items)
        user_prompt = DISPATCHER_USER.format(count=len(items), items=items_text)

        try:
            response = await self.client.complete(
                system=DISPATCHER_SYSTEM,
                user=user_prompt,
            )
            result = parse_json_response(response)
            if result is None:
                return self._fallback_routing(items)

            routing = result.get("routing", [])
            assignments = self._build_assignments(routing, len(items))
            return {"routing": routing, "assignments": assignments}

        except Exception:
            return self._fallback_routing(items)

    def _format_items(self, items: List[ContentItem]) -> str:
        """Format items for the dispatcher prompt."""
        lines = []
        for i, item in enumerate(items):
            tags = ", ".join(item.ai_tags) if item.ai_tags else "—"
            summary = item.ai_summary or "—"
            lines.append(
                f"[{i}] {item.title}\n"
                f"    Source: {item.source_type.value}\n"
                f"    Tags: {tags}\n"
                f"    Summary: {summary}"
            )
        return "\n\n".join(lines)

    def _build_assignments(
        self, routing: list, item_count: int
    ) -> dict[str, list[int]]:
        """Build domain -> [item_indices] mapping from routing plan."""
        assignments: dict[str, list[int]] = {
            "ai-tech": [],
            "taiwan-affairs": [],
            "intl-politics": [],
            "sports": [],
            "knowledge-mgmt": [],
        }

        for entry in routing:
            idx = entry.get("item_id", -1)
            if not isinstance(idx, int) or idx < 0 or idx >= item_count:
                continue

            primary = entry.get("primary_domain", "")
            if primary in assignments:
                assignments[primary].append(idx)

            for secondary in entry.get("secondary_domains", []):
                if secondary in assignments and idx not in assignments[secondary]:
                    assignments[secondary].append(idx)

        return assignments

    def _fallback_routing(self, items: List[ContentItem]) -> dict:
        """Tag-based fallback routing when AI call fails."""
        assignments: dict[str, list[int]] = {
            "ai-tech": [],
            "taiwan-affairs": [],
            "intl-politics": [],
            "sports": [],
            "knowledge-mgmt": [],
        }

        tag_to_domain = {
            "ai-tech": "ai-tech",
            "taiwan-affairs": "taiwan-affairs",
            "intl-politics": "intl-politics",
            "sports": "sports",
            "knowledge-mgmt": "knowledge-mgmt",
            "llm": "ai-tech", "ml": "ai-tech", "deep-learning": "ai-tech",
            "cross-strait": "taiwan-affairs",
            "elections": "intl-politics",
            "baseball": "sports",
            "productivity-tools": "knowledge-mgmt",
        }

        for i, item in enumerate(items):
            routed = False
            for tag in item.ai_tags or []:
                domain = tag_to_domain.get(tag.lower())
                if domain and domain in assignments:
                    assignments[domain].append(i)
                    routed = True
                    break
            if not routed:
                assignments["ai-tech"].append(i)  # default bucket

        return {"routing": [], "assignments": assignments}