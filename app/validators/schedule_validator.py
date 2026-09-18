import math

from app.models import (
    DirectiveInterpretation,
    OptimizeEnergyRequest,
)

from app.optimizer.energy_optimizer import (
    OptimizationResult,
)


TOLERANCE = 1e-5


class ScheduleValidationError(ValueError):
    """
    Raised when the optimizer returns a schedule that violates
    the GridWise energy scheduling rules.
    """


def _close(
    first: float,
    second: float,
    tolerance: float = TOLERANCE,
) -> bool:
    """
    Compare floating-point values safely.
    """

    return abs(first - second) <= tolerance


def validate_schedule(
    request: OptimizeEnergyRequest,
    directives: list[DirectiveInterpretation],
    result: OptimizationResult,
) -> None:
    """
    Independently validate the optimizer's complete 24-hour plan.

    Returns None if the schedule is valid.

    Raises ScheduleValidationError if any rule is violated.
    """

    plan = result.hourly_plan
    battery = request.battery

    # ---------------------------------------------------------
    # 1. Validate plan structure
    # ---------------------------------------------------------

    if len(plan) != 24:
        raise ScheduleValidationError(
            "Hourly plan must contain exactly 24 entries."
        )

    actual_hours = [
        entry.hour
        for entry in plan
    ]

    expected_hours = list(range(24))

    if actual_hours != expected_hours:
        raise ScheduleValidationError(
            "Hourly plan hours must be exactly 0 through 23 "
            "in ascending order."
        )

    # ---------------------------------------------------------
    # 2. Put request data into hour order
    # ---------------------------------------------------------

    request_hour_map = {
        entry.hour: entry
        for entry in request.hours
    }

    # ---------------------------------------------------------
    # 3. Calculate effective limits after directives
    # ---------------------------------------------------------

    effective_solar = {
        hour: request_hour_map[hour].solar_kwh
        for hour in range(24)
    }

    minimum_energy = {
        hour: battery.minimum_energy_kwh
        for hour in range(24)
    }

    no_charge_hours: set[int] = set()
    no_discharge_hours: set[int] = set()

    max_grid = {
        hour: None
        for hour in range(24)
    }

    for directive in directives:

        if not directive.applies:
            continue

        adjustment = directive.structured_adjustment

        if directive.directive_type == "solar_reduction":

            for hour in adjustment.hours:
                effective_solar[hour] *= adjustment.factor

        elif (
            directive.directive_type
            == "minimum_battery_reserve"
        ):

            for hour in adjustment.hours:
                minimum_energy[hour] = max(
                    minimum_energy[hour],
                    adjustment.minimum_energy_kwh,
                )

        elif directive.directive_type == "no_charge_window":

            no_charge_hours.update(
                adjustment.hours
            )

        elif directive.directive_type == "no_discharge_window":

            no_discharge_hours.update(
                adjustment.hours
            )

        elif directive.directive_type == "max_grid_window":

            for hour in adjustment.hours:

                new_cap = adjustment.max_grid_kwh

                current_cap = max_grid[hour]

                if current_cap is None:
                    max_grid[hour] = new_cap
                else:
                    max_grid[hour] = min(
                        current_cap,
                        new_cap,
                    )

    # ---------------------------------------------------------
    # 4. Replay every hour independently
    # ---------------------------------------------------------

    previous_energy = battery.initial_energy_kwh

    for hour in range(24):

        input_hour = request_hour_map[hour]
        output_hour = plan[hour]

        grid = output_hour.grid_kwh
        solar = output_hour.solar_used_kwh
        battery_kwh = output_hour.battery_kwh
        energy_after = output_hour.battery_energy_after_kwh
        action = output_hour.battery_action

        # -----------------------------------------------------
        # All numeric values must be finite
        # -----------------------------------------------------

        values_to_check = [
            grid,
            solar,
            battery_kwh,
            energy_after,
        ]

        if not all(
            math.isfinite(value)
            for value in values_to_check
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: schedule contains a "
                "non-finite numeric value."
            )

        # -----------------------------------------------------
        # Grid import cannot be negative
        # -----------------------------------------------------

        if grid < -TOLERANCE:
            raise ScheduleValidationError(
                f"Hour {hour}: grid import cannot be negative."
            )

        # -----------------------------------------------------
        # Solar used cannot be negative
        # -----------------------------------------------------

        if solar < -TOLERANCE:
            raise ScheduleValidationError(
                f"Hour {hour}: solar usage cannot be negative."
            )

        # -----------------------------------------------------
        # Solar usage cannot exceed effective solar
        # -----------------------------------------------------

        if (
            solar
            > effective_solar[hour] + TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: solar_used_kwh exceeds "
                "available solar after operator directives."
            )

        # -----------------------------------------------------
        # Battery kWh cannot be negative
        # -----------------------------------------------------

        if battery_kwh < -TOLERANCE:
            raise ScheduleValidationError(
                f"Hour {hour}: battery_kwh cannot be negative."
            )

        # -----------------------------------------------------
        # Interpret battery action
        # -----------------------------------------------------

        if action == "charge":

            charge = battery_kwh
            discharge = 0.0

            if battery_kwh <= TOLERANCE:
                raise ScheduleValidationError(
                    f"Hour {hour}: charge action must have "
                    "positive battery_kwh."
                )

        elif action == "discharge":

            charge = 0.0
            discharge = battery_kwh

            if battery_kwh <= TOLERANCE:
                raise ScheduleValidationError(
                    f"Hour {hour}: discharge action must have "
                    "positive battery_kwh."
                )

        elif action == "idle":

            charge = 0.0
            discharge = 0.0

            if abs(battery_kwh) > TOLERANCE:
                raise ScheduleValidationError(
                    f"Hour {hour}: idle action must have "
                    "battery_kwh equal to zero."
                )

        else:
            raise ScheduleValidationError(
                f"Hour {hour}: invalid battery action."
            )

        # -----------------------------------------------------
        # Battery charge rate
        # -----------------------------------------------------

        if (
            charge
            > battery.max_charge_kwh_per_hour
            + TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: battery charging exceeds "
                "maximum hourly charge rate."
            )

        # -----------------------------------------------------
        # Battery discharge rate
        # -----------------------------------------------------

        if (
            discharge
            > battery.max_discharge_kwh_per_hour
            + TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: battery discharging exceeds "
                "maximum hourly discharge rate."
            )

        # -----------------------------------------------------
        # Battery state transition
        #
        # energy_after =
        # previous_energy + charge - discharge
        # -----------------------------------------------------

        expected_energy_after = (
            previous_energy
            + charge
            - discharge
        )

        if not _close(
            energy_after,
            expected_energy_after,
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: battery state transition is "
                f"invalid. Expected {expected_energy_after}, "
                f"got {energy_after}."
            )

        # -----------------------------------------------------
        # Battery cannot exceed capacity
        # -----------------------------------------------------

        if (
            energy_after
            > battery.capacity_kwh + TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: battery energy exceeds capacity."
            )

        # -----------------------------------------------------
        # Battery must respect active minimum reserve
        # -----------------------------------------------------

        if (
            energy_after
            < minimum_energy[hour] - TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: battery energy falls below "
                "the required minimum reserve."
            )

        # -----------------------------------------------------
        # Official energy balance:
        #
        # grid + solar + discharge
        # =
        # demand + charge
        # -----------------------------------------------------

        supply = (
            grid
            + solar
            + discharge
        )

        consumption = (
            input_hour.demand_kwh
            + charge
        )

        if not _close(
            supply,
            consumption,
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: energy balance failed. "
                f"Supply={supply}, consumption={consumption}."
            )

        # -----------------------------------------------------
        # no_charge_window
        # -----------------------------------------------------

        if (
            hour in no_charge_hours
            and charge > TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: charging is prohibited "
                "by an operator directive."
            )

        # -----------------------------------------------------
        # no_discharge_window
        # -----------------------------------------------------

        if (
            hour in no_discharge_hours
            and discharge > TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: discharging is prohibited "
                "by an operator directive."
            )

        # -----------------------------------------------------
        # max_grid_window
        # -----------------------------------------------------

        grid_cap = max_grid[hour]

        if (
            grid_cap is not None
            and grid > grid_cap + TOLERANCE
        ):
            raise ScheduleValidationError(
                f"Hour {hour}: grid import exceeds "
                f"operator cap of {grid_cap} kWh."
            )

        previous_energy = energy_after

    # ---------------------------------------------------------
    # 5. End-of-day battery neutrality
    # ---------------------------------------------------------

    if not _close(
        previous_energy,
        battery.initial_energy_kwh,
    ):
        raise ScheduleValidationError(
            "Battery must end hour 23 at its initial "
            "energy level."
        )

    # ---------------------------------------------------------
    # 6. Independently recalculate totals
    # ---------------------------------------------------------

    calculated_total_grid = sum(
        entry.grid_kwh
        for entry in plan
    )

    calculated_total_cost = sum(
        plan[hour].grid_kwh
        * request_hour_map[hour].tariff_bdt_per_kwh
        for hour in range(24)
    )

    calculated_peak_grid = max(
        entry.grid_kwh
        for entry in plan
    )

    # ---------------------------------------------------------
    # 7. Verify reported totals
    # ---------------------------------------------------------

    if not _close(
        result.total_grid_kwh,
        calculated_total_grid,
    ):
        raise ScheduleValidationError(
            "Reported total_grid_kwh does not match "
            "the hourly plan."
        )

    if not _close(
        result.total_cost_bdt,
        calculated_total_cost,
    ):
        raise ScheduleValidationError(
            "Reported total_cost_bdt does not match "
            "the hourly plan."
        )

    if not _close(
        result.peak_grid_kwh,
        calculated_peak_grid,
    ):
        raise ScheduleValidationError(
            "Reported peak_grid_kwh does not match "
            "the hourly plan."
        )