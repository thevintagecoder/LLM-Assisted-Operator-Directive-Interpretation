import json
import time

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


with open(
    "tests/data/public_cases.json",
    "r",
    encoding="utf-8",
) as file:
    sample_pack = json.load(file)


print()
print("GRIDWISE FULL END-TO-END TEST")
print("=" * 75)


passed = 0
failed = 0
latencies = []


for case in sample_pack["cases"]:

    case_id = case["id"]
    request_body = case["input"]
    expected = case["expected_output"]

    start = time.perf_counter()

    response = client.post(
        "/optimize-energy",
        json=request_body,
    )

    elapsed = time.perf_counter() - start
    latencies.append(elapsed)

    if response.status_code != 200:

        print(
            f"{case_id:12} FAIL  "
            f"HTTP {response.status_code}  "
            f"{elapsed:.2f}s"
        )

        print(response.json())

        failed += 1
        continue

    result = response.json()

    expected_cost = expected["total_cost_bdt"]
    actual_cost = result["total_cost_bdt"]

    cost_ok = (
        abs(actual_cost - expected_cost) <= 0.01
    )

    hours_ok = (
        len(result["hourly_plan"]) == 24
    )

    directive_count_ok = (
        len(result["directive_interpretation"])
        ==
        len(expected["directive_interpretation"])
    )

    success = (
        cost_ok
        and hours_ok
        and directive_count_ok
    )

    if success:

        passed += 1

        print(
            f"{case_id:12} PASS  "
            f"cost={actual_cost:.2f}  "
            f"time={elapsed:.2f}s"
        )

    else:

        failed += 1

        print(
            f"{case_id:12} FAIL  "
            f"ours={actual_cost:.2f}  "
            f"expected={expected_cost:.2f}  "
            f"time={elapsed:.2f}s"
        )


print("=" * 75)
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if latencies:

    average = sum(latencies) / len(latencies)

    print(
        f"Average latency: {average:.2f}s"
    )

    print(
        f"Slowest request: {max(latencies):.2f}s"
    )