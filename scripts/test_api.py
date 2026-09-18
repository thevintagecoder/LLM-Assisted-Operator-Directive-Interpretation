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


case = sample_pack["cases"][0]

request_body = case["input"]
expected_output = case["expected_output"]


print()
print("GRIDWISE END-TO-END API TEST")
print("=" * 60)

print(f"Scenario: {request_body['scenario_id']}")

print()
print("Sending request through full pipeline...")
print()


response = client.post(
    "/optimize-energy",
    json=request_body,
)


print(f"HTTP status: {response.status_code}")


if response.status_code != 200:
    print()
    print("API ERROR:")
    print(
        json.dumps(
            response.json(),
            indent=2,
        )
    )

    raise SystemExit(1)


result = response.json()


print()
print("DIRECTIVE INTERPRETATION:")
print(
    json.dumps(
        result["directive_interpretation"],
        indent=2,
    )
)


print()
print("OPTIMIZATION RESULTS:")

print(
    f"Total grid: "
    f"{result['total_grid_kwh']:.2f} kWh"
)

print(
    f"Total cost: "
    f"{result['total_cost_bdt']:.2f} BDT"
)

print(
    f"Peak grid: "
    f"{result['peak_grid_kwh']:.2f} kWh"
)


print()
print("EXPECTED COST:")

print(
    f"{expected_output['total_cost_bdt']:.2f} BDT"
)


cost_difference = abs(
    result["total_cost_bdt"]
    - expected_output["total_cost_bdt"]
)


if cost_difference <= 0.01:
    print()
    print("PASS: End-to-end cost matches reference.")
else:
    print()
    print("FAIL: End-to-end cost does not match reference.")


print()
print(
    f"Hourly plan entries: "
    f"{len(result['hourly_plan'])}"
)


if len(result["hourly_plan"]) == 24:
    print("PASS: Response contains exactly 24 hours.")
else:
    print("FAIL: Response does not contain exactly 24 hours.")


print()
print("PLAN SUMMARY:")
print(result["plan_summary"])

print("=" * 60)