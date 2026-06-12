"""
ARIA — Mock Data Seeder
Generates realistic prospect signals for demo and testing.
Run: python scripts/seed_mock_data.py
"""

import json
import random
import uuid

random.seed(42)

LIFE_EVENTS = [
    "first_job", "marriage", "home_purchase",
    "vehicle_purchase", "child_birth", "education", None, None, None
]
EMPLOYMENT_TYPES = ["salaried", "self_employed", "gig", "student"]
SOURCES = ["job_portal", "bc_network", "yono_partial", "pmjdy"]

def generate_prospect():
    age = random.randint(21, 55)
    emp = random.choice(EMPLOYMENT_TYPES)
    income_map = {
        "salaried": random.uniform(25_000, 200_000),
        "self_employed": random.uniform(30_000, 500_000),
        "gig": random.uniform(15_000, 80_000),
        "student": random.uniform(5_000, 20_000),
    }
    events = random.sample([e for e in LIFE_EVENTS if e], k=random.randint(0, 2))
    return {
        "prospect_id": f"P{uuid.uuid4().hex[:8].upper()}",
        "source": random.choice(SOURCES),
        "age": age,
        "location_tier": random.choices([1, 2, 3, 4], weights=[20, 30, 30, 20])[0],
        "employment_type": emp,
        "estimated_monthly_income": round(income_map[emp], 2),
        "has_existing_sbi_account": random.random() < 0.3,
        "life_events": events,
        "existing_products": random.sample(
            ["savings_account", "fd", "loan", "credit_card"],
            k=random.randint(0, 2)
        ),
    }

if __name__ == "__main__":
    prospects = [generate_prospect() for _ in range(500)]
    with open("mock_prospects.json", "w") as f:
        json.dump(prospects, f, indent=2)
    print(f"Generated {len(prospects)} mock prospects → mock_prospects.json")
    print("\nSample prospect:")
    print(json.dumps(prospects[0], indent=2))
