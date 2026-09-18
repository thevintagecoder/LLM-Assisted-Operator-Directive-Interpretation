import json
import time

import requests


BASE_URL = "https://llm-assisted-operator-directive.onrender.com"


with open(
    "tests/data/public_cases.json",
    "r",
    encoding="utf-8",
) as file:
    sample_pack = json.load(file)


print()
print("GRIDWISE RENDER PRODUCTION TEST")
print("=" * 80)


# ---------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------

health_response = requests.get(
    f"{BASE_URL}/health",
    timeout=10,
)

print(
    f"Health check: HTTP {health_response.status_code}"
)

if health_response.status_code != 200:
    print("FAIL: Render deployment is not healthy.")
    raise SystemExit(1)

print("PASS: Render deployment is healthy.")
print()


# ---------------------------------------------------------
# 2. Run all 10 public cases
# ---------------------------------------------------------

passed = 0
failed = 0
latencies = []


for case in sample_pack["cases"]:

    case_id = case["id"]
    request_body = case["input"]
    expected_output = case["expected_output"]

    start = time.perf_counter()

    try:
        response = requests.post(
            f"{BASE_URL}/optimize-energy",
            json=request_body,
            timeout=30,
        )

    except requests.Timeout:
        print(
            f"{case_id:12} FAIL  TIMEOUT (>30s)"
        )

        failed += 1
        continue

    elapsed = time.perf_counter() - start
    latencies.append(elapsed)

    if response.status_code != 200:

        print(
            f"{case_id:12} FAIL  "
            f"HTTP {response.status_code}  "
            f"time={elapsed:.2f}s"
        )

        try:
            print(response.json())
        except Exception:
            print(response.text)

        failed += 1
        continue

    result = response.json()

    expected_cost = expected_output[
        "total_cost_bdt"
    ]

    actual_cost = result[
        "total_cost_bdt"
    ]

    cost_ok = (
        abs(
            actual_cost
            - expected_cost
        )
        <= 0.01
    )

    hours_ok = (
        len(
            result["hourly_plan"]
        )
        == 24
    )

    directive_count_ok = (
        len(
            result[
                "directive_interpretation"
            ]
        )
        ==
        len(
            expected_output[
                "directive_interpretation"
            ]
        )
    )

    scenario_ok = (
        result["scenario_id"]
        ==
        request_body["scenario_id"]
    )

    success = (
        cost_ok
        and hours_ok
        and directive_count_ok
        and scenario_ok
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


print("=" * 80)

print(f"Passed: {passed}")
print(f"Failed: {failed}")


if latencies:

    sorted_latencies = sorted(latencies)

    average = (
        sum(latencies)
        / len(latencies)
    )

    slowest = max(latencies)

    p95_index = max(
        0,
        int(
            0.95
            * len(
                sorted_latencies
            )
        )
        - 1,
    )

    p95 = sorted_latencies[
        p95_index
    ]

    print(
        f"Average latency: "
        f"{average:.2f}s"
    )

    print(
        f"P95 latency: "
        f"{p95:.2f}s"
    )

    print(
        f"Slowest request: "
        f"{slowest:.2f}s"
    )