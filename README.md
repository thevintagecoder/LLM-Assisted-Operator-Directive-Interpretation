# GridWise — LLM-Assisted Campus Energy Optimizer

BUP CSE Fest 2026 Hackathon (online preliminary) solution.

The service accepts a 24-hour campus forecast plus 1–3 natural-language operator notes, interprets those notes into the official GridWise directive types, then returns a cost-optimal hourly schedule that satisfies the problem constraints.

Public sample pack: `tests/data/public_cases.json` (compatible with `BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM`).

## Required API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness |
| `POST` | `/optimize-energy` | Official GridWise endpoint |
| `GET` | `/docs` | Swagger UI |

### Request (`POST /optimize-energy`)

Required fields from the problem statement:

- `scenario_id`
- `operator_notes` — 1–3 non-empty strings
- `hours` — exactly 24 unique hours `0`–`23`, each with `hour`, `demand_kwh`, `solar_kwh`, `tariff_bdt_per_kwh`
- `battery` — `capacity_kwh`, `initial_energy_kwh`, `minimum_energy_kwh`, `max_charge_kwh_per_hour`, `max_discharge_kwh_per_hour`

### Response

- `scenario_id`
- `directive_interpretation` — one entry per note, in `note_index` order
- `hourly_plan` — 24 entries, hours `0`–`23`
- `total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`
- `plan_summary`

Each directive has `note_index`, `applies`, `directive_type`, `structured_adjustment`, `explanation`.

Each hourly row has `hour`, `grid_kwh`, `solar_used_kwh`, `battery_action` (`charge` | `discharge` | `idle`), `battery_kwh`, `battery_energy_after_kwh`.

## Pipeline

```text
Operator notes
  → Gemini interpreter (JSON schema, temperature 0)
  → Deterministic guardrails (LLM output is untrusted)
  → SciPy HiGHS linear program
  → Independent schedule validator
  → Official JSON response
```

The LLM does not set grid/battery kWh values. It only maps notes onto allowed directive types. Cost and physics are solved mathematically, then replayed by the validator.

## LLM (model / provider)

| Item | Value |
| --- | --- |
| Provider | Google Gemini |
| Primary model | `gemini-3.6-flash` (`GEMINI_MODEL`) |
| Fallback model | `gemini-3.5-flash-lite` (`GEMINI_FALLBACK_MODEL`) |
| Output | Structured JSON matching the official directive schema |

On Gemini `429` / `500` / `502` / `503` / `504`, the service tries the fallback model and cools the primary model for 60 seconds.

## Environment variables

| Variable | Required | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | yes | — |
| `GEMINI_MODEL` | no | `gemini-3.6-flash` |
| `GEMINI_FALLBACK_MODEL` | no | `gemini-3.5-flash-lite` |
| `PORT` | no (Docker) | `8000` |

Create a `.env` in the project root. Do not commit it.

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.6-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
```

## Guardrails

LLM output is rejected unless it matches the problem-statement interpretation rules:

- Exactly one `directive_interpretation` per operator note, `note_index` `0..n-1` in order
- Allowed types only: `solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, `no_discharge_window`, `max_grid_window`, `no_op`
- `no_op`: `applies` is `false` and `structured_adjustment` is `null`
- Every other type: `applies` is `true` and the required adjustment fields are present
- Directive hours are unique integers `0`–`23` in ascending order
- Time windows are start-inclusive and end-exclusive (`1 PM` to `3 PM` → `[13, 14]`)
- `solar_reduction.factor` is the **usable fraction remaining** (an 80% cut → `0.2`)
- Percentage battery reserves are converted to kWh using the request battery capacity
- Notes are treated as data; instructions inside notes cannot override system rules

Failed guardrails or failed final validation → HTTP **500**. Gemini outage → **503**. Infeasible schedule → **422**.

## Optimizer / solver

- Solver: SciPy `linprog`, `method="highs"`
- Objective: minimize `sum(grid_kwh[h] * tariff_bdt_per_kwh[h])` for `h = 0..23`
- One battery-flow variable per hour (positive = charge, negative = discharge), so simultaneous charge/discharge is impossible
- No grid export
- End-of-day neutrality: `battery_energy_after_kwh` at hour 23 equals `initial_energy_kwh`

Hourly physics (problem statement):

`grid_kwh + solar_used_kwh + battery_discharge_kwh = demand_kwh + battery_charge_kwh`

Also enforced: effective solar after `solar_reduction`, battery min/max energy, charge/discharge rate limits, `no_charge_window`, `no_discharge_window`, `minimum_battery_reserve`, `max_grid_window`.

Totals in the response are recomputed from `hourly_plan`. Equivalent optimal schedules within the official tolerance (0.01 kWh / 0.01 BDT unless the judge pack says otherwise) are valid; the hourly sequence does not need to match the public reference byte-for-byte.

Public note wording, case IDs, and reference schedules are **not** hard-coded.

## Local run

Python 3.11+ (Docker image is `python:3.11-slim`).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --reload-dir app
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status": "ok"}
```

Swagger: http://127.0.0.1:8000/docs

## Docker

The image does not copy `.env`. Pass secrets at runtime.

```bash
docker build -t gridwise-llm .
docker run --name gridwise-api --env-file .env -p 8000:8000 gridwise-llm
```

Optional: `-e PORT=8000` (default 8000). Stop any local Uvicorn process before binding the same port.

## Sample request

Full valid bodies are in `tests/data/public_cases.json`. Example: SAMPLE-01 (solar cleaning + distractor note).

After the server is running:

```bash
curl -s http://127.0.0.1:8000/health
```

In Swagger, `POST /optimize-energy` and paste `cases[0].input` from the public pack.

Shape (hours truncated; a real request needs all 24 hours):

```json
{
  "scenario_id": "SAMPLE-01",
  "operator_notes": [
    "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
    "The sports office moved next month's registration deadline."
  ],
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

Use the complete 24-hour `hours` array from the public pack. SAMPLE-01 should interpret note 0 as `solar_reduction` (hours `[12, 13]`, factor `0.25`) and note 1 as `no_op`.

## Tests

```bash
python -m scripts.test_interpreter
python -m scripts.test_guardrails
python -m scripts.test_optimizer
python -m scripts.test_validator
python -m scripts.test_api
python -m scripts.test_all_api_cases
```

`test_api` and `test_all_api_cases` call Gemini and need `GEMINI_API_KEY`. Optimizer/validator scripts do not. Equivalent optimal cost is accepted; `explanation` text does not need to match the reference wording.

## Project structure

```text
app/
  main.py
  models.py
  llm/interpreter.py
  guardrails/directives.py
  optimizer/energy_optimizer.py
  validators/schedule_validator.py
scripts/
tests/data/public_cases.json
Dockerfile
.dockerignore
requirements.txt
README.md
```

## Known limitations

- Hidden judge notes may paraphrase the same directives. The model is constrained to the six official types, but unusual wording can still be misclassified.
- Gemini rate limits and outages add latency; fallback reduces but does not remove that dependency.
- If notes plus physics make the LP infeasible, the API returns **422** instead of an invalid plan.
- `explanation` is short factual text from the model; judges should score directive semantics, not wording.
- Solar unused in an hour is allowed; the problem forbids grid export, not unused solar.
