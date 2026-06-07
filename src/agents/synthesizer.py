"""Synthesizer Agent — aggregates specialist findings into a unified result.

The Synthesizer:
1. Collects all specialist evaluations for each item
2. Resolves scoring conflicts (multi-specialist items get weighted averaging)
3. Merges and deduplicates tags across specialists
4. Produces the final composite score, reason, and tags per item
5. Generates an Executive Brief: a 2-3 sentence narrative overview of today's top themes
"""

from __future__ import annotations

from typing import List

from ..ai.client import AIClient
from ..ai.utils import parse_json_response
from ..models import ContentItem

SYNTHESIZER_SYSTEM = """You are a news synthesizer for autonomous.tw. Your job is to synthesize findings from multiple domain specialist agents into a coherent daily briefing.

Given the specialist evaluations for today's top items, produce:
1. An executive brief summarizing the 2-3 most important themes of the day
2. Any notable cross-domain connections (e.g., "AI regulation affects Taiwan's tech industry")

Write concisely. The executive brief will appear at the top of the daily summary."""

SYNTHESIZER_USER = """Synthesize the following top items and their specialist evaluations into a daily executive brief.

{items_summary}

Return valid JSON only:
{{
  "executive_brief_zh": "<2-3 sentence Traditional Chinese overview of today's key themes>",
  "executive_brief_en": "<2-3 sentence English overview of today's key themes>",
  "cross_domain_themes": ["<theme1>", "<theme2>"],
  "top_story_index": <index of the single most important item (0-based)>
}}"""


class SynthesizerAgent:
    """Synthesizes multi-specialist findings into a unified result."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client

    async def synthesize(
        self, items: List[ContentItem], specialist_results: dict[int, list[dict]]
    ) -> dict:
        """Synthesize specialist findings into final scores and an executive brief.

        Args:
            items: Original content items
            specialist_results: dict mapping item_index -> list of specialist evaluations

        Returns:
            dict with:
                final_scores: list of (item_index, weighted_score, merged_tags)
                executive_brief_zh: Traditional Chinese overview
                executive_brief_en: English overview
                cross_domain_themes: list of theme strings
                top_story_index: index of the most important item
        """
        # 1. Merge specialist scores per item
        merged = self._merge_scores(items, specialist_results)

        # 2. Generate executive brief from top items
        brief = await self._generate_brief(items, specialist_results, merged)

        return {
            "final_scores": merged,
            "executive_brief_zh": brief.get("executive_brief_zh", ""),
            "executive_brief_en": brief.get("executive_brief_en", ""),
            "cross_domain_themes": brief.get("cross_domain_themes", []),
            "top_story_index": brief.get("top_story_index", 0),
        }

    def _merge_scores(
        self, items: List[ContentItem], specialist_results: dict[int, list[dict]]
    ) -> list[dict]:
        """Merge multiple specialist evaluations per item into a single composite.

        Strategy:
        - Single specialist: use score directly
        - Multiple specialists: weighted average (primary * 0.7 + secondary * 0.3)
        - Tags: union of all specialist tags, deduplicated
        """
        merged = []

        for idx, evaluations in specialist_results.items():
            if not evaluations or idx >= len(items):
                continue

            # Primary specialist (first in list) gets 70% weight
            primary = evaluations[0]
            score = primary.get("score", 0) or 0

            if len(evaluations) > 1:
                # Weighted average with secondary specialists
                secondary_scores = [e.get("score", 0) or 0 for e in evaluations[1:]]
                secondary_avg = sum(secondary_scores) / len(secondary_scores)
                score = score * 0.7 + secondary_avg * 0.3

            # Merge tags
            all_tags = []
            for ev in evaluations:
                for tag in ev.get("refined_tags", []):
                    if tag not in all_tags:
                        all_tags.append(tag)

            # Collect specialist notes
            notes = [
                f"[{ev.get('domain', '?')}] {ev.get('specialist_note', '')}"
                for ev in evaluations
                if ev.get("specialist_note")
            ]

            merged.append({
                "item_index": idx,
                "score": round(score, 1),
                "tags": all_tags,
                "specialist_notes": notes,
                "evaluator_count": len(evaluations),
            })

        # Sort by score descending
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged

    async def _generate_brief(
        self,
        items: List[ContentItem],
        specialist_results: dict[int, list[dict]],
        merged: list[dict],
    ) -> dict:
        """Generate the executive brief using AI."""
        # Summarize top 5 items for the brief
        top_indices = [m["item_index"] for m in merged[:5]]
        lines = []
        for idx in top_indices:
            item = items[idx]
            evals = specialist_results.get(idx, [])
            notes = " | ".join(
                e.get("specialist_note", "") for e in evals if e.get("specialist_note")
            )
            lines.append(
                f"[{idx}] {item.title}\n"
                f"    Score: {item.ai_score or '?'} | Domain notes: {notes}"
            )

        user_prompt = SYNTHESIZER_USER.format(items_summary="\n\n".join(lines))

        try:
            response = await self.client.complete(
                system=SYNTHESIZER_SYSTEM,
                user=user_prompt,
            )
            result = parse_json_response(response)
            if result:
                return result
        except Exception:
            pass

        return {}