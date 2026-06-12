"""
ARIA — Scout Agent
Identifies and scores high-intent prospects for SBI customer acquisition
using XGBoost (prospect scoring) + LSTM (life-event prediction).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ProspectSignal:
    """Raw signal ingested from external / internal data sources."""
    prospect_id: str
    source: str                    # "job_portal" | "bc_network" | "yono_partial" | "pmjdy"
    age: int
    location_tier: int             # 1=metro, 2=tier2, 3=tier3, 4=rural
    employment_type: str           # "salaried" | "self_employed" | "student" | "gig"
    estimated_monthly_income: float
    has_existing_sbi_account: bool
    life_events: list[str] = field(default_factory=list)  # e.g. ["first_job", "marriage"]
    last_transaction_date: str | None = None
    existing_products: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredProspect:
    """Output of Scout Agent with acquisition probability and product affinity."""
    prospect_id: str
    acquisition_score: float       # 0.0–1.0 probability of conversion
    ltv_score: float               # Lifetime value estimate (normalized 0–1)
    priority_tier: str             # "high" | "medium" | "low"
    recommended_product_category: str
    life_event_detected: str | None
    outreach_channel: str          # "whatsapp" | "yono" | "bc" | "rm"
    reasoning: str
    scored_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ScoutAgent:
    """
    Scout Agent: ingests prospect signals and outputs scored, segmented leads.

    In production, XGBoost and LSTM models are loaded from MLflow / S3.
    This module ships with a rule-based scoring fallback for demo/hackathon use.
    """

    # Life-event → product affinity mapping
    LIFE_EVENT_PRODUCTS = {
        "first_job":        "salary_account",
        "marriage":         "joint_account",
        "home_purchase":    "home_loan",
        "vehicle_purchase": "auto_loan",
        "child_birth":      "recurring_deposit",
        "education":        "education_loan",
        "business_start":   "current_account",
        "retirement":       "senior_citizen_fd",
    }

    # Channel selection logic
    CHANNEL_RULES = {
        "tier1_salaried":   "whatsapp",
        "tier1_student":    "yono",
        "tier2_salaried":   "whatsapp",
        "tier2_self":       "bc",
        "tier3_any":        "bc",
        "tier4_any":        "bc",
        "high_value":       "rm",
    }

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self._xgb_model = None
        self._lstm_model = None
        logger.info("ScoutAgent initialized (rule-based fallback active)")

    def _extract_features(self, signal: ProspectSignal) -> np.ndarray:
        """Extract feature vector for ML model inference."""
        income_norm = min(signal.estimated_monthly_income / 200_000, 1.0)
        age_norm = (signal.age - 18) / (65 - 18)
        employment_enc = {"salaried": 1.0, "self_employed": 0.8, "gig": 0.6, "student": 0.4}.get(
            signal.employment_type, 0.5
        )
        location_enc = (5 - signal.location_tier) / 4.0  # tier1=1.0, tier4=0.25
        has_life_event = 1.0 if signal.life_events else 0.0
        is_existing = 1.0 if signal.has_existing_sbi_account else 0.0
        product_gap = max(0, 3 - len(signal.existing_products)) / 3.0

        return np.array([
            income_norm, age_norm, employment_enc,
            location_enc, has_life_event, is_existing, product_gap
        ], dtype=np.float32)

    def _rule_based_score(self, signal: ProspectSignal, features: np.ndarray) -> tuple[float, float]:
        """Fallback scoring when ML models are not loaded."""
        income_norm, age_norm, employment_enc, location_enc, has_life_event, is_existing, product_gap = features

        # Acquisition score: weighted linear combination
        acq_score = (
            0.25 * income_norm
            + 0.20 * employment_enc
            + 0.15 * age_norm
            + 0.20 * has_life_event
            + 0.10 * (1 - is_existing)  # new-to-bank is higher priority
            + 0.10 * location_enc
        )
        acq_score = float(np.clip(acq_score + np.random.normal(0, 0.03), 0.05, 0.98))

        # LTV score: income + age (younger = higher LTV)
        ltv_score = float(np.clip(0.6 * income_norm + 0.4 * (1 - age_norm * 0.5), 0.1, 0.95))

        return acq_score, ltv_score

    def _detect_life_event(self, signal: ProspectSignal) -> str | None:
        """Return the highest-priority life event detected."""
        priority_order = [
            "first_job", "home_purchase", "marriage",
            "vehicle_purchase", "education", "child_birth",
            "business_start", "retirement"
        ]
        for event in priority_order:
            if event in signal.life_events:
                return event
        return None

    def _select_channel(self, signal: ProspectSignal, acq_score: float) -> str:
        """Choose the optimal outreach channel for this prospect."""
        if acq_score > 0.75 and signal.estimated_monthly_income > 100_000:
            return "rm"
        if signal.location_tier >= 3:
            return "bc"
        if signal.employment_type == "student":
            return "yono"
        return "whatsapp"

    def _assign_tier(self, acq_score: float) -> str:
        if acq_score >= 0.65:
            return "high"
        elif acq_score >= 0.40:
            return "medium"
        return "low"

    def score_prospect(self, signal: ProspectSignal) -> ScoredProspect:
        """
        Score a single prospect signal and return a ScoredProspect.

        In production: replaces rule-based scoring with loaded XGBoost + LSTM models.
        """
        features = self._extract_features(signal)

        if self._xgb_model is not None:
            # Production path: XGBoost inference
            acq_score = float(self._xgb_model.predict_proba([features])[0][1])
            ltv_score = float(np.clip(acq_score * 1.1, 0, 1))
        else:
            acq_score, ltv_score = self._rule_based_score(signal, features)

        life_event = self._detect_life_event(signal)
        product_category = self.LIFE_EVENT_PRODUCTS.get(life_event, "savings_account") if life_event else "savings_account"
        channel = self._select_channel(signal, acq_score)
        tier = self._assign_tier(acq_score)

        reasoning = (
            f"Score={acq_score:.2f}. "
            f"{'Life event: ' + life_event + '. ' if life_event else ''}"
            f"Income tier: {'high' if signal.estimated_monthly_income > 80000 else 'medium'}. "
            f"Employment: {signal.employment_type}. "
            f"Location tier: {signal.location_tier}. "
            f"Recommended: {product_category} via {channel}."
        )

        return ScoredProspect(
            prospect_id=signal.prospect_id,
            acquisition_score=round(acq_score, 4),
            ltv_score=round(ltv_score, 4),
            priority_tier=tier,
            recommended_product_category=product_category,
            life_event_detected=life_event,
            outreach_channel=channel,
            reasoning=reasoning,
        )

    def score_batch(self, signals: list[ProspectSignal]) -> list[ScoredProspect]:
        """Score a batch of prospects and return sorted by acquisition score."""
        scored = [self.score_prospect(s) for s in signals]
        return sorted(scored, key=lambda p: p.acquisition_score, reverse=True)

    def get_high_priority_leads(
        self, signals: list[ProspectSignal], top_n: int = 100
    ) -> list[ScoredProspect]:
        """Return top-N high-priority leads for immediate outreach."""
        all_scored = self.score_batch(signals)
        high = [p for p in all_scored if p.priority_tier == "high"]
        return high[:top_n]
