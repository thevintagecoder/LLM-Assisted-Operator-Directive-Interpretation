from fastapi import FastAPI, HTTPException

from app.guardrails.directives import (
    DirectiveValidationError,
    validate_and_normalize_directives,
)
from app.llm.interpreter import (
    interpret_operator_notes,
)
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
    return {"status": "ok"}


@app.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse,
)
def optimize_energy(request: OptimizeEnergyRequest):

    # ---------------------------------------------------------
    # 1. LLM interpretation
    # ---------------------------------------------------------
    # Convert natural-language operator notes into structured
    # directive candidates using Gemini.

    try:
        raw_interpretation = interpret_operator_notes(
            operator_notes=request.operator_notes,
            battery=request.battery,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM interpretation failed: {exc}",
        ) from exc

    # ---------------------------------------------------------
    # 2. Deterministic guardrails
    # ---------------------------------------------------------
    # Reject or normalize LLM output so only valid GridWise
    # directives reach the optimizer.

    try:
        directives = validate_and_normalize_directives(
            raw_response=raw_interpretation,
            request=request,
        )

    except DirectiveValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Directive validation failed: {exc}",
        ) from exc

    # ---------------------------------------------------------
    # 3. Energy optimization
    # ---------------------------------------------------------
    # Solve the 24-hour linear program that minimizes grid cost
    # while honoring the interpreted directives.

    try:
        optimization_result = optimize_energy_schedule(
            request=request,
            directives=directives,
        )

    except OptimizationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Optimization failed: {exc}",
        ) from exc

    # ---------------------------------------------------------
    # 4. Final validation
    # ---------------------------------------------------------
    # Replay every constraint to catch any inconsistency before
    # the response is returned.

    try:
        validate_schedule(
            request=request,
            directives=directives,
            result=optimization_result,
        )

    except ScheduleValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Schedule validation failed: {exc}",
        ) from exc

    # ---------------------------------------------------------
    # 5. API response
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
