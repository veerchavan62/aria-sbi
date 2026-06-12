"""
ARIA — FastAPI Application Entry Point
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any
import uuid
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(
    title="ARIA — Agentic Relationship & Intelligence Acquisition",
    description="SBI's autonomous customer acquisition agent system",
    version="1.0.0",
)


class ProspectSignalPayload(BaseModel):
    prospect_id: str
    source: str = "job_portal"
    age: int = 25
    location_tier: int = 2
    employment_type: str = "salaried"
    estimated_monthly_income: float = 50000.0
    has_existing_sbi_account: bool = False
    life_events: list[str] = []
    existing_products: list[str] = []


class BatchRunRequest(BaseModel):
    signals: list[ProspectSignalPayload]
    run_id: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "service": "ARIA"}


@app.post("/api/v1/pipeline/run")
def run_pipeline(req: BatchRunRequest) -> dict[str, Any]:
    """Run the full ARIA pipeline for a batch of prospect signals."""
    from agents.agent_graph import ARIAPipeline

    run_id = req.run_id or f"run_{uuid.uuid4().hex[:8]}"
    pipeline = ARIAPipeline()
    signals = [s.model_dump() for s in req.signals]
    state = pipeline.run(signals, run_id=run_id)
    return pipeline.get_summary(state)


@app.post("/api/v1/scout/score")
def score_single(signal: ProspectSignalPayload) -> dict[str, Any]:
    """Score a single prospect signal."""
    from agents.scout_agent import ScoutAgent, ProspectSignal

    agent = ScoutAgent()
    result = agent.score_prospect(ProspectSignal(**signal.model_dump()))
    return vars(result)


@app.get("/api/v1/compliance/status/{prospect_id}")
def compliance_status(prospect_id: str) -> dict[str, Any]:
    """Check compliance status for a prospect."""
    from compliance.rbi_rules import RBIComplianceEngine

    engine = RBIComplianceEngine()
    decision = engine.evaluate(prospect_id)
    return vars(decision)
