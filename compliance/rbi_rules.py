"""
ARIA — Compliance & Explainability Layer
Ensures every outreach is RBI-compliant, consent-gated, and fully auditable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum

logger = logging.getLogger(__name__)


class ComplianceStatus(str, Enum):
    CLEARED = "cleared"
    BLOCKED = "blocked"
    REQUIRES_CONSENT = "requires_consent"
    COOLING_OFF = "cooling_off"


@dataclass
class ComplianceDecision:
    prospect_id: str
    status: ComplianceStatus
    reason: str
    audit_hash: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    shap_factors: dict = field(default_factory=dict)


class RBIComplianceEngine:
    """
    Enforces RBI TRAI Do-Not-Disturb (DND) and outreach regulations.

    Key rules enforced:
    - DND registry check (mock — production integrates TRAI API)
    - No outreach 9PM–9AM
    - Maximum 3 outreach attempts per prospect per 30 days
    - Cooling-off period after rejection
    - Consent required for non-account-holders
    """

    # Allowed outreach hours: 9:00 AM – 9:00 PM IST
    ALLOWED_START = time(9, 0)
    ALLOWED_END = time(21, 0)

    # Max contact attempts per 30-day window
    MAX_ATTEMPTS = 3

    # Cooling-off period after rejection (days)
    COOLING_OFF_DAYS = 30

    def __init__(self):
        # In production: connect to DND registry API + Redis for attempt tracking
        self._dnd_registry: set[str] = set()       # mock DND list
        self._attempt_log: dict[str, list] = {}     # prospect_id → list of attempt timestamps
        self._consent_store: dict[str, bool] = {}   # prospect_id → consent granted
        self._rejection_log: dict[str, str] = {}    # prospect_id → rejection timestamp

    def register_dnd(self, prospect_id: str):
        """Add prospect to DND (Do Not Disturb) registry."""
        self._dnd_registry.add(prospect_id)

    def record_consent(self, prospect_id: str, granted: bool):
        """Record consent decision for a prospect."""
        self._consent_store[prospect_id] = granted
        logger.info(f"Consent {'granted' if granted else 'denied'} for {prospect_id}")

    def record_rejection(self, prospect_id: str):
        """Record that a prospect rejected outreach — triggers cooling-off."""
        self._rejection_log[prospect_id] = datetime.utcnow().isoformat()

    def _check_dnd(self, prospect_id: str) -> bool:
        return prospect_id not in self._dnd_registry

    def _check_time_window(self) -> bool:
        now = datetime.utcnow()
        # Convert UTC to IST (+5:30)
        ist_hour = (now.hour + 5) % 24
        ist_minute = (now.minute + 30) % 60
        ist_time = time(ist_hour, ist_minute)
        return self.ALLOWED_START <= ist_time <= self.ALLOWED_END

    def _check_attempt_limit(self, prospect_id: str) -> bool:
        attempts = self._attempt_log.get(prospect_id, [])
        # Count attempts in last 30 days
        cutoff = datetime.utcnow().timestamp() - (30 * 86400)
        recent = [a for a in attempts if a > cutoff]
        return len(recent) < self.MAX_ATTEMPTS

    def _check_cooling_off(self, prospect_id: str) -> bool:
        rejection_ts = self._rejection_log.get(prospect_id)
        if not rejection_ts:
            return True
        rejection_dt = datetime.fromisoformat(rejection_ts)
        days_since = (datetime.utcnow() - rejection_dt).days
        return days_since >= self.COOLING_OFF_DAYS

    def _check_consent(self, prospect_id: str, has_existing_account: bool) -> bool:
        """Existing customers have implied consent; others need explicit consent."""
        if has_existing_account:
            return True
        return self._consent_store.get(prospect_id, False)

    def _generate_audit_hash(self, prospect_id: str, decision: str) -> str:
        payload = f"{prospect_id}:{decision}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def evaluate(
        self,
        prospect_id: str,
        has_existing_account: bool = False,
        shap_scores: dict | None = None,
    ) -> ComplianceDecision:
        """
        Run full compliance check for a prospect.
        Returns ComplianceDecision with status and audit trail.
        """
        # 1. DND Check
        if not self._check_dnd(prospect_id):
            return ComplianceDecision(
                prospect_id=prospect_id,
                status=ComplianceStatus.BLOCKED,
                reason="Prospect is on DND registry (TRAI)",
                audit_hash=self._generate_audit_hash(prospect_id, "blocked_dnd"),
                shap_factors=shap_scores or {},
            )

        # 2. Time window check
        if not self._check_time_window():
            return ComplianceDecision(
                prospect_id=prospect_id,
                status=ComplianceStatus.BLOCKED,
                reason="Outside allowed outreach hours (9AM–9PM IST per RBI guidelines)",
                audit_hash=self._generate_audit_hash(prospect_id, "blocked_time"),
                shap_factors=shap_scores or {},
            )

        # 3. Attempt limit
        if not self._check_attempt_limit(prospect_id):
            return ComplianceDecision(
                prospect_id=prospect_id,
                status=ComplianceStatus.BLOCKED,
                reason=f"Attempt limit reached: max {self.MAX_ATTEMPTS} contacts per 30 days",
                audit_hash=self._generate_audit_hash(prospect_id, "blocked_attempts"),
                shap_factors=shap_scores or {},
            )

        # 4. Cooling-off check
        if not self._check_cooling_off(prospect_id):
            return ComplianceDecision(
                prospect_id=prospect_id,
                status=ComplianceStatus.COOLING_OFF,
                reason=f"In {self.COOLING_OFF_DAYS}-day cooling-off period after rejection",
                audit_hash=self._generate_audit_hash(prospect_id, "cooling_off"),
                shap_factors=shap_scores or {},
            )

        # 5. Consent check
        if not self._check_consent(prospect_id, has_existing_account):
            return ComplianceDecision(
                prospect_id=prospect_id,
                status=ComplianceStatus.REQUIRES_CONSENT,
                reason="Explicit consent required for non-account-holder outreach",
                audit_hash=self._generate_audit_hash(prospect_id, "requires_consent"),
                shap_factors=shap_scores or {},
            )

        # All checks passed — record this attempt
        if prospect_id not in self._attempt_log:
            self._attempt_log[prospect_id] = []
        self._attempt_log[prospect_id].append(datetime.utcnow().timestamp())

        return ComplianceDecision(
            prospect_id=prospect_id,
            status=ComplianceStatus.CLEARED,
            reason="All RBI compliance checks passed",
            audit_hash=self._generate_audit_hash(prospect_id, "cleared"),
            shap_factors=shap_scores or {},
        )

    def bulk_evaluate(
        self, prospects: list[dict]
    ) -> tuple[list[str], list[ComplianceDecision]]:
        """
        Evaluate a list of prospects.
        Returns (cleared_ids, all_decisions).
        """
        decisions = []
        cleared = []
        for p in prospects:
            decision = self.evaluate(
                prospect_id=p["prospect_id"],
                has_existing_account=p.get("has_existing_sbi_account", False),
                shap_scores=p.get("shap_scores"),
            )
            decisions.append(decision)
            if decision.status == ComplianceStatus.CLEARED:
                cleared.append(p["prospect_id"])
        return cleared, decisions
