"""Agentic Workflow Orchestrator.

Ties together Dispatcher → Specialists → Synthesizer into a single
orchestrated flow that can run as an alternative to or enhancement of
the standard linear pipeline.

Usage:
    orchestrator = AgenticOrchestrator(ai_client)
    result = await orchestrator.run(items, enrich=True)
    # result.items have updated scores/tags, result.brief has executive summary
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List

from ..ai.client import AIClient
from ..models import ContentItem
from .dispatcher import DispatcherAgent
from .specialists import SpecialistAgent, DOMAIN_SYSTEMS
from .synthesizer import SynthesizerAgent

logger = logging.getLogger(__name__)


@dataclass
class AgenticResult:
    """Output of the agentic workflow."""

    items: List[ContentItem] = field(default_factory=list)
    executive_brief_zh: str = ""
    executive_brief_en: str = ""
    cross_domain_themes: List[str] = field(default_factory=list)
    top_story_index: int = 0
    routing: dict = field(default_factory=dict)
    specialist_count: int = 0


class AgenticOrchestrator:
    """Orchestrates the Dispatcher → Specialists → Synthesizer flow.

    This is the main entry point for agentic-mode processing.
    """

    def __init__(self, ai_client: AIClient):
        self.client = ai_client
        self.dispatcher = DispatcherAgent(ai_client)

    async def run(self, items: List[ContentItem]) -> AgenticResult:
        """Execute the full agentic workflow.

        Args:
            items: Content items to process (already fetched and deduplicated)

        Returns:
            AgenticResult with updated items, brief, and metadata
        """
        if not items:
            return AgenticResult(items=[])

        logger.info(f"Agentic workflow starting for {len(items)} items")

        # Phase 1: Dispatch — route items to specialists
        routing = await self.dispatcher.route(items)
        logger.info(
            f"Dispatch complete: "
            + ", ".join(f"{k}={len(v)}" for k, v in routing["assignments"].items())
        )

        # Phase 2: Specialists — parallel domain analysis
        specialist_results = await self._run_specialists(items, routing["assignments"])

        total_evals = sum(len(v) for v in specialist_results.values())
        logger.info(f"Specialists produced {total_evals} evaluations")

        # Phase 3: Synthesize — merge scores, generate brief
        synthesizer = SynthesizerAgent(self.client)
        synthesis = await synthesizer.synthesize(items, specialist_results)

        # Apply merged scores back to items
        self._apply_scores(items, synthesis["final_scores"])

        # Stamp provenance
        for item in items:
            item.add_provenance(
                "agentic_refined",
                f"specialists={routing['assignments']} brief={'yes' if synthesis['executive_brief_zh'] else 'no'}",
            )

        return AgenticResult(
            items=items,
            executive_brief_zh=synthesis.get("executive_brief_zh", ""),
            executive_brief_en=synthesis.get("executive_brief_en", ""),
            cross_domain_themes=synthesis.get("cross_domain_themes", []),
            top_story_index=synthesis.get("top_story_index", 0),
            routing=routing,
            specialist_count=total_evals,
        )

    async def _run_specialists(
        self, items: List[ContentItem], assignments: dict[str, list[int]]
    ) -> dict[int, list[dict]]:
        """Run all specialists in parallel over their assigned items.

        Returns:
            dict mapping item_index -> list of specialist evaluation dicts
        """
        results: dict[int, list[dict]] = {}

        async def _run_one(domain: str, indices: list[int]) -> None:
            if not indices:
                return
            specialist = SpecialistAgent(domain, self.client)
            domain_items = [items[i] for i in indices if i < len(items)]
            evals = await specialist.evaluate_batch(domain_items)
            for ev in evals:
                item_idx = ev.pop("item_id", None)
                if item_idx is not None:
                    results.setdefault(item_idx, []).append(ev)

        tasks = [
            _run_one(domain, indices)
            for domain, indices in assignments.items()
            if indices
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    @staticmethod
    def _apply_scores(items: List[ContentItem], merged: list[dict]) -> None:
        """Apply merged scores and tags back to the original items."""
        for m in merged:
            idx = m["item_index"]
            if idx >= len(items):
                continue
            item = items[idx]

            # Blend new specialist score with existing AI score
            old_score = item.ai_score or 0
            new_score = m["score"]
            # If specialist score is meaningfully different, blend
            if abs(new_score - old_score) > 1.0:
                item.ai_score = round((old_score * 0.4 + new_score * 0.6), 1)
            else:
                item.ai_score = round(max(old_score, new_score), 1)

            # Merge tags (keep existing + add specialist-refined ones)
            existing = set(item.ai_tags or [])
            for tag in m.get("tags", []):
                if tag not in existing:
                    item.ai_tags.append(tag)

            # Store specialist notes in metadata
            notes = m.get("specialist_notes", [])
            if notes:
                item.metadata["specialist_notes"] = notes