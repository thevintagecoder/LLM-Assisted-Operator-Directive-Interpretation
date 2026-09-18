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
