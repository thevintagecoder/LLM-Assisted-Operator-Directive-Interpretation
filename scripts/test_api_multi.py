"""
Run a few public cases through the full wired endpoint.
"""

import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


with open(
    "tests/data/public_cases.json",
    "r",
    encoding="utf-8",
) as file:
    sample_pack = json.load(file)


# Test a representative subset.
case_ids = [
    "SAMPLE-01",
    "SAMPLE-02",
    "SAMPLE-03",
    "SAMPLE-04",
    "SAMPLE-05",
]


case_map = {
    case["id"]: case
    for case in sample_pack["cases"]
}


print()
print("MULTI-CASE API ENDPOINT TEST")
print("=" * 70)


for case_id in case_ids:

    case = case_map[case_id]

    print()
    print(f"Case: {case_id} - {case['label']}")

    response = client.post(
        "/optimize-energy",
        json=case["input"],
    )

    print(f"  Status: {response.status_code}")

    if response.status_code != 200:
        print(f"  Error: {response.text[:200]}")
        continue

    data = response.json()

    print("  Directives:")
    for d in data["directive_interpretation"]:
        print(
            f"    note_index={d['note_index']} "
            f"applies={d['applies']} "
            f"type={d['directive_type']}"
        )

    print(
        f"  cost={data['total_cost_bdt']} "
        f"(expected ~{case['expected_output']['total_cost_bdt']}) "
        f"peak={data['peak_grid_kwh']}"
    )


print()
print("=" * 70)
