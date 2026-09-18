from app.guardrails.directives import (
    validate_and_normalize_directives,
)

from app.llm.interpreter import (
    interpret_operator_notes,
)

from app.models import (
    BatteryInput,
    HourInput,
    OptimizeEnergyRequest,
)


battery = BatteryInput(
    capacity_kwh=200,
    initial_energy_kwh=100,
    minimum_energy_kwh=40,
    max_charge_kwh_per_hour=50,
    max_discharge_kwh_per_hour=50,
)


hours = [
    HourInput(
        hour=hour,
        demand_kwh=100,
        solar_kwh=0,
        tariff_bdt_per_kwh=10,
    )
    for hour in range(24)
]


request = OptimizeEnergyRequest(
    scenario_id="GUARDRAIL-TEST",
    operator_notes=[
        "Do not charge the battery between 2 PM and 4 PM."
    ],
    hours=hours,
    battery=battery,
)


raw_result = interpret_operator_notes(
    operator_notes=request.operator_notes,
    battery=request.battery,
)


print("RAW GEMINI OUTPUT:")
print(
    raw_result.model_dump_json(indent=2)
)


clean_result = validate_and_normalize_directives(
    raw_response=raw_result,
    request=request,
)


print("\nCLEAN GUARDED OUTPUT:")

for directive in clean_result:
    print(
        directive.model_dump_json(indent=2)
    )