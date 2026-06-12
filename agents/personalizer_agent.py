"""
ARIA — Personalizer Agent
Generates hyper-personalized SBI product recommendations using
Claude 3.5 Sonnet + Pinecone RAG on the SBI product catalog.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# ─── Product catalog (loaded from config/product_catalog.json in production) ───
PRODUCT_CATALOG: list[dict] = [
    {
        "id": "salary_account",
        "name": "SBI Salary Account",
        "tagline": "Your first salary deserves the best home",
        "benefits": ["Zero balance", "Free debit card", "Instant YONO access", "Overdraft up to 2x salary"],
        "target": "salaried professionals, first jobbers",
        "cta": "Open in 10 minutes via YONO — no branch visit needed",
    },
    {
        "id": "home_loan",
        "name": "SBI Home Loan",
        "tagline": "India's most trusted home loan since 1955",
        "benefits": ["Lowest interest rates", "No prepayment penalty", "Tax benefits under 80C", "Balance transfer available"],
        "target": "working professionals, existing account holders",
        "cta": "Check your eligibility instantly — pre-approved offers available",
    },
    {
        "id": "education_loan",
        "name": "SBI Student Loan",
        "tagline": "Fund your future, not your worries",
        "benefits": ["Up to ₹1.5 Cr for abroad studies", "Moratorium period", "Collateral-free up to ₹7.5L", "Tax deduction on interest"],
        "target": "students, parents planning higher education",
        "cta": "Apply before your admission deadline — fast disbursement",
    },
    {
        "id": "savings_account",
        "name": "SBI Savings Account",
        "tagline": "Start your financial journey today",
        "benefits": ["Doorstep banking", "Free YONO app", "SBI Rewardz points", "Pan-India ATM access"],
        "target": "unbanked, rural customers, new-to-bank",
        "cta": "Open via Video KYC in minutes — no documents to courier",
    },
    {
        "id": "recurring_deposit",
        "name": "SBI Recurring Deposit",
        "tagline": "Small savings, big dreams",
        "benefits": ["Guaranteed returns", "Flexible tenure 1–10 years", "Loan against RD", "Auto-debit facility"],
        "target": "young families, new parents, salaried employees",
        "cta": "Start with as low as ₹100/month",
    },
    {
        "id": "auto_loan",
        "name": "SBI Car Loan",
        "tagline": "Drive your dream car today",
        "benefits": ["Up to 90% funding", "Flexible EMI", "Quick approval", "No hidden charges"],
        "target": "salaried, self-employed with vehicle purchase intent",
        "cta": "Get approval in 4 hours with your existing SBI account",
    },
]


@dataclass
class PersonalizationRequest:
    prospect_id: str
    product_category: str
    life_event: str | None
    prospect_profile: dict[str, Any]  # age, income, location, employment_type


@dataclass
class PersonalizedMessage:
    prospect_id: str
    product_id: str
    whatsapp_message: str          # ≤ 160 chars for WhatsApp
    yono_message: str              # Push notification copy
    bc_script: str                 # BC agent talking points
    subject_line: str              # For email fallback
    personalization_factors: list[str]


class PersonalizerAgent:
    """
    Personalizer Agent: RAG + LLM pipeline for product message generation.

    Uses Anthropic Claude 3.5 Sonnet to generate personalized outreach messages
    grounded in SBI's product catalog.
    """

    SYSTEM_PROMPT = """You are ARIA's Personalizer Agent for State Bank of India.
Your job is to generate hyper-personalized, compliant outreach messages for SBI customer acquisition.

Rules:
1. Messages must be warm, respectful, and in simple English (or translatable to Hindi)
2. Never make promises SBI cannot keep — only state real product benefits
3. WhatsApp message: max 160 characters, direct and compelling
4. YONO push: max 80 characters
5. BC script: 3–4 sentences the Business Correspondent can say verbally
6. Always include a clear, low-pressure call to action
7. Never be pushy or use high-pressure sales language
8. Respect the prospect's life moment — be empathetic, not transactional
9. Output ONLY valid JSON — no markdown, no preamble

Output format:
{
  "whatsapp_message": "...",
  "yono_message": "...",
  "bc_script": "...",
  "subject_line": "...",
  "personalization_factors": ["...", "..."]
}"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._product_index = {p["id"]: p for p in PRODUCT_CATALOG}

    def _get_product(self, product_id: str) -> dict:
        return self._product_index.get(product_id, PRODUCT_CATALOG[0])

    def _build_user_prompt(self, req: PersonalizationRequest, product: dict) -> str:
        profile = req.prospect_profile
        life_event_context = f"\nLife event detected: {req.life_event}" if req.life_event else ""

        return f"""Generate personalized SBI outreach messages for this prospect:

Prospect Profile:
- Age: {profile.get('age', 'unknown')}
- Employment: {profile.get('employment_type', 'unknown')}
- Monthly Income: ₹{profile.get('estimated_monthly_income', 0):,.0f}
- Location Tier: {profile.get('location_tier', 2)} (1=metro, 4=rural)
- Existing SBI customer: {profile.get('has_existing_sbi_account', False)}{life_event_context}

Recommended Product: {product['name']}
Product Tagline: {product['tagline']}
Key Benefits: {', '.join(product['benefits'][:3])}
Target Segment: {product['target']}
Suggested CTA: {product['cta']}

Generate messages that feel personal to this specific prospect's situation."""

    def generate(self, req: PersonalizationRequest) -> PersonalizedMessage:
        """Generate personalized messages for a single prospect."""
        product = self._get_product(req.product_category)
        user_prompt = self._build_user_prompt(req, product)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw = response.content[0].text.strip()
            # Strip any accidental markdown fences
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            return PersonalizedMessage(
                prospect_id=req.prospect_id,
                product_id=product["id"],
                whatsapp_message=data["whatsapp_message"],
                yono_message=data["yono_message"],
                bc_script=data["bc_script"],
                subject_line=data["subject_line"],
                personalization_factors=data.get("personalization_factors", []),
            )

        except Exception as e:
            logger.error(f"PersonalizerAgent error for {req.prospect_id}: {e}")
            # Graceful fallback to template message
            return PersonalizedMessage(
                prospect_id=req.prospect_id,
                product_id=product["id"],
                whatsapp_message=f"Hi! SBI has a special offer on {product['name']} for you. {product['cta']}",
                yono_message=f"New SBI offer for you: {product['name']}",
                bc_script=f"I'm reaching out on behalf of SBI about a {product['name']} that might suit you. {product['cta']}",
                subject_line=f"SBI: A personalized offer just for you — {product['name']}",
                personalization_factors=["fallback_template"],
            )

    def generate_batch(
        self, requests: list[PersonalizationRequest]
    ) -> list[PersonalizedMessage]:
        """Generate personalized messages for a batch of prospects."""
        return [self.generate(req) for req in requests]
