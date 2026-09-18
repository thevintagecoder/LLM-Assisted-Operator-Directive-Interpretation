from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from app.models import (
    DirectiveInterpretation,
    HourlyPlanEntry,
    OptimizeEnergyRequest,
)


HOURS = 24
EPSILON = 1e-7


class OptimizationError(RuntimeError):
    """
    Raised when the energy optimization problem cannot be solved.
    """


@dataclass
class OptimizationResult:
    hourly_plan: list[HourlyPlanEntry]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str


def _clean_number(value: float) -> float:
    """
    Remove tiny floating-point noise such as -0.00000000001.
    """

    if abs(value) < EPSILON:
        return 0.0

    return float(value)


def optimize_energy_schedule(
    request: OptimizeEnergyRequest,
    directives: list[DirectiveInterpretation],
) -> OptimizationResult:
    """
    Produce the minimum-cost valid 24-hour energy schedule.

    Battery flow convention:

        positive battery_flow = charging
        negative battery_flow = discharging

    This lets us represent charge/discharge with one variable,
    making simultaneous charging and discharging impossible.
    """

    # ---------------------------------------------------------
    # 1. Put hourly input into guaranteed 0..23 order
    # ---------------------------------------------------------

    hour_map = {
        entry.hour: entry
        for entry in request.hours
    }

    demand = np.array(
        [
            hour_map[h].demand_kwh
            for h in range(HOURS)
        ],
        dtype=float,
    )

    original_solar = np.array(
        [
            hour_map[h].solar_kwh
            for h in range(HOURS)
        ],
        dtype=float,
    )

    tariff = np.array(
        [
            hour_map[h].tariff_bdt_per_kwh
            for h in range(HOURS)
        ],
        dtype=float,
    )

    battery = request.battery

    # ---------------------------------------------------------
    # 2. Start with normal GridWise limits
    # ---------------------------------------------------------

    effective_solar = original_solar.copy()

    minimum_energy = np.full(
        HOURS,
        battery.minimum_energy_kwh,
        dtype=float,
    )

    # Positive = charging
    # Negative = discharging
    battery_flow_lower = np.full(
        HOURS,
        -battery.max_discharge_kwh_per_hour,
        dtype=float,
    )

    battery_flow_upper = np.full(
        HOURS,
        battery.max_charge_kwh_per_hour,
        dtype=float,
    )

    # None means there is normally no explicit grid cap.
    grid_upper: list[float | None] = [
        None
        for _ in range(HOURS)
    ]

    # ---------------------------------------------------------
    # 3. Apply all guarded operator directives
    # ---------------------------------------------------------

    for directive in directives:

        if not directive.applies:
            continue

        directive_type = directive.directive_type
        adjustment = directive.structured_adjustment

        # -----------------------------------------------------
        # Solar reduction
        # -----------------------------------------------------

        if directive_type == "solar_reduction":

            for hour in adjustment.hours:
                effective_solar[hour] *= adjustment.factor

        # -----------------------------------------------------
        # Minimum battery reserve
        # -----------------------------------------------------

        elif directive_type == "minimum_battery_reserve":

            for hour in adjustment.hours:
                minimum_energy[hour] = max(
                    minimum_energy[hour],
                    adjustment.minimum_energy_kwh,
                )

        # -----------------------------------------------------
        # No charging
        # -----------------------------------------------------

        elif directive_type == "no_charge_window":

            for hour in adjustment.hours:
                battery_flow_upper[hour] = min(
                    battery_flow_upper[hour],
                    0.0,
                )

        # -----------------------------------------------------
        # No discharging
        # -----------------------------------------------------

        elif directive_type == "no_discharge_window":

            for hour in adjustment.hours:
                battery_flow_lower[hour] = max(
                    battery_flow_lower[hour],
                    0.0,
                )

        # -----------------------------------------------------
        # Maximum grid import
        # -----------------------------------------------------

        elif directive_type == "max_grid_window":

            for hour in adjustment.hours:

                new_cap = adjustment.max_grid_kwh

                if grid_upper[hour] is None:
                    grid_upper[hour] = new_cap
                else:
                    grid_upper[hour] = min(
                        grid_upper[hour],
                        new_cap,
                    )

    # ---------------------------------------------------------
    # 4. Define optimization variables
    # ---------------------------------------------------------
    #
    # There are 96 variables:
    #
    # 0  - 23 : grid energy
    # 24 - 47 : solar used
    # 48 - 71 : battery flow
    # 72 - 95 : battery energy after each hour
    #
    # ---------------------------------------------------------

    GRID_START = 0
    SOLAR_START = 24
    FLOW_START = 48
    ENERGY_START = 72

    VARIABLE_COUNT = 96

    # ---------------------------------------------------------
    # 5. Objective function
    # ---------------------------------------------------------
    #
    # Minimize:
    #
    # SUM(grid[h] * tariff[h])
    #
    # Solar, battery flow and battery state have zero direct cost.
    # ---------------------------------------------------------

    objective = np.zeros(
        VARIABLE_COUNT,
        dtype=float,
    )

    for h in range(HOURS):
        objective[GRID_START + h] = tariff[h]

    # ---------------------------------------------------------
    # 6. Variable bounds
    # ---------------------------------------------------------

    bounds = []

    # Grid:
    # 0 <= grid <= optional operator grid cap

    for h in range(HOURS):
        bounds.append(
            (
                0.0,
                grid_upper[h],
            )
        )

    # Solar:
    # 0 <= solar_used <= effective solar

    for h in range(HOURS):
        bounds.append(
            (
                0.0,
                float(effective_solar[h]),
            )
        )

    # Battery flow:
    #
    # negative = discharge
    # positive = charge

    for h in range(HOURS):
        bounds.append(
            (
                float(battery_flow_lower[h]),
                float(battery_flow_upper[h]),
            )
        )

    # Battery state:
    #
    # active reserve <= energy <= capacity

    for h in range(HOURS):
        bounds.append(
            (
                float(minimum_energy[h]),
                float(battery.capacity_kwh),
            )
        )

    # ---------------------------------------------------------
    # 7. Equality constraints
    # ---------------------------------------------------------

    equality_rows = []
    equality_values = []

    # =========================================================
    # ENERGY BALANCE
    # =========================================================
    #
    # Official rule:
    #
    # grid + solar + discharge
    # =
    # demand + charge
    #
    # Because battery_flow uses:
    #
    #   positive = charge
    #   negative = discharge
    #
    # this becomes:
    #
    # grid + solar - battery_flow = demand
    #
    # =========================================================

    for h in range(HOURS):

        row = np.zeros(
            VARIABLE_COUNT,
            dtype=float,
        )

        row[GRID_START + h] = 1.0
        row[SOLAR_START + h] = 1.0
        row[FLOW_START + h] = -1.0

        equality_rows.append(row)
        equality_values.append(demand[h])

    # =========================================================
    # BATTERY STATE TRANSITIONS
    # =========================================================
    #
    # hour 0:
    #
    # E_after[0] = initial_energy + flow[0]
    #
    # later:
    #
    # E_after[h] =
    # E_after[h - 1] + flow[h]
    #
    # =========================================================

    initial_energy = battery.initial_energy_kwh

    for h in range(HOURS):

        row = np.zeros(
            VARIABLE_COUNT,
            dtype=float,
        )

        row[ENERGY_START + h] = 1.0
        row[FLOW_START + h] = -1.0

        if h == 0:

            equality_rows.append(row)
            equality_values.append(
                initial_energy
            )

        else:

            row[ENERGY_START + h - 1] = -1.0

            equality_rows.append(row)
            equality_values.append(0.0)

    # =========================================================
    # END-OF-DAY BATTERY NEUTRALITY
    # =========================================================
    #
    # Battery must finish hour 23 at the same energy
    # level it started hour 0.
    #
    # =========================================================

    final_energy_row = np.zeros(
        VARIABLE_COUNT,
        dtype=float,
    )

    final_energy_row[ENERGY_START + 23] = 1.0

    equality_rows.append(final_energy_row)
    equality_values.append(initial_energy)

    # ---------------------------------------------------------
    # 8. Solve the linear optimization problem
    # ---------------------------------------------------------

    result = linprog(
        c=objective,
        A_eq=np.array(equality_rows),
        b_eq=np.array(equality_values),
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        raise OptimizationError(
            "Energy optimization failed: "
            f"{result.message}"
        )

    # ---------------------------------------------------------
    # 9. Extract solution
    # ---------------------------------------------------------

    solution = result.x

    grid_values = solution[
        GRID_START:GRID_START + HOURS
    ]

    solar_values = solution[
        SOLAR_START:SOLAR_START + HOURS
    ]

    battery_flows = solution[
        FLOW_START:FLOW_START + HOURS
    ]

    battery_energy = solution[
        ENERGY_START:ENERGY_START + HOURS
    ]

    # ---------------------------------------------------------
    # 10. Convert mathematical solution into API hourly_plan
    # ---------------------------------------------------------

    hourly_plan: list[HourlyPlanEntry] = []

    for h in range(HOURS):

        grid = _clean_number(
            grid_values[h]
        )

        solar = _clean_number(
            solar_values[h]
        )

        flow = _clean_number(
            battery_flows[h]
        )

        energy_after = _clean_number(
            battery_energy[h]
        )

        if flow > EPSILON:

            battery_action = "charge"
            battery_kwh = flow

        elif flow < -EPSILON:

            battery_action = "discharge"
            battery_kwh = abs(flow)

        else:

            battery_action = "idle"
            battery_kwh = 0.0

        hourly_plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=grid,
                solar_used_kwh=solar,
                battery_action=battery_action,
                battery_kwh=battery_kwh,
                battery_energy_after_kwh=energy_after,
            )
        )

    # ---------------------------------------------------------
    # 11. Calculate official totals FROM the returned plan
    # ---------------------------------------------------------

    total_grid_kwh = sum(
        entry.grid_kwh
        for entry in hourly_plan
    )

    total_cost_bdt = sum(
        hourly_plan[h].grid_kwh
        * tariff[h]
        for h in range(HOURS)
    )

    peak_grid_kwh = max(
        entry.grid_kwh
        for entry in hourly_plan
    )

    # ---------------------------------------------------------
    # 12. Deterministic human-readable summary
    # ---------------------------------------------------------

    applied_directives = [
        directive.directive_type
        for directive in directives
        if directive.applies
    ]

    if applied_directives:

        directive_text = ", ".join(
            applied_directives
        )

        plan_summary = (
            "Minimized 24-hour grid electricity cost while "
            f"applying the operator directives: {directive_text}. "
            "The schedule respects solar and battery limits and "
            "restores the battery to its initial energy level."
        )

    else:

        plan_summary = (
            "Minimized 24-hour grid electricity cost while "
            "respecting solar and battery limits and restoring "
            "the battery to its initial energy level."
        )

    return OptimizationResult(
        hourly_plan=hourly_plan,
        total_grid_kwh=_clean_number(
            total_grid_kwh
        ),
        total_cost_bdt=_clean_number(
            total_cost_bdt
        ),
        peak_grid_kwh=_clean_number(
            peak_grid_kwh
        ),
        plan_summary=plan_summary,
    )