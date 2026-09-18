"""
Final deterministic validation for an optimized 24-hour energy schedule.

This validator replays the interpreted directives against the returned
hourly plan and confirms every GridWise hard constraint is satisfied.
"""

from app.models import (
    DirectiveInterpretation,
    OptimizeEnergyRequest,
)
from app.optimizer.energy_optimizer import (
    OptimizationResult,
)


HOURS = 24
EPSILON = 1e-6


class ScheduleValidationError(ValueError):
    """
    Raised when an optimized schedule violates a GridWise constraint.
    """


def _effective_solar(
    request: OptimizeEnergyRequest,
    directives: list[DirectiveInterpretation],
) -> list[float]:
    """
    Compute the usable solar profile after applying solar_reduction directives.
    """

    solar = [
        entry.solar_kwh
        for entry in sorted(request.hours, key=lambda h: h.hour)
    ]

    for directive in directives:
        if not directive.applies:
            continue

        if directive.directive_type == "solar_reduction":
            adjustment = directive.structured_adjustment
            for hour in adjustment.hours:
                solar[hour] *= adjustment.factor

    return solar


def _active_minimum_energy(
    request: OptimizeEnergyRequest,
    directives: list[DirectiveInterpretation],
) -> list[float]:
    """
    Compute the per-hour minimum battery energy after reserves are applied.
    """

    minimum = [
        request.battery.minimum_energy_kwh
        for _ in range(HOURS)
    ]

    for directive in directives:
        if not directive.applies:
            continue

        if directive.directive_type == "minimum_battery_reserve":
            adjustment = directive.structured_adjustment
            for hour in adjustment.hours:
                minimum[hour] = max(
                    minimum[hour],
                    adjustment.minimum_energy_kwh,
                )

    return minimum


def validate_schedule(
    request: OptimizeEnergyRequest,
    directives: list[DirectiveInterpretation],
    result: OptimizationResult,
) -> None:
    """
    Validate that the optimized schedule satisfies all GridWise constraints.

    Raises ScheduleValidationError if any rule is violated.
    """

    plan = result.hourly_plan

    # ---------------------------------------------------------
    # 1. Plan shape
    # ---------------------------------------------------------

    if len(plan) != HOURS:
        raise ScheduleValidationError(
            f"hourly_plan must contain {HOURS} entries, "
            f"got {len(plan)}."
        )

    hours = [entry.hour for entry in plan]

    if len(set(hours)) != HOURS or set(hours) != set(range(HOURS)):
        raise ScheduleValidationError(
            "hourly_plan must contain hours 0 through 23 exactly once."
        )

    # ---------------------------------------------------------
    # 2. Prepare reference data in hour order
    # ---------------------------------------------------------

    hour_map = {
        entry.hour: entry
        for entry in request.hours
    }

    effective_solar = _effective_solar(request, directives)
    active_minimum = _active_minimum_energy(request, directives)

    battery = request.battery

    recalc_total_grid = 0.0
    recalc_total_cost = 0.0
    recalc_peak_grid = 0.0

    # ---------------------------------------------------------
    # 3. Validate each hour
    # ---------------------------------------------------------

    for entry in plan:

        h = entry.hour
        demand = hour_map[h].demand_kwh
        tariff = hour_map[h].tariff_bdt_per_kwh

        grid = entry.grid_kwh
        solar = entry.solar_used_kwh
        action = entry.battery_action
        battery_kwh = entry.battery_kwh
        energy_after = entry.battery_energy_after_kwh

        # ---- grid and solar non-negative ----

        if grid < -EPSILON or solar < -EPSILON or battery_kwh < -EPSILON:
            raise ScheduleValidationError(
                f"Hour {h}: grid, solar_used, and battery_kwh "
                "must be non-negative."
            )

        # ---- battery action consistency ----

        if action == "idle" and battery_kwh > EPSILON:
            raise ScheduleValidationError(
                f"Hour {h}: battery_action is idle but battery_kwh is "
                f"{battery_kwh}."
            )

        charge = battery_kwh if action == "charge" else 0.0
        discharge = battery_kwh if action == "discharge" else 0.0

        # ---- energy balance ----
        # grid + solar + discharge = demand + charge

        lhs = grid + solar + discharge
        rhs = demand + charge

        if abs(lhs - rhs) > 0.01:
            raise ScheduleValidationError(
                f"Hour {h}: energy balance violated. "
                f"grid ({grid}) + solar ({solar}) + discharge "
                f"({discharge}) != demand ({demand}) + charge ({charge})."
            )

        # ---- solar cap ----

        if solar > effective_solar[h] + 0.01:
            raise ScheduleValidationError(
                f"Hour {h}: solar_used ({solar}) exceeds effective "
                f"solar ({effective_solar[h]})."
            )

        # ---- battery rate limits ----

        if action == "charge" and battery_kwh > (
            battery.max_charge_kwh_per_hour + 0.01
        ):
            raise ScheduleValidationError(
                f"Hour {h}: charge ({battery_kwh}) exceeds max charge rate "
                f"({battery.max_charge_kwh_per_hour})."
            )

        if action == "discharge" and battery_kwh > (
            battery.max_discharge_kwh_per_hour + 0.01
        ):
            raise ScheduleValidationError(
                f"Hour {h}: discharge ({battery_kwh}) exceeds max discharge "
                f"rate ({battery.max_discharge_kwh_per_hour})."
            )

        # ---- battery energy limits ----

        if energy_after < active_minimum[h] - 0.01:
            raise ScheduleValidationError(
                f"Hour {h}: battery energy ({energy_after}) is below "
                f"active minimum ({active_minimum[h]})."
            )

        if energy_after > battery.capacity_kwh + 0.01:
            raise ScheduleValidationError(
                f"Hour {h}: battery energy ({energy_after}) exceeds "
                f"capacity ({battery.capacity_kwh})."
            )

        # ---- no-charge / no-discharge window enforcement ----

        for directive in directives:
            if not directive.applies:
                continue

            if directive.directive_type == "no_charge_window":
                if h in directive.structured_adjustment.hours:
                    if action == "charge":
                        raise ScheduleValidationError(
                            f"Hour {h}: charging is forbidden by "
                            "no_charge_window directive."
                        )

            if directive.directive_type == "no_discharge_window":
                if h in directive.structured_adjustment.hours:
                    if action == "discharge":
                        raise ScheduleValidationError(
                            f"Hour {h}: discharging is forbidden by "
                            "no_discharge_window directive."
                        )

        # ---- accumulate totals ----

        recalc_total_grid += grid
        recalc_total_cost += grid * tariff
        recalc_peak_grid = max(recalc_peak_grid, grid)

    # ---------------------------------------------------------
    # 4. Battery state continuity
    # ---------------------------------------------------------

    for index, entry in enumerate(plan):
        if index == 0:
            expected_energy = battery.initial_energy_kwh
        else:
            expected_energy = plan[index - 1].battery_energy_after_kwh

        action = entry.battery_action
        battery_kwh = entry.battery_kwh

        charge = battery_kwh if action == "charge" else 0.0
        discharge = battery_kwh if action == "discharge" else 0.0

        expected_energy = expected_energy + charge - discharge

        if abs(entry.battery_energy_after_kwh - expected_energy) > 0.01:
            raise ScheduleValidationError(
                f"Hour {entry.hour}: battery energy transition invalid. "
                f"Expected {expected_energy}, got "
                f"{entry.battery_energy_after_kwh}."
            )

    # ---------------------------------------------------------
    # 5. End-of-day neutrality
    # ---------------------------------------------------------

    final_energy = plan[-1].battery_energy_after_kwh
    if abs(final_energy - battery.initial_energy_kwh) > 0.01:
        raise ScheduleValidationError(
            f"End-of-day neutrality violated: final energy ({final_energy}) "
            f"!= initial energy ({battery.initial_energy_kwh})."
        )

    # ---------------------------------------------------------
    # 6. Totals match
    # ---------------------------------------------------------

    if abs(result.total_grid_kwh - recalc_total_grid) > 0.01:
        raise ScheduleValidationError(
            f"total_grid_kwh mismatch: reported {result.total_grid_kwh}, "
            f"recalculated {recalc_total_grid}."
        )

    if abs(result.total_cost_bdt - recalc_total_cost) > 0.01:
        raise ScheduleValidationError(
            f"total_cost_bdt mismatch: reported {result.total_cost_bdt}, "
            f"recalculated {recalc_total_cost}."
        )

    if abs(result.peak_grid_kwh - recalc_peak_grid) > 0.01:
        raise ScheduleValidationError(
            f"peak_grid_kwh mismatch: reported {result.peak_grid_kwh}, "
            f"recalculated {recalc_peak_grid}."
        )
