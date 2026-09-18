import math

from app.models import (
    LLMInterpretationResponse,
    OptimizeEnergyRequest,
    DirectiveInterpretation,
    SolarReductionDirective,
    SolarReductionAdjustment,
    MinimumBatteryReserveDirective,
    MinimumBatteryReserveAdjustment,
    NoChargeDirective,
    NoChargeAdjustment,
    NoDischargeDirective,
    NoDischargeAdjustment,
    MaxGridDirective,
    MaxGridAdjustment,
    NoOpDirective,
)


class DirectiveValidationError(ValueError):
    """
    Raised when Gemini produces an interpretation that violates
    the deterministic GridWise directive rules.
    """


def _validate_hours(hours: list[int]) -> list[int]:
    """
    Validate the official GridWise hours-array rules.

    Hours must:
    - be integers
    - be between 0 and 23
    - contain no duplicates
    - already be in ascending order
    """

    if not hours:
        raise DirectiveValidationError(
            "Directive hours cannot be empty."
        )

    if any(
        isinstance(hour, bool) or not isinstance(hour, int)
        for hour in hours
    ):
        raise DirectiveValidationError(
            "Every directive hour must be an integer."
        )

    if any(hour < 0 or hour > 23 for hour in hours):
        raise DirectiveValidationError(
            "Directive hours must be between 0 and 23."
        )

    if len(hours) != len(set(hours)):
        raise DirectiveValidationError(
            "Directive hours must not contain duplicates."
        )

    if hours != sorted(hours):
        raise DirectiveValidationError(
            "Directive hours must be in ascending order."
        )

    return hours


def _require_adjustment(raw_directive):
    adjustment = raw_directive.structured_adjustment

    if adjustment is None:
        raise DirectiveValidationError(
            f"{raw_directive.directive_type} requires "
            "structured_adjustment."
        )

    return adjustment


def validate_and_normalize_directives(
    raw_response: LLMInterpretationResponse,
    request: OptimizeEnergyRequest,
) -> list[DirectiveInterpretation]:
    """
    Validate Gemini's raw interpretation and convert it into
    exact GridWise directive objects.

    Nothing returned from this function should be considered
    trusted until all checks below have passed.
    """

    raw_directives = raw_response.directive_interpretation

    expected_count = len(request.operator_notes)

    # ---------------------------------------------------------
    # 1. Exactly one interpretation per operator note
    # ---------------------------------------------------------

    if len(raw_directives) != expected_count:
        raise DirectiveValidationError(
            "Gemini must return exactly one interpretation "
            "for every operator note."
        )

    note_indexes = [
        directive.note_index
        for directive in raw_directives
    ]

    expected_indexes = list(range(expected_count))

    if note_indexes != expected_indexes:
        raise DirectiveValidationError(
            "Directive note_index values must exactly match "
            f"{expected_indexes} in order."
        )

    clean_directives: list[DirectiveInterpretation] = []

    # ---------------------------------------------------------
    # 2. Validate each directive
    # ---------------------------------------------------------

    for raw in raw_directives:

        directive_type = raw.directive_type

        # =====================================================
        # NO-OP
        # =====================================================

        if directive_type == "no_op":

            if raw.applies is not False:
                raise DirectiveValidationError(
                    "no_op must use applies=false."
                )

            if raw.structured_adjustment is not None:
                raise DirectiveValidationError(
                    "no_op must use structured_adjustment=null."
                )

            clean_directives.append(
                NoOpDirective(
                    note_index=raw.note_index,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation=raw.explanation,
                )
            )

            continue

        # -----------------------------------------------------
        # Every real directive must apply
        # -----------------------------------------------------

        if raw.applies is not True:
            raise DirectiveValidationError(
                f"{directive_type} must use applies=true."
            )

        adjustment = _require_adjustment(raw)

        hours = _validate_hours(adjustment.hours)

        # =====================================================
        # SOLAR REDUCTION
        # =====================================================

        if directive_type == "solar_reduction":

            factor = adjustment.factor

            if factor is None:
                raise DirectiveValidationError(
                    "solar_reduction requires factor."
                )

            if not math.isfinite(factor):
                raise DirectiveValidationError(
                    "Solar factor must be finite."
                )

            if factor < 0 or factor > 1:
                raise DirectiveValidationError(
                    "Solar factor must be between 0 and 1."
                )

            clean_directives.append(
                SolarReductionDirective(
                    note_index=raw.note_index,
                    applies=True,
                    directive_type="solar_reduction",
                    structured_adjustment=(
                        SolarReductionAdjustment(
                            hours=hours,
                            factor=factor,
                        )
                    ),
                    explanation=raw.explanation,
                )
            )

        # =====================================================
        # MINIMUM BATTERY RESERVE
        # =====================================================

        elif directive_type == "minimum_battery_reserve":

            minimum_energy = adjustment.minimum_energy_kwh

            if minimum_energy is None:
                raise DirectiveValidationError(
                    "minimum_battery_reserve requires "
                    "minimum_energy_kwh."
                )

            if not math.isfinite(minimum_energy):
                raise DirectiveValidationError(
                    "Minimum battery reserve must be finite."
                )

            if minimum_energy < 0:
                raise DirectiveValidationError(
                    "Minimum battery reserve cannot be negative."
                )

            if minimum_energy > request.battery.capacity_kwh:
                raise DirectiveValidationError(
                    "Minimum battery reserve cannot exceed "
                    "battery capacity."
                )

            clean_directives.append(
                MinimumBatteryReserveDirective(
                    note_index=raw.note_index,
                    applies=True,
                    directive_type="minimum_battery_reserve",
                    structured_adjustment=(
                        MinimumBatteryReserveAdjustment(
                            hours=hours,
                            minimum_energy_kwh=minimum_energy,
                        )
                    ),
                    explanation=raw.explanation,
                )
            )

        # =====================================================
        # NO CHARGE WINDOW
        # =====================================================

        elif directive_type == "no_charge_window":

            clean_directives.append(
                NoChargeDirective(
                    note_index=raw.note_index,
                    applies=True,
                    directive_type="no_charge_window",
                    structured_adjustment=(
                        NoChargeAdjustment(
                            hours=hours,
                        )
                    ),
                    explanation=raw.explanation,
                )
            )

        # =====================================================
        # NO DISCHARGE WINDOW
        # =====================================================

        elif directive_type == "no_discharge_window":

            clean_directives.append(
                NoDischargeDirective(
                    note_index=raw.note_index,
                    applies=True,
                    directive_type="no_discharge_window",
                    structured_adjustment=(
                        NoDischargeAdjustment(
                            hours=hours,
                        )
                    ),
                    explanation=raw.explanation,
                )
            )

        # =====================================================
        # MAX GRID WINDOW
        # =====================================================

        elif directive_type == "max_grid_window":

            max_grid = adjustment.max_grid_kwh

            if max_grid is None:
                raise DirectiveValidationError(
                    "max_grid_window requires max_grid_kwh."
                )

            if not math.isfinite(max_grid):
                raise DirectiveValidationError(
                    "max_grid_kwh must be finite."
                )

            if max_grid < 0:
                raise DirectiveValidationError(
                    "max_grid_kwh cannot be negative."
                )

            clean_directives.append(
                MaxGridDirective(
                    note_index=raw.note_index,
                    applies=True,
                    directive_type="max_grid_window",
                    structured_adjustment=(
                        MaxGridAdjustment(
                            hours=hours,
                            max_grid_kwh=max_grid,
                        )
                    ),
                    explanation=raw.explanation,
                )
            )

        # =====================================================
        # UNKNOWN TYPE
        # =====================================================

        else:
            raise DirectiveValidationError(
                f"Unsupported directive type: {directive_type}"
            )

    return clean_directives