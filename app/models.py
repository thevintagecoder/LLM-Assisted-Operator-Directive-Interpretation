from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )

class HourInput(StrictModel):
    hour: int = Field(ge=0, le=23)
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)

class BatteryInput(StrictModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_battery_levels(self):
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                "initial_energy_kwh cannot exceed capacity_kwh"
            )

        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError(
                "minimum_energy_kwh cannot exceed capacity_kwh"
            )

        return self


class OptimizeEnergyRequest(StrictModel):
    scenario_id: str = Field(min_length=1)

    operator_notes: list[str] = Field(
        min_length=1,
        max_length=3,
    )

    hours: list[HourInput] = Field(
        min_length=24,
        max_length=24,
    )

    battery: BatteryInput

    @field_validator("operator_notes")
    @classmethod
    def validate_operator_notes(cls, notes: list[str]):
        cleaned_notes = []

        for note in notes:
            cleaned = note.strip()

            if not cleaned:
                raise ValueError(
                    "operator notes cannot be empty"
                )

            cleaned_notes.append(cleaned)

        return cleaned_notes

    @model_validator(mode="after")
    def validate_hours(self):
        hour_numbers = [entry.hour for entry in self.hours]

        if len(set(hour_numbers)) != 24:
            raise ValueError(
                "hours must contain 24 unique hour values"
            )

        if set(hour_numbers) != set(range(24)):
            raise ValueError(
                "hours must contain every hour from 0 through 23"
            )

        return self

class SolarReductionAdjustment(StrictModel):
    hours: list[int]
    factor: float = Field(ge=0, le=1)


class MinimumBatteryReserveAdjustment(StrictModel):
    hours: list[int]
    minimum_energy_kwh: float = Field(ge=0)


class NoChargeAdjustment(StrictModel):
    hours: list[int]


class NoDischargeAdjustment(StrictModel):
    hours: list[int]


class MaxGridAdjustment(StrictModel):
    hours: list[int]
    max_grid_kwh: float = Field(ge=0)

class DirectiveBase(StrictModel):
    note_index: int = Field(ge=0)
    explanation: str = Field(min_length=1)


class SolarReductionDirective(DirectiveBase):
    applies: bool
    directive_type: Literal["solar_reduction"]
    structured_adjustment: SolarReductionAdjustment


class MinimumBatteryReserveDirective(DirectiveBase):
    applies: bool
    directive_type: Literal["minimum_battery_reserve"]
    structured_adjustment: MinimumBatteryReserveAdjustment


class NoChargeDirective(DirectiveBase):
    applies: bool
    directive_type: Literal["no_charge_window"]
    structured_adjustment: NoChargeAdjustment


class NoDischargeDirective(DirectiveBase):
    applies: bool
    directive_type: Literal["no_discharge_window"]
    structured_adjustment: NoDischargeAdjustment


class MaxGridDirective(DirectiveBase):
    applies: bool
    directive_type: Literal["max_grid_window"]
    structured_adjustment: MaxGridAdjustment


class NoOpDirective(DirectiveBase):
    applies: bool
    directive_type: Literal["no_op"]
    structured_adjustment: None

DirectiveInterpretation = Annotated[
    Union[
        SolarReductionDirective,
        MinimumBatteryReserveDirective,
        NoChargeDirective,
        NoDischargeDirective,
        MaxGridDirective,
        NoOpDirective,
    ],
    Field(discriminator="directive_type"),
]

class HourlyPlanEntry(StrictModel):
    hour: int = Field(ge=0, le=23)
    grid_kwh: float = Field(ge=0)
    solar_used_kwh: float = Field(ge=0)

    battery_action: Literal[
        "charge",
        "discharge",
        "idle",
    ]

    battery_kwh: float = Field(ge=0)
    battery_energy_after_kwh: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_idle_action(self):
        if self.battery_action == "idle" and self.battery_kwh != 0:
            raise ValueError(
                "battery_kwh must be 0 when battery_action is idle"
            )

        return self

class OptimizeEnergyResponse(StrictModel):
    scenario_id: str

    directive_interpretation: list[
        DirectiveInterpretation
    ]

    hourly_plan: list[HourlyPlanEntry] = Field(
        min_length=24,
        max_length=24,
    )

    total_grid_kwh: float = Field(ge=0)
    total_cost_bdt: float = Field(ge=0)
    peak_grid_kwh: float = Field(ge=0)

    plan_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_hourly_plan_hours(self):
        hours = [entry.hour for entry in self.hourly_plan]

        if len(set(hours)) != 24:
            raise ValueError(
                "hourly_plan must contain 24 unique hours"
            )

        if set(hours) != set(range(24)):
            raise ValueError(
                "hourly_plan must contain hours 0 through 23"
            )

        return self

# =========================================================
# GEMINI RAW OUTPUT MODELS
# =========================================================

class GeminiStructuredAdjustment(BaseModel):
    hours: list[int]
    factor: float | None = None
    minimum_energy_kwh: float | None = None
    max_grid_kwh: float | None = None


class GeminiDirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool

    directive_type: Literal[
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
        "no_op",
    ]

    structured_adjustment: GeminiStructuredAdjustment | None = None
    explanation: str


class LLMInterpretationResponse(BaseModel):
    directive_interpretation: list[
        GeminiDirectiveInterpretation
    ] = Field(
        min_length=1,
        max_length=3,
    )