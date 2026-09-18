from fastapi import FastAPI, HTTPException

from app.guardrails.directives import (
    DirectiveValidationError,
    validate_and_normalize_directives,
)
from app.llm.interpreter import interpret_operator_notes
from app.models import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
)
from app.optimizer.energy_optimizer import (
    OptimizationError,
    optimize_energy_schedule,
)
from app.validators.schedule_validator import (
    ScheduleValidationError,
    validate_schedule,
)


app = FastAPI(
    title="GridWise LLM Energy Optimizer",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse,
)
def optimize_energy(
    request: OptimizeEnergyRequest,
) -> OptimizeEnergyResponse:
    """
    Complete GridWise optimization pipeline.

    1. Interpret operator notes using the LLM.
    2. Deterministically validate and normalize directives.
    3. Optimize the 24-hour energy schedule.
    4. Independently validate the final schedule.
    5. Return the official response structure.
    """

    # ---------------------------------------------------------
    # 1. LLM interpretation
    # ---------------------------------------------------------

    try:
        raw_interpretation = interpret_operator_notes(
            operator_notes=request.operator_notes,
            battery=request.battery,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Operator-note interpretation service "
                "is temporarily unavailable."
            ),
        ) from exc

    # ---------------------------------------------------------
    # 2. Deterministic LLM guardrails
    # ---------------------------------------------------------

    try:
        directives = validate_and_normalize_directives(
            raw_response=raw_interpretation,
            request=request,
        )

    except DirectiveValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Operator-note interpretation failed "
                f"deterministic validation: {exc}"
            ),
        ) from exc

    # ---------------------------------------------------------
    # 3. Mathematical optimization
    # ---------------------------------------------------------

    try:
        optimization_result = optimize_energy_schedule(
            request=request,
            directives=directives,
        )

    except OptimizationError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "No valid energy schedule could be produced: "
                f"{exc}"
            ),
        ) from exc

    # ---------------------------------------------------------
    # 4. Independent final schedule validation
    # ---------------------------------------------------------

    try:
        validate_schedule(
            request=request,
            directives=directives,
            result=optimization_result,
        )

    except ScheduleValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Generated schedule failed final validation: "
                f"{exc}"
            ),
        ) from exc

    # ---------------------------------------------------------
    # 5. Construct official challenge response
    # ---------------------------------------------------------

    return OptimizeEnergyResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=directives,
        hourly_plan=optimization_result.hourly_plan,
        total_grid_kwh=optimization_result.total_grid_kwh,
        total_cost_bdt=optimization_result.total_cost_bdt,
        peak_grid_kwh=optimization_result.peak_grid_kwh,
        plan_summary=optimization_result.plan_summary,
    )