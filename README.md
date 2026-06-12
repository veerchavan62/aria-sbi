# ARIA — Agentic Relationship & Intelligence Acquisition
### SBI Hackathon 2025 · Agentic AI & Emerging Tech · Customer Acquisition

> **Don't wait for customers to come. Go to them.**

ARIA is a multi-agent AI system that enables SBI to proactively acquire high-intent customers by detecting life-event signals, generating personalized product recommendations, and orchestrating compliant outreach at scale.

---

## Problem

SBI has 52 Cr customers but loses urban millennials & Gen Z to HDFC/ICICI because:
- Customer acquisition is **reactive** (branch walk-in or app download)
- **Life-event windows** (first salary, marriage, home purchase) are missed
- 85,000 Business Correspondents are under-utilized for targeted outreach
- Cost-per-acquisition via branch: ~₹620 vs digital target of ₹180

## Solution: 3 Specialized AI Agents

```
[Data Sources] → Scout Agent → Personalizer Agent → Compliance Layer → Engagement Agent → [Feedback Loop]
```

| Agent | Role | Models Used |
|---|---|---|
| **Scout Agent** | Scores & segments high-intent prospects | XGBoost + LSTM |
| **Personalizer Agent** | Generates product recommendations via RAG | Claude 3.5 Sonnet + Pinecone |
| **Engagement Agent** | Routes outreach (WhatsApp / YONO / BC) | FastAPI + WhatsApp Business API |

All agents run under an **RBI-Compliant Compliance & Explainability Layer** (SHAP audit logs, consent gates).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ARIA SYSTEM ARCHITECTURE                  │
└──────────────────────────────────────────────────────────────┘

  [External Signals]            [SBI Internal Data]
  Job portals, public           CRM, YONO logs,
  life-event APIs               BC network data
         │                            │
         └────────────┬───────────────┘
                      ▼
           ┌─────────────────────┐
           │   Data Ingestion    │  Kafka + Airflow
           └────────┬────────────┘
                    │
                    ▼
           ┌─────────────────────┐
           │   SCOUT AGENT       │  XGBoost scoring + LSTM life-event
           └────────┬────────────┘
                    │ Scored Segment
                    ▼
           ┌─────────────────────┐
           │  PERSONALIZER AGENT │  LLM + Pinecone RAG on SBI catalog
           └────────┬────────────┘
                    │
                    ▼
           ┌─────────────────────────────────────────┐
           │          COMPLIANCE LAYER               │
           │  RBI rules · Consent gate · SHAP audit  │
           └────────────────────┬────────────────────┘
                                │
                                ▼
           ┌─────────────────────┐
           │  ENGAGEMENT AGENT   │  WhatsApp / YONO / BC routing
           └────────┬────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   [Converted]           [No Response]
   Video KYC →           Cool-off 30d →
   Account opened        Re-score loop
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | LangGraph, LangChain |
| LLM | Claude 3.5 Sonnet (Anthropic API) |
| ML Models | XGBoost (prospect scoring), LSTM (life-event prediction) |
| Vector Store | Pinecone (RAG on SBI product catalog) |
| Data Streaming | Apache Kafka, Apache Airflow |
| Backend | FastAPI (Python 3.11) |
| Messaging | WhatsApp Business API, YONO Deep Link SDK, FCM |
| Database | PostgreSQL, Redis |
| Compliance | SHAP, custom RBI rule engine |
| Infra | Docker, Kubernetes, AWS GovCloud / NIC Cloud |
| Monitoring | Prometheus, Grafana |

---

## Project Structure

```
aria-sbi/
├── agents/
│   ├── scout_agent.py          # Prospect scoring & segmentation
│   ├── personalizer_agent.py   # LLM + RAG product recommendation
│   ├── engagement_agent.py     # Channel selection & outreach
│   └── agent_graph.py          # LangGraph multi-agent orchestration
├── api/
│   ├── main.py                 # FastAPI app entry point
│   ├── routes/
│   │   ├── prospects.py        # Prospect management endpoints
│   │   ├── campaigns.py        # Campaign creation & tracking
│   │   └── analytics.py        # Dashboard metrics
│   └── schemas.py              # Pydantic models
├── compliance/
│   ├── rbi_rules.py            # RBI regulatory rule engine
│   ├── consent_manager.py      # Consent tracking & validation
│   └── explainability.py       # SHAP audit log generation
├── data_pipeline/
│   ├── kafka_consumer.py       # Real-time event ingestion
│   ├── airflow_dags/
│   │   ├── prospect_scoring_dag.py
│   │   └── feedback_loop_dag.py
│   └── feature_engineering.py  # Feature extraction for ML models
├── engagement/
│   ├── whatsapp_handler.py     # WhatsApp Business API integration
│   ├── yono_deeplink.py        # YONO app deep link generator
│   └── bc_router.py            # Business Correspondent routing
├── config/
│   ├── settings.py             # App configuration (env vars)
│   └── product_catalog.json    # SBI product catalog for RAG
├── tests/
│   ├── test_scout_agent.py
│   ├── test_personalizer.py
│   ├── test_compliance.py
│   └── test_engagement.py
├── scripts/
│   ├── seed_mock_data.py       # Generate mock prospect data
│   └── evaluate_agents.py      # Agent performance evaluation
├── docs/
│   ├── architecture.md
│   └── api_reference.md
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/veerchavan/aria-sbi.git
cd aria-sbi

# 2. Environment setup
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, PINECONE_API_KEY, DATABASE_URL, etc.

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start services
docker-compose up -d  # Starts Kafka, PostgreSQL, Redis

# 5. Seed mock data
python scripts/seed_mock_data.py

# 6. Run the API
uvicorn api.main:app --reload --port 8000

# 7. Test the Scout Agent
python -m pytest tests/test_scout_agent.py -v
```

---

## Key Metrics (Target)

| Metric | Baseline | ARIA Target |
|---|---|---|
| Cost per Acquisition | ~₹620 | ~₹180 |
| Time to Onboard | 3–5 days | < 24 hrs |
| Lead Conversion Rate | ~4% | 12–15% |
| Products per New Customer | 1.2 | 2.1 |

---

## Team

**Veer Chavan** — AI/ML Developer, 3rd Year CSE (AI/ML), Manipal University Jaipur

---

## License

MIT License — for hackathon purposes. Production deployment to require SBI approval and RBI compliance audit.
