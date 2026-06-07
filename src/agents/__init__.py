"""Agentic workflow module for autonomous.tw.

Phase 4b — Multi-Agent Refinement Architecture

Instead of a linear pipeline, the agentic workflow uses:
- Dispatcher Agent: Analyzes the full item set and assigns each item to the
  most appropriate domain specialist.
- Specialist Agents: Domain experts (AI Tech, Taiwan Affairs, Intl Politics,
  Sports, KM) that perform targeted analysis with domain-specific scoring
  criteria.
- Synthesizer Agent: Aggregates specialist findings, resolves cross-domain
  overlaps, and produces the final scored/enriched item set.

This runs as an optional alternative to the standard linear pipeline and
can be enabled by config or used as a second-pass refinement layer.
"""