from fastapi import FastAPI

app = FastAPI(
    title="GridWise LLM Energy Optimizer",
    version="0.1.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}