# GridWise — LLM-Assisted Campus Energy Optimizer

GridWise is a FastAPI-based smart campus energy optimization system built for the **BUP CSE Fest 2026 Hackathon — Smart Campus Energy Optimization Challenge**.

The system interprets natural-language operator directives using an LLM, validates the LLM output using deterministic guardrails, and generates a cost-optimal 24-hour energy schedule using mathematical optimization.

---

## Live Deployment

### API Base URL

https://llm-assisted-operator-directive.onrender.com

### Swagger Documentation

https://llm-assisted-operator-directive.onrender.com/docs

### Health Check

https://llm-assisted-operator-directive.onrender.com/health

Expected response:

```json
{
  "status": "ok"
}
```

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
Primary / Fallback Model Handling
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
```

The LLM is used only to understand the natural-language operator notes.

It does not directly control the optimization process.

Every LLM-generated directive must pass deterministic validation before it can affect the energy schedule.

---

## Features

- Natural-language operator directive interpretation
- Gemini-powered structured extraction
- Primary and fallback LLM handling
- Deterministic validation of LLM outputs
- 24-hour campus energy scheduling
- Solar energy utilization
- Battery charge/discharge optimization
- Grid electricity cost minimization
- Operator constraint enforcement
- Independent final schedule validation
- FastAPI REST API
- Swagger / OpenAPI documentation
- Docker support
- Public Render deployment
- Health monitoring support

---

## Supported Operator Directives

GridWise supports six directive types:

### `solar_reduction`

Temporarily reduces usable solar generation.

Example:

```text
"Solar output will be reduced by 80% from 1 PM until 3 PM."
```

Structured interpretation:

```json
{
  "hours": [13, 14],
  "factor": 0.2
}
```

The factor represents the fraction of solar energy remaining.

---

### `minimum_battery_reserve`

Requires the battery to maintain a minimum energy level during specified hours.

Example:

```text
"Keep at least 50% of battery capacity in reserve from 6 PM until 9 PM."
```

For a 200 kWh battery:

```json
{
  "hours": [18, 19, 20],
  "minimum_energy_kwh": 100
}
```

---

### `no_charge_window`

Prevents battery charging during specified hours.

Example:

```text
"Do not charge the battery between 2 PM and 4 PM."
```

Structured interpretation:

```json
{
  "hours": [14, 15]
}
```

---

### `no_discharge_window`

Prevents battery discharge during specified hours.

Example:

```text
"Do not discharge the battery from 6 PM until 8 PM."
```

Structured interpretation:

```json
{
  "hours": [18, 19]
}
```

---

### `max_grid_window`

Limits grid electricity usage during specified hours.

Example:

```text
"Grid import must not exceed 155 kWh from 6 PM until 9 PM."
```

Structured interpretation:

```json
{
  "hours": [18, 19, 20],
  "max_grid_kwh": 155
}
```

---

### `no_op`

Used when an operator note does not affect the current energy schedule.

Example:

```text
"The sports office moved next month's registration deadline."
```

Structured interpretation:

```json
{
  "applies": false,
  "directive_type": "no_op",
  "structured_adjustment": null
}
```

---

## Time Interpretation Rules

GridWise uses 24-hour integer time values from `0` through `23`.

Intervals are:

```text
start-inclusive
end-exclusive
```

For example:

```text
1 PM to 3 PM
```

becomes:

```json
[13, 14]
```

and:

```text
2 AM to 5 AM
```

becomes:

```json
[2, 3, 4]
```

---

## Optimization Objective

The optimizer minimizes total electricity cost over the 24-hour scheduling period:

```text
SUM(grid_kwh[h] × tariff_bdt_per_kwh[h])
```

subject to all energy and operator constraints.

---

## Energy Constraints

The optimizer enforces the following rules.

### Hourly Energy Balance

```text
grid
+ solar used
+ battery discharge
=
demand
+ battery charge
```

### Battery Constraints

The battery must respect:

- battery capacity
- minimum battery energy
- maximum charge rate per hour
- maximum discharge rate per hour
- operator reserve requirements
- no-charge windows
- no-discharge windows

The battery must also finish hour 23 at the same energy level at which it started the day.

### Solar Constraints

Solar usage must never exceed available solar after applying operator directives.

### Grid Constraints

Grid import:

- cannot be negative
- cannot export electricity
- must obey any active `max_grid_window` directive

---

## Mathematical Optimizer

GridWise uses:

```text
SciPy
+
HiGHS Linear Programming Solver
```

The optimizer uses a single signed battery-flow variable:

```text
positive battery flow → charging

negative battery flow → discharging

zero battery flow     → idle
```

This prevents simultaneous charging and discharging by construction.

---

## LLM Guardrails

LLM output is treated as untrusted.

Before any directive reaches the optimizer, GridWise deterministically checks:

- exactly one interpretation per operator note
- correct note order
- valid `note_index`
- supported directive type
- correct `applies` value
- valid structured adjustment
- valid hours
- hours between `0` and `23`
- no duplicate hours
- ascending hour order
- solar factor between `0` and `1`
- battery reserve within battery capacity
- non-negative grid cap
- correct `no_op` structure

The guardrail also normalizes the generic Gemini output into the exact directive structure required by the API.

---

## LLM Reliability

GridWise supports a primary and fallback Gemini model.

Current configuration:

```text
Primary:
gemini-3.6-flash

Fallback:
gemini-3.5-flash-lite
```

If the primary model experiences a temporary error such as:

```text
429
500
502
503
504
```

GridWise can switch to the fallback model.

The primary model is temporarily placed into cooldown after transient provider failures to prevent repeated requests to an overloaded model.

---

## Final Schedule Validation

The optimizer output is not returned immediately.

A separate deterministic validator independently replays all 24 hours and verifies:

- 24 hourly entries exist
- hours are exactly `0` through `23`
- energy balance
- solar limits
- charge limits
- discharge limits
- battery state transitions
- battery capacity
- battery minimum reserve
- no-charge directives
- no-discharge directives
- grid-cap directives
- final battery neutrality
- total grid consumption
- total electricity cost
- peak grid usage

If the generated schedule violates any rule, the response is rejected.

---

# API

## Health Check

### Request

```http
GET /health
```

### Response

```json
{
  "status": "ok"
}
```

---

## Energy Optimization

### Request

```http
POST /optimize-energy
```

The request contains:

- scenario ID
- 1–3 natural-language operator notes
- 24 hourly demand, solar and tariff entries
- battery configuration

Example structure:

```json
{
  "scenario_id": "EXAMPLE-01",
  "operator_notes": ["Do not charge the battery between 2 PM and 4 PM."],
  "hours": [
    {
      "hour": 0,
      "demand_kwh": 90,
      "solar_kwh": 0,
      "tariff_bdt_per_kwh": 6
    }
  ],
  "battery": {
    "capacity_kwh": 220,
    "initial_energy_kwh": 110,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
```

The actual request must contain exactly 24 hourly entries.

---

## Response

The endpoint returns:

```json
{
  "scenario_id": "EXAMPLE-01",
  "directive_interpretation": [],
  "hourly_plan": [],
  "total_grid_kwh": 0,
  "total_cost_bdt": 0,
  "peak_grid_kwh": 0,
  "plan_summary": "..."
}
```

The `hourly_plan` contains exactly 24 entries.

Each entry contains:

```text
hour
grid_kwh
solar_used_kwh
battery_action
battery_kwh
battery_energy_after_kwh
```

---

# Production Deployment

GridWise is deployed on Render.

### Base URL

```text
https://llm-assisted-operator-directive.onrender.com
```

### Swagger

```text
https://llm-assisted-operator-directive.onrender.com/docs
```

### Health Check

```text
https://llm-assisted-operator-directive.onrender.com/health
```

The production health endpoint is monitored periodically to verify service availability.

---

# Production Benchmark

All 10 public test scenarios were executed against the deployed Render API.

Results:

```text
Passed: 10
Failed: 0

Average latency: 1.70s
P95 latency: 1.89s
Slowest request: 2.03s
```

This benchmark includes:

```text
internet request
+
Render deployment
+
LLM interpretation
+
guardrails
+
mathematical optimization
+
final validation
+
API response
```

---

# Testing

## Optimizer Test

Run:

```bash
python -m scripts.test_optimizer
```

Result:

```text
Passed: 10
Failed: 0
```

---

## Final Validator Test

Run:

```bash
python -m scripts.test_validator
```

Result:

```text
Passed: 10
Failed: 0
```

The validator test also deliberately corrupts a valid schedule.

Expected result:

```text
PASS: Validator rejected corrupted schedule.
```

This verifies that the final validator does not blindly trust optimizer output.

---

## Local End-to-End API Test

Run:

```bash
python -m scripts.test_all_api_cases
```

Result:

```text
Passed: 10
Failed: 0
```

This test exercises:

```text
operator note
→ Gemini
→ guardrail
→ optimizer
→ validator
→ API response
```

---

## Production API Test

Run:

```bash
python -m scripts.test_render_api
```

This sends the 10 public cases to the actual deployed Render endpoint.

Production result:

```text
Passed: 10
Failed: 0
Average latency: 1.70s
P95 latency: 1.89s
Slowest request: 2.03s
```

---

# Local Setup

## 1. Clone the Repository

```bash
git clone https://github.com/thevintagecoder/LLM-Assisted-Operator-Directive-Interpretation.git

cd LLM-Assisted-Operator-Directive-Interpretation
```

---

## 2. Create a Virtual Environment

```bash
python3.11 -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file in the repository root:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.6-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
```

Never commit the `.env` file.

An `.env.example` file is provided for reference.

---

## 5. Start the API

```bash
python -m uvicorn app.main:app --reload --reload-dir app
```

The local API will run at:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

---

# Docker

## Build the Image

```bash
docker build -t gridwise-llm .
```

---

## Run the Container

```bash
docker run \
  --name gridwise-api \
  --env-file .env \
  -p 8000:8000 \
  gridwise-llm
```

---

## Test the Container

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "ok"
}
```

Swagger should then be available at:

```text
http://127.0.0.1:8000/docs
```

---

# Project Structure

```text
gridwise-llm/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── interpreter.py
│   │
│   ├── guardrails/
│   │   ├── __init__.py
│   │   └── directives.py
│   │
│   ├── optimizer/
│   │   ├── __init__.py
│   │   └── energy_optimizer.py
│   │
│   └── validators/
│       ├── __init__.py
│       └── schedule_validator.py
│
├── scripts/
│   ├── __init__.py
│   ├── test_interpreter.py
│   ├── test_guardrails.py
│   ├── test_optimizer.py
│   ├── test_validator.py
│   ├── test_api.py
│   ├── test_all_api_cases.py
│   └── test_render_api.py
│
├── tests/
│   └── data/
│       └── public_cases.json
│
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# Technology Stack

### Backend

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic

### Language Model

- Google Gemini API

### Optimization

- SciPy
- NumPy
- HiGHS Linear Programming Solver

### Deployment

- Docker
- Render

### Monitoring

- Health endpoint
- External HTTP uptime monitoring

---

# Security

GridWise follows several defensive practices.

### API Keys

Secrets are loaded using environment variables.

The real Gemini API key is never stored in the repository.

### Prompt Injection Protection

Operator notes are treated as untrusted data.

The system instruction explicitly prevents operator-note content from overriding the directive interpretation rules.

### LLM Output Validation

LLM-generated structured data must pass deterministic guardrails before reaching the optimizer.

### Final Plan Validation

The optimizer output is independently verified before being returned by the API.

---

# Reliability Strategy

GridWise uses multiple layers of reliability:

```text
Pydantic request validation
        ↓
LLM interpretation
        ↓
LLM provider fallback
        ↓
directive guardrails
        ↓
mathematical optimizer
        ↓
independent schedule validator
        ↓
FastAPI response validation
```

This separation ensures that no single probabilistic LLM output is trusted without deterministic checks.

---

# Repository

GitHub:

```text
https://github.com/thevintagecoder/LLM-Assisted-Operator-Directive-Interpretation
```

---

# Author

Built for the **BUP CSE Fest 2026 Smart Campus Energy Optimization Challenge**.
