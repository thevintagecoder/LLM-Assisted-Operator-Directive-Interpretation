# GridWise — LLM-Assisted Campus Energy Optimizer

GridWise is a FastAPI-based smart campus energy optimization system built for the BUP CSE Fest 2026 Hackathon.

The system interprets natural-language operator directives using an LLM, validates them using deterministic guardrails, and generates a cost-optimal 24-hour energy schedule using mathematical optimization.

---

## Architecture

```text
POST /optimize-energy
        |
        v
Pydantic Request Validation
        |
        v
Gemini LLM Interpretation
        |
        v
Deterministic Directive Guardrails
        |
        v
Linear Programming Optimizer
        |
        v
Independent Schedule Validator
        |
        v
Structured API Response
Features
Natural-language operator directive interpretation
Gemini model fallback handling
Deterministic validation of LLM outputs
24-hour electricity scheduling
Solar energy utilization
Battery charging and discharging optimization
Grid cost minimization
Operator constraint enforcement
Independent final schedule validation
FastAPI Swagger documentation
Docker support
Supported Operator Directives

GridWise supports:

solar_reduction
minimum_battery_reserve
no_charge_window
no_discharge_window
max_grid_window
no_op

The LLM converts operator notes into structured directives.

All LLM output is treated as untrusted until it passes deterministic validation.

Optimization Objective

The optimizer minimizes total electricity cost over 24 hours:

sum(grid_kwh[h] × tariff_bdt_per_kwh[h])

while satisfying:

hourly energy balance
solar availability
battery capacity
battery minimum energy
charge rate limits
discharge rate limits
operator directives
no grid export
final battery energy equal to initial battery energy

The optimizer uses SciPy's HiGHS linear programming solver.

API
Health Check
GET /health

Response:

{
  "status": "ok"
}
Energy Optimization
POST /optimize-energy

The endpoint accepts:

scenario ID
1–3 operator notes
24 hourly demand/solar/tariff entries
battery configuration

It returns:

interpreted operator directives
24-hour optimized energy schedule
total grid consumption
total electricity cost
peak grid usage
plan summary
Local Setup
1. Clone the repository
git clone https://github.com/thevintagecoder/LLM-Assisted-Operator-Directive-Interpretation.git
cd LLM-Assisted-Operator-Directive-Interpretation
2. Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
4. Configure environment variables

Create a .env file:

GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.6-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite

Never commit .env.

5. Start the API
python -m uvicorn app.main:app --reload --reload-dir app

Open Swagger:

http://127.0.0.1:8000/docs
Docker

Build the image:

docker build -t gridwise-llm .

Run:

docker run --name gridwise-api \
  --env-file .env \
  -p 8000:8000 \
  gridwise-llm

Test:

curl http://127.0.0.1:8000/health
Testing
Optimizer tests
python -m scripts.test_optimizer

Result:

Passed: 10
Failed: 0
Final schedule validator
python -m scripts.test_validator

Result:

Passed: 10
Failed: 0

The validator also deliberately tests a corrupted schedule and verifies that it is rejected.

Full end-to-end API tests
python -m scripts.test_all_api_cases

Current public-case result:

Passed: 10
Failed: 0
Reliability

If the primary Gemini model is temporarily unavailable or rate-limited, GridWise automatically attempts the configured fallback model.

The LLM does not directly control the optimizer.

LLM output must first pass deterministic validation before it can influence the energy schedule.

The generated optimization result is then independently replayed and validated before being returned by the API.

Technology Stack
Python 3.11
FastAPI
Pydantic
Google Gemini API
SciPy
NumPy
HiGHS Linear Programming Solver
Docker
Uvicorn
Project Structure
gridwise-llm/
├── app/
│   ├── main.py
│   ├── models.py
│   │
│   ├── llm/
│   │   └── interpreter.py
│   │
│   ├── guardrails/
│   │   └── directives.py
│   │
│   ├── optimizer/
│   │   └── energy_optimizer.py
│   │
│   └── validators/
│       └── schedule_validator.py
│
├── scripts/
│   ├── test_interpreter.py
│   ├── test_guardrails.py
│   ├── test_optimizer.py
│   ├── test_validator.py
│   ├── test_api.py
│   └── test_all_api_cases.py
│
├── tests/
│   └── data/
│
├── Dockerfile
├── .dockerignore
├── .env.example
├── requirements.txt
└── README.md
Security

Secrets such as the Gemini API key are loaded using environment variables and are not stored in the repository.

Operator notes are treated as untrusted input, and instructions attempting to override system rules are not followed.

Author

Built for the BUP CSE Fest 2026 Smart Campus Energy Optimization Challenge
```
