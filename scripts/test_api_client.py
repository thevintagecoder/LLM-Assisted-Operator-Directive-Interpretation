"""
Integration test using FastAPI TestClient.

This hits the real endpoint code including the LLM interpreter,
deterministic guardrails, optimizer, and final validator.
"""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.models import OptimizeEnergyRequest


client = TestClient(app)


with open(
    "tests/data/public_cases.json",
    "r",
    encoding="utf-8",
) as file:
    sample_pack = json.load(file)


case = sample_pack["cases"][0]


print()
print("API ENDPOINT INTEGRATION TEST")
print("=" * 60)
print(f"Case: {case['id']} - {case['label']}")
print()


response = client.post(
    "/optimize-energy",
    json=case["input"],
)


print(f"Status: {response.status_code}")
print()

if response.status_code == 200:
    data = response.json()
    print("Directive interpretation:")
    for d in data["directive_interpretation"]:
        print(f"  note_index={d['note_index']} "
              f"applies={d['applies']} "
              f"type={d['directive_type']}")
    print()
    print(f"total_grid_kwh: {data['total_grid_kwh']}")
    print(f"total_cost_bdt: {data['total_cost_bdt']}")
    print(f"peak_grid_kwh:  {data['peak_grid_kwh']}")
    print()
    print(f"plan_summary: {data['plan_summary']}")
else:
    print(response.text)
