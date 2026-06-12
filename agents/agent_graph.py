"""
ARIA — Agent Graph (LangGraph Orchestration)
Wires Scout → Personalizer → Compliance → Engagement into a
stateful multi-agent pipeline with iterative feedback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass
class ARIAState:
    """Shared state passed between all ARIA agents."""
    # Input
    raw_signals: list[dict] = field(default_factory=list)

    # Scout output
    scored_prospects: list[dict] = field(default_factory=list)

    # Personalizer output
    personalized_messages: list[dict] = field(default_factory=list)

    # Compliance output
    cleared_ids: list[str] = field(default_factory=list)
    compliance_decisions: list[dict] = field(default_factory=list)

    # Engagement output
    dispatched: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    # Pipeline metadata
    run_id: str = ""
    errors: list[str] = field(default_factory=list)
    stage: str = "init"


class ARIAPipeline:
    """
    ARIA Multi-Agent Pipeline.

    Stages:
    1. scout      — score & segment prospects
    2. personalize — generate personalized messages
    3. comply     — run RBI compliance checks
    4. engage     — dispatch outreach
    5. feedback   — log results for model retraining

    In production, each stage is a LangGraph node connected via
    StateGraph edges. This class provides the same interface for
    hackathon/demo purposes.
    """

    def __init__(self):
        from agents.scout_agent import ScoutAgent, ProspectSignal
        from agents.personalizer_agent import PersonalizerAgent, PersonalizationRequest
        from compliance.rbi_rules import RBIComplianceEngine
        from engagement.engagement_agent import EngagementAgent

        self.scout = ScoutAgent()
        self.personalizer = PersonalizerAgent()
        self.compliance = RBIComplianceEngine()
        self.engagement = EngagementAgent()

    def run(self, raw_signals: list[dict], run_id: str = "run_001") -> ARIAState:
        """Execute the full ARIA pipeline for a batch of prospect signals."""
        from agents.scout_agent import ProspectSignal
        from agents.personalizer_agent import PersonalizationRequest

        state = ARIAState(raw_signals=raw_signals, run_id=run_id)
        logger.info(f"[{run_id}] Pipeline started — {len(raw_signals)} signals")

        # ── Stage 1: Scout ──────────────────────────────────────────────
        state.stage = "scout"
        try:
            signals = [ProspectSignal(**s) for s in raw_signals]
            scored = self.scout.score_batch(signals)
            state.scored_prospects = [vars(p) for p in scored]
            logger.info(f"[{run_id}] Scout: scored {len(scored)} prospects")
        except Exception as e:
            state.errors.append(f"Scout stage error: {e}")
            logger.error(f"[{run_id}] Scout error: {e}")
            return state

        # ── Stage 2: Personalizer ───────────────────────────────────────
        state.stage = "personalize"
        try:
            requests = [
                PersonalizationRequest(
                    prospect_id=p["prospect_id"],
                    product_category=p["recommended_product_category"],
                    life_event=p["life_event_detected"],
                    prospect_profile=next(
                        (s for s in raw_signals if s["prospect_id"] == p["prospect_id"]), {}
                    ),
                )
                for p in state.scored_prospects
                if p["priority_tier"] in ("high", "medium")
            ]
            messages = self.personalizer.generate_batch(requests)
            state.personalized_messages = [vars(m) for m in messages]
            logger.info(f"[{run_id}] Personalizer: generated {len(messages)} messages")
        except Exception as e:
            state.errors.append(f"Personalizer stage error: {e}")
            logger.error(f"[{run_id}] Personalizer error: {e}")

        # ── Stage 3: Compliance ─────────────────────────────────────────
        state.stage = "comply"
        try:
            prospect_data = [
                {
                    "prospect_id": p["prospect_id"],
                    "has_existing_sbi_account": next(
                        (s.get("has_existing_sbi_account", False)
                         for s in raw_signals if s["prospect_id"] == p["prospect_id"]), False
                    ),
                }
                for p in state.scored_prospects
                if p["priority_tier"] in ("high", "medium")
            ]
            cleared_ids, decisions = self.compliance.bulk_evaluate(prospect_data)
            state.cleared_ids = cleared_ids
            state.compliance_decisions = [vars(d) for d in decisions]
            logger.info(f"[{run_id}] Compliance: {len(cleared_ids)}/{len(prospect_data)} cleared")
        except Exception as e:
            state.errors.append(f"Compliance stage error: {e}")
            logger.error(f"[{run_id}] Compliance error: {e}")

        # ── Stage 4: Engagement ─────────────────────────────────────────
        state.stage = "engage"
        try:
            cleared_messages = [
                m for m in state.personalized_messages
                if m["prospect_id"] in state.cleared_ids
            ]
            channel_map = {
                p["prospect_id"]: p["outreach_channel"]
                for p in state.scored_prospects
            }
            dispatched, failed = self.engagement.dispatch_batch(
                cleared_messages, channel_map
            )
            state.dispatched = dispatched
            state.failed = failed
            logger.info(f"[{run_id}] Engagement: {len(dispatched)} dispatched, {len(failed)} failed")
        except Exception as e:
            state.errors.append(f"Engagement stage error: {e}")
            logger.error(f"[{run_id}] Engagement error: {e}")

        state.stage = "complete"
        logger.info(f"[{run_id}] Pipeline complete.")
        return state

    def get_summary(self, state: ARIAState) -> dict[str, Any]:
        """Return a summary dict for dashboard/logging."""
        return {
            "run_id": state.run_id,
            "stage": state.stage,
            "total_signals": len(state.raw_signals),
            "scored": len(state.scored_prospects),
            "high_priority": sum(1 for p in state.scored_prospects if p.get("priority_tier") == "high"),
            "messages_generated": len(state.personalized_messages),
            "compliance_cleared": len(state.cleared_ids),
            "dispatched": len(state.dispatched),
            "failed": len(state.failed),
            "errors": state.errors,
            "conversion_rate_estimate": (
                len(state.dispatched) / max(len(state.raw_signals), 1) * 0.12
            ),
        }
