from fastapi import FastAPI, HTTPException

from app.models import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
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

    # We have not built the LLM or optimizer yet.
    # For now, reaching this point means the request
    # successfully passed Pydantic validation.

    raise HTTPException(
        status_code=501,
        detail=(
            "Request schema is valid. "
            "LLM interpretation and optimization "
            "are not implemented yet."
        ),
    )