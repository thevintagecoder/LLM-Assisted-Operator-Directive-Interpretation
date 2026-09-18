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
    validate_schedule,
)


DIRECTIVE_ADAPTER = TypeAdapter(DirectiveInterpretation)


with open(
    "tests/data/public_cases.json",
    "r",
    encoding="utf-8",
) as file:
    sample_pack = json.load(file)


print()
print("SCHEDULE VALIDATOR TEST")
print("=" * 60)


for case in sample_pack["cases"]:

    request = OptimizeEnergyRequest.model_validate(
        case["input"]
    )

    directives = [
        DIRECTIVE_ADAPTER.validate_python(directive)
        for directive in case[
            "expected_output"
        ]["directive_interpretation"]
    ]

    result = optimize_energy_schedule(
        request=request,
        directives=directives,
    )

    validate_schedule(
        request=request,
        directives=directives,
        result=result,
    )

    print(
        f"{case['id']:12} PASS"
    )


print("=" * 60)
print("All schedules validated.")
