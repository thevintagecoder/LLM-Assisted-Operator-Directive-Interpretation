import json

from pydantic import TypeAdapter

from app.models import (
    DirectiveInterpretation,
    OptimizeEnergyRequest,
)

from app.optimizer.energy_optimizer import (
    optimize_energy_schedule,
)

from app.validators.schedule_validator import (
    ScheduleValidationError,
    validate_schedule,
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
print("GRIDWISE FINAL VALIDATOR TEST")
print("=" * 60)


passed = 0
failed = 0


for case in sample_pack["cases"]:

    case_id = case["id"]

    request = OptimizeEnergyRequest.model_validate(
        case["input"]
    )

    directives = [
        DIRECTIVE_ADAPTER.validate_python(
            directive
        )
        for directive in case[
            "expected_output"
        ]["directive_interpretation"]
    ]

    result = optimize_energy_schedule(
        request=request,
        directives=directives,
    )

    try:

        validate_schedule(
            request=request,
            directives=directives,
            result=result,
        )

        print(
            f"{case_id:12} PASS"
        )

        passed += 1

    except ScheduleValidationError as exc:

        print(
            f"{case_id:12} FAIL  {exc}"
        )

        failed += 1


print("=" * 60)
print(f"Passed: {passed}")
print(f"Failed: {failed}")

print()
print("DELIBERATE INVALID-SCHEDULE TEST")
print("=" * 60)


first_case = sample_pack["cases"][0]

request = OptimizeEnergyRequest.model_validate(
    first_case["input"]
)

directives = [
    DIRECTIVE_ADAPTER.validate_python(
        directive
    )
    for directive in first_case[
        "expected_output"
    ]["directive_interpretation"]
]

result = optimize_energy_schedule(
    request=request,
    directives=directives,
)


# Deliberately corrupt hour 0.
result.hourly_plan[0].grid_kwh += 10


try:

    validate_schedule(
        request=request,
        directives=directives,
        result=result,
    )

    print(
        "FAIL: Validator accepted a corrupted schedule."
    )

except ScheduleValidationError as exc:

    print(
        "PASS: Validator rejected corrupted schedule."
    )

    print(
        f"Reason: {exc}"
    )