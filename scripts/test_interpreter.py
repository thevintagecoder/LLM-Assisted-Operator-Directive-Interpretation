from app.llm.interpreter import interpret_operator_notes
from app.models import BatteryInput


battery = BatteryInput(
    capacity_kwh=200,
    initial_energy_kwh=100,
    minimum_energy_kwh=40,
    max_charge_kwh_per_hour=50,
    max_discharge_kwh_per_hour=50,
)


notes = [
    "Do not charge the battery between 2 PM and 4 PM."
]


result = interpret_operator_notes(
    operator_notes=notes,
    battery=battery,
)


print(
    result.model_dump_json(indent=2)
)