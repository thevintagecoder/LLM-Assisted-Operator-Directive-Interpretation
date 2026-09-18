# GridWise LLM Energy Optimizer

BUP CSE Fest 2026 Hackathon preliminary-round solution.

## Architecture

The system will use the following pipeline:

Operator Notes
→ LLM Interpreter
→ Deterministic Guardrails
→ Energy Optimizer
→ Final Validation
→ API Response

## Current Development

Implemented:

- FastAPI service
- `GET /health`

Planned:

- `POST /optimize-energy`
- LLM directive interpretation
- deterministic guardrails
- 24-hour energy optimizer
- schedule validation
- public sample-case testing

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

pip install -r requirements.txt

Start the API:

uvicorn app.main:app --reload

Test health:

curl http://127.0.0.1:8000/health

This README will eventually need much more detail because the judges want things like the model/provider, environment variables, optimizer/solver, run command, sample requests, guardrails, Docker instructions, and known limitations. :contentReference[oaicite:3]{index=3}

We'll build that as we go instead of doing it at the end.

---

## 10. Make your first Git commit

Stop Uvicorn if necessary with:

```text
Ctrl + C
```
