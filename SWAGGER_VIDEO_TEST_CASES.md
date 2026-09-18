# GridWise — Swagger Video Test Script

Use this script while recording the Swagger UI demo.
Each section tells you **where to click**, **what JSON to paste**, and **what the response should show**.

> ✅ The pipeline is now wired in `app/main.py`: operator notes → LLM interpreter → deterministic guardrails → energy optimizer → final validation → response.
>
> ⚠️ Requirements for the `/optimize-energy` tests:
> - A valid `GEMINI_API_KEY` in `.env`.
> - Enough API quota. If you see `429 RESOURCE_EXHAUSTED`, wait a moment or switch to a key/plan with quota.
> - Internet access to reach the Gemini API.
>
> The public reference `total_cost_bdt` should match. `peak_grid_kwh` may differ slightly when several optimal schedules exist — that is still accepted.

---

## 1. Start the server and open Swagger

```bash
uvicorn app.main:app --reload
```

Open browser:

```text
http://127.0.0.1:8000/docs
```

What you should see:
- Swagger UI loads.
- Two endpoints listed: `GET /health` and `POST /optimize-energy`.

---

## 2. Smoke test — `GET /health`

### Where to write
- Click **GET /health**.
- Click **Try it out**.
- Click **Execute**.

### What you should see
- **Code:** `200`
- **Response body:**

```json
{
  "status": "ok"
}
```

---

## 3. Test case — solar reduction + distractor note

### Where to write
- Click **POST /optimize-energy**.
- Click **Try it out**.
- In the request body box, **replace** the example with the JSON below.
- Click **Execute**.

### What to write (request body)

```json
{
  "scenario_id": "SAMPLE-01",
  "operator_notes": [
    "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
    "The sports office moved next month's registration deadline."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 6, "demand_kwh": 110, "solar_kwh": 5, "tariff_bdt_per_kwh": 8 },
    { "hour": 7, "demand_kwh": 130, "solar_kwh": 20, "tariff_bdt_per_kwh": 10 },
    { "hour": 8, "demand_kwh": 150, "solar_kwh": 50, "tariff_bdt_per_kwh": 12 },
    { "hour": 9, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14 },
    { "hour": 10, "demand_kwh": 175, "solar_kwh": 130, "tariff_bdt_per_kwh": 16 },
    { "hour": 11, "demand_kwh": 180, "solar_kwh": 160, "tariff_bdt_per_kwh": 16 },
    { "hour": 12, "demand_kwh": 185, "solar_kwh": 180, "tariff_bdt_per_kwh": 15 },
    { "hour": 13, "demand_kwh": 180, "solar_kwh": 170, "tariff_bdt_per_kwh": 14 },
    { "hour": 14, "demand_kwh": 170, "solar_kwh": 140, "tariff_bdt_per_kwh": 13 },
    { "hour": 15, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14 },
    { "hour": 16, "demand_kwh": 170, "solar_kwh": 45, "tariff_bdt_per_kwh": 18 },
    { "hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 22 },
    { "hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 28 },
    { "hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30 },
    { "hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26 },
    { "hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18 },
    { "hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10 },
    { "hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7 }
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

### What you should see
- **Code:** `200`
- `directive_interpretation[0]` has `directive_type: "solar_reduction"`, `hours: [12, 13]`, `factor: 0.25`.
- `directive_interpretation[1]` has `directive_type: "no_op"`, `applies: false`, `structured_adjustment: null`.
- `hourly_plan` has exactly 24 entries.
- Expected totals:
  - `total_grid_kwh`: ~2692.5
  - `total_cost_bdt`: **38365** (should match within 0.01)
  - `peak_grid_kwh`: non-negative, recalculated from the plan
- `plan_summary` mentions the reduced solar and the distractor being ignored.

---

## 4. Test case — no-charge maintenance window

### Where to write
- **POST /optimize-energy** → **Try it out** → paste the JSON below → **Execute**.

### What to write (request body)

```json
{
  "scenario_id": "SAMPLE-02",
  "operator_notes": [
    "The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 1, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 2, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 4 },
    { "hour": 3, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 4 },
    { "hour": 4, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 4 },
    { "hour": 5, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 6, "demand_kwh": 120, "solar_kwh": 0, "tariff_bdt_per_kwh": 7 },
    { "hour": 7, "demand_kwh": 135, "solar_kwh": 10, "tariff_bdt_per_kwh": 9 },
    { "hour": 8, "demand_kwh": 145, "solar_kwh": 30, "tariff_bdt_per_kwh": 11 },
    { "hour": 9, "demand_kwh": 155, "solar_kwh": 55, "tariff_bdt_per_kwh": 13 },
    { "hour": 10, "demand_kwh": 165, "solar_kwh": 80, "tariff_bdt_per_kwh": 15 },
    { "hour": 11, "demand_kwh": 175, "solar_kwh": 100, "tariff_bdt_per_kwh": 16 },
    { "hour": 12, "demand_kwh": 180, "solar_kwh": 110, "tariff_bdt_per_kwh": 16 },
    { "hour": 13, "demand_kwh": 175, "solar_kwh": 105, "tariff_bdt_per_kwh": 15 },
    { "hour": 14, "demand_kwh": 165, "solar_kwh": 85, "tariff_bdt_per_kwh": 14 },
    { "hour": 15, "demand_kwh": 160, "solar_kwh": 60, "tariff_bdt_per_kwh": 15 },
    { "hour": 16, "demand_kwh": 170, "solar_kwh": 30, "tariff_bdt_per_kwh": 19 },
    { "hour": 17, "demand_kwh": 190, "solar_kwh": 10, "tariff_bdt_per_kwh": 24 },
    { "hour": 18, "demand_kwh": 210, "solar_kwh": 0, "tariff_bdt_per_kwh": 31 },
    { "hour": 19, "demand_kwh": 220, "solar_kwh": 0, "tariff_bdt_per_kwh": 33 },
    { "hour": 20, "demand_kwh": 210, "solar_kwh": 0, "tariff_bdt_per_kwh": 29 },
    { "hour": 21, "demand_kwh": 180, "solar_kwh": 0, "tariff_bdt_per_kwh": 20 },
    { "hour": 22, "demand_kwh": 145, "solar_kwh": 0, "tariff_bdt_per_kwh": 11 },
    { "hour": 23, "demand_kwh": 115, "solar_kwh": 0, "tariff_bdt_per_kwh": 7 }
  ],
  "battery": {
    "capacity_kwh": 200,
    "initial_energy_kwh": 70,
    "minimum_energy_kwh": 30,
    "max_charge_kwh_per_hour": 55,
    "max_discharge_kwh_per_hour": 55
  }
}
```

### What you should see
- **Code:** `200`
- `directive_interpretation[0]` has `directive_type: "no_charge_window"`, `hours: [2, 3, 4]`.
- Hours 2, 3, and 4 in `hourly_plan` should never show `battery_action: "charge"`.
- Expected totals:
  - `total_grid_kwh`: ~2915
  - `total_cost_bdt`: **42885** (should match within 0.01)
  - `peak_grid_kwh`: non-negative, recalculated from the plan

---

## 5. Test case — minimum battery reserve as percentage

### Where to write
- **POST /optimize-energy** → **Try it out** → paste the JSON below → **Execute**.

### What to write (request body)

```json
{
  "scenario_id": "SAMPLE-03",
  "operator_notes": [
    "Keep at least 50% of the battery capacity stored in the battery from 6 PM until 9 PM for emergency operations."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 6, "demand_kwh": 110, "solar_kwh": 5, "tariff_bdt_per_kwh": 8 },
    { "hour": 7, "demand_kwh": 130, "solar_kwh": 20, "tariff_bdt_per_kwh": 10 },
    { "hour": 8, "demand_kwh": 150, "solar_kwh": 50, "tariff_bdt_per_kwh": 12 },
    { "hour": 9, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14 },
    { "hour": 10, "demand_kwh": 175, "solar_kwh": 130, "tariff_bdt_per_kwh": 16 },
    { "hour": 11, "demand_kwh": 180, "solar_kwh": 160, "tariff_bdt_per_kwh": 16 },
    { "hour": 12, "demand_kwh": 185, "solar_kwh": 180, "tariff_bdt_per_kwh": 15 },
    { "hour": 13, "demand_kwh": 180, "solar_kwh": 170, "tariff_bdt_per_kwh": 14 },
    { "hour": 14, "demand_kwh": 170, "solar_kwh": 140, "tariff_bdt_per_kwh": 13 },
    { "hour": 15, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14 },
    { "hour": 16, "demand_kwh": 170, "solar_kwh": 45, "tariff_bdt_per_kwh": 18 },
    { "hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 22 },
    { "hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 28 },
    { "hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30 },
    { "hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26 },
    { "hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18 },
    { "hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10 },
    { "hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7 }
  ],
  "battery": {
    "capacity_kwh": 200,
    "initial_energy_kwh": 120,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
```

### What you should see
- **Code:** `200`
- `directive_interpretation[0]` has `directive_type: "minimum_battery_reserve"`, `hours: [18, 19, 20]`, `minimum_energy_kwh: 100`.
- `battery_energy_after_kwh` for hours 18, 19, 20 must be **≥ 100**.
- Expected totals:
  - `total_grid_kwh`: ~2430
  - `total_cost_bdt`: **35480** (should match within 0.01)
  - `peak_grid_kwh`: non-negative, recalculated from the plan

---

## 6. Test case — no-discharge protection window

### Where to write
- **POST /optimize-energy** → **Try it out** → paste the JSON below → **Execute**.

### What to write (request body)

```json
{
  "scenario_id": "SAMPLE-04",
  "operator_notes": [
    "For protection testing, the battery must not discharge from 6 PM until 8 PM."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 7 },
    { "hour": 1, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 2, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 3, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 4, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 5, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 6, "demand_kwh": 115, "solar_kwh": 5, "tariff_bdt_per_kwh": 8 },
    { "hour": 7, "demand_kwh": 130, "solar_kwh": 15, "tariff_bdt_per_kwh": 10 },
    { "hour": 8, "demand_kwh": 145, "solar_kwh": 40, "tariff_bdt_per_kwh": 12 },
    { "hour": 9, "demand_kwh": 155, "solar_kwh": 75, "tariff_bdt_per_kwh": 14 },
    { "hour": 10, "demand_kwh": 165, "solar_kwh": 110, "tariff_bdt_per_kwh": 16 },
    { "hour": 11, "demand_kwh": 175, "solar_kwh": 145, "tariff_bdt_per_kwh": 16 },
    { "hour": 12, "demand_kwh": 180, "solar_kwh": 165, "tariff_bdt_per_kwh": 15 },
    { "hour": 13, "demand_kwh": 175, "solar_kwh": 155, "tariff_bdt_per_kwh": 14 },
    { "hour": 14, "demand_kwh": 170, "solar_kwh": 125, "tariff_bdt_per_kwh": 13 },
    { "hour": 15, "demand_kwh": 165, "solar_kwh": 80, "tariff_bdt_per_kwh": 14 },
    { "hour": 16, "demand_kwh": 175, "solar_kwh": 35, "tariff_bdt_per_kwh": 17 },
    { "hour": 17, "demand_kwh": 195, "solar_kwh": 5, "tariff_bdt_per_kwh": 21 },
    { "hour": 18, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 29 },
    { "hour": 19, "demand_kwh": 225, "solar_kwh": 0, "tariff_bdt_per_kwh": 32 },
    { "hour": 20, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30 },
    { "hour": 21, "demand_kwh": 185, "solar_kwh": 0, "tariff_bdt_per_kwh": 20 },
    { "hour": 22, "demand_kwh": 150, "solar_kwh": 0, "tariff_bdt_per_kwh": 11 },
    { "hour": 23, "demand_kwh": 120, "solar_kwh": 0, "tariff_bdt_per_kwh": 8 }
  ],
  "battery": {
    "capacity_kwh": 230,
    "initial_energy_kwh": 130,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 55,
    "max_discharge_kwh_per_hour": 55
  }
}
```

### What you should see
- **Code:** `200`
- `directive_interpretation[0]` has `directive_type: "no_discharge_window"`, `hours: [18, 19]`.
- Hours 18 and 19 in `hourly_plan` should never show `battery_action: "discharge"`.
- Expected totals:
  - `total_grid_kwh`: ~2645
  - `total_cost_bdt`: **40495** (should match within 0.01)
  - `peak_grid_kwh`: non-negative, recalculated from the plan

---

## 7. Test case — maximum grid import cap

### Where to write
- **POST /optimize-energy** → **Try it out** → paste the JSON below → **Execute**.

### What to write (request body)

```json
{
  "scenario_id": "SAMPLE-05",
  "operator_notes": [
    "From 6 PM until 9 PM, campus grid import must not exceed 155 kWh in any hour because the feeder is operating under a temporary limit."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5 },
    { "hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 },
    { "hour": 6, "demand_kwh": 110, "solar_kwh": 5, "tariff_bdt_per_kwh": 8 },
    { "hour": 7, "demand_kwh": 130, "solar_kwh": 20, "tariff_bdt_per_kwh": 10 },
    { "hour": 8, "demand_kwh": 150, "solar_kwh": 50, "tariff_bdt_per_kwh": 12 },
    { "hour": 9, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14 },
    { "hour": 10, "demand_kwh": 175, "solar_kwh": 130, "tariff_bdt_per_kwh": 16 },
    { "hour": 11, "demand_kwh": 180, "solar_kwh": 160, "tariff_bdt_per_kwh": 16 },
    { "hour": 12, "demand_kwh": 185, "solar_kwh": 180, "tariff_bdt_per_kwh": 15 },
    { "hour": 13, "demand_kwh": 180, "solar_kwh": 170, "tariff_bdt_per_kwh": 14 },
    { "hour": 14, "demand_kwh": 170, "solar_kwh": 140, "tariff_bdt_per_kwh": 13 },
    { "hour": 15, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14 },
    { "hour": 16, "demand_kwh": 170, "solar_kwh": 45, "tariff_bdt_per_kwh": 18 },
    { "hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 22 },
    { "hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 28 },
    { "hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30 },
    { "hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26 },
    { "hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18 },
    { "hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10 },
    { "hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7 }
  ],
  "battery": {
    "capacity_kwh": 240,
    "initial_energy_kwh": 120,
    "minimum_energy_kwh": 30,
    "max_charge_kwh_per_hour": 60,
    "max_discharge_kwh_per_hour": 60
  }
}
```

### What you should see
- **Code:** `200`
- `directive_interpretation[0]` has `directive_type: "max_grid_window"`, `hours: [18, 19, 20]`, `max_grid_kwh: 155`.
- `grid_kwh` for hours 18, 19, 20 must be **≤ 155**.
- Expected totals:
  - `total_grid_kwh`: ~2430
  - `total_cost_bdt`: **33950** (should match within 0.01)
  - `peak_grid_kwh`: non-negative, recalculated from the plan

---

## 8. Negative test — invalid request body

### Where to write
- **POST /optimize-energy** → **Try it out** → paste the JSON below → **Execute**.

### What to write (request body)

```json
{
  "scenario_id": "BAD-REQUEST",
  "operator_notes": [
    "Note one",
    ""
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 10 }
  ],
  "battery": {
    "capacity_kwh": 200,
    "initial_energy_kwh": 100,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
```

### What you should see
- **Code:** `422 Unprocessable Entity`
- Response body contains validation errors, for example:
  - Operator notes cannot be empty.
  - `hours` must contain exactly 24 unique entries.

This proves the FastAPI/Pydantic guardrails are active before any LLM call or optimization runs.

---

## Quick verification checklist

After running the positive cases, confirm:

| Check | How to see it in Swagger |
|---|---|
| 24 plan rows | `hourly_plan` array length is 24. |
| Hour uniqueness | Every `hour` from 0 to 23 appears exactly once. |
| End-of-day neutrality | `hourly_plan[23].battery_energy_after_kwh` equals `battery.initial_energy_kwh`. |
| Energy balance | For every row: `grid_kwh + solar_used_kwh + discharge = demand_kwh + charge`. |
| No invalid actions | `battery_action` is one of `charge`, `discharge`, `idle`. |
| Cost matches | `total_cost_bdt` equals Σ (`grid_kwh * tariff`) across all 24 hours. |
| Peak is consistent | `peak_grid_kwh` equals the largest `grid_kwh` in `hourly_plan` (exact value may differ from the public reference if multiple optimal schedules exist). |
