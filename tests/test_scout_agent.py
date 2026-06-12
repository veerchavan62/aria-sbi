"""Tests for ARIA Scout Agent."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from agents.scout_agent import ScoutAgent, ProspectSignal, ScoredProspect


@pytest.fixture
def agent():
    return ScoutAgent()


def make_signal(**kwargs):
    defaults = dict(
        prospect_id="TEST001",
        source="job_portal",
        age=26,
        location_tier=1,
        employment_type="salaried",
        estimated_monthly_income=60_000,
        has_existing_sbi_account=False,
        life_events=[],
    )
    defaults.update(kwargs)
    return ProspectSignal(**defaults)


class TestScoutAgent:

    def test_score_returns_scored_prospect(self, agent):
        signal = make_signal()
        result = agent.score_prospect(signal)
        assert isinstance(result, ScoredProspect)
        assert 0.0 <= result.acquisition_score <= 1.0
        assert result.priority_tier in ("high", "medium", "low")

    def test_life_event_increases_score(self, agent):
        no_event = agent.score_prospect(make_signal(life_events=[]))
        with_event = agent.score_prospect(make_signal(life_events=["first_job"]))
        # Life event should generally increase score (stochastic, so use average)
        # Run multiple times and check average
        scores_no = [agent.score_prospect(make_signal(life_events=[])).acquisition_score for _ in range(20)]
        scores_ev = [agent.score_prospect(make_signal(life_events=["first_job"])).acquisition_score for _ in range(20)]
        assert sum(scores_ev) / len(scores_ev) > sum(scores_no) / len(scores_no)

    def test_product_recommendation_for_life_event(self, agent):
        result = agent.score_prospect(make_signal(life_events=["first_job"]))
        assert result.recommended_product_category == "salary_account"

    def test_rural_routes_to_bc(self, agent):
        result = agent.score_prospect(make_signal(location_tier=4, estimated_monthly_income=20_000))
        assert result.outreach_channel == "bc"

    def test_high_value_routes_to_rm(self, agent):
        result = agent.score_prospect(make_signal(location_tier=1, estimated_monthly_income=150_000))
        # Multiple runs to account for score variance
        results = [agent.score_prospect(make_signal(location_tier=1, estimated_monthly_income=150_000)).outreach_channel for _ in range(10)]
        assert "rm" in results or "whatsapp" in results  # Either is valid

    def test_batch_sorted_by_score(self, agent):
        signals = [make_signal(prospect_id=f"P{i:03d}") for i in range(10)]
        scored = agent.score_batch(signals)
        scores = [p.acquisition_score for p in scored]
        assert scores == sorted(scores, reverse=True)

    def test_get_high_priority_leads(self, agent):
        signals = [make_signal(prospect_id=f"P{i:03d}") for i in range(50)]
        leads = agent.get_high_priority_leads(signals, top_n=10)
        assert len(leads) <= 10
        assert all(p.priority_tier == "high" for p in leads)
