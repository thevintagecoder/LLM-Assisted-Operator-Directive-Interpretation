import json

from pydantic import TypeAdapter

from app.models import (
    DirectiveInterpretation,
    OptimizeEnergyRequest,
)

from app.optimizer.energy_optimizer import (
    optimize_energy_schedule,
)


DIRECTIVE_ADAPTER = TypeAdapter(
    DirectiveInterpretation
)


with open(
    "tests/data/public_cases.json",
    "r",
    encoding="utf-8",
) as file:
    sample_pack = json.load(file)


print()
print("GRIDWISE OPTIMIZER TEST")
print("=" * 60)


passed = 0
failed = 0


for case in sample_pack["cases"]:

    case_id = case["id"]

    request = OptimizeEnergyRequest.model_validate(
        case["input"]
    )

    expected_directives = [
        DIRECTIVE_ADAPTER.validate_python(
            directive
        )
        for directive in case[
            "expected_output"
        ]["directive_interpretation"]
    ]

    result = optimize_energy_schedule(
        request=request,
        directives=expected_directives,
    )

    expected_cost = case[
        "expected_output"
    ]["total_cost_bdt"]

    difference = abs(
        result.total_cost_bdt
        - expected_cost
    )

    success = difference <= 0.01

    if success:
        passed += 1
        status = "PASS"
    else:
        failed += 1
        status = "FAIL"

    print(
        f"{case_id:12} "
        f"{status:5} "
        f"ours={result.total_cost_bdt:.2f} "
        f"expected={expected_cost:.2f}"
    )


print("=" * 60)

print(
    f"Passed: {passed}"
)

print(
    f"Failed: {failed}"
)