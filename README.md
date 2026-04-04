# Email Triage OpenEnv

A Tier-2 support benchmark for AI agents. The environment tests whether an
agent can handle realistic support workflows, not just FAQ chat.

## What This Environment Does

Simulates real support tickets where the agent must:
- classify raw incoming emails with category, priority, and order extraction
- apply policy by querying the policy tool before drafting a response
- resolve defective-item cases using order DB and inventory lookups

## Tasks

| Task | Difficulty | Description |
|------|-----------|-------------|
| task_1 | Easy | Email triage: category + priority + order ID extraction |
| task_2 | Medium | Policy response: use `query_policy`, then draft outcome |
| task_3 | Hard | Multi-system resolution: order lookup, inventory check, final action |

## Action Space

Actions are JSON objects with an `action_type` field.

### Task 1 actions
- `{"action_type":"classify_email","category":"Shipping Delay","priority":"Normal","order_id":"ORD-1001"}`

### Task 2 actions
- `{"action_type":"query_policy","policy_question":"Can a 40-day-old order be returned?"}`
- `{"action_type":"draft_response","response_text":"...outside the 30-day window..."}`

### Task 3 actions
- `{"action_type":"query_order_db","order_id":"ORD-5001"}`
- `{"action_type":"query_inventory","sku":"SKU-BLEND-01"}`
- `{"action_type":"ship_replacement","order_id":"ORD-5001","reason":"defective_item"}`
- `{"action_type":"issue_refund","order_id":"ORD-5002","reason":"out_of_stock_replacement"}`

## Observation Space

Observations include:
- `task_id`, `step_number`
- `inbox` and `current_email` for `task_1`
- `ticket` for `task_2` and `task_3`
- `available_actions`
- `tool_traces` (tool call history)
- `context`, `last_action_error`

## Reward Function

All tasks score in `[0.0, 1.0]` with deterministic grading:
- `task_1`: `0.33` category + `0.33` priority + `0.34` order ID
- `task_2`: `0.5` if `query_policy` was called before answer + `0.5` for correct policy outcome
- `task_3`: `0.2` order DB query + `0.2` inventory query + `0.6` correct final action

Fail conditions in `task_3` force score `0.0`:
- issuing a refund while inventory is available
- shipping a replacement for an order that does not exist

## Baseline Scores

| Task | GPT-4o-mini Score |
|------|------------------|
| task_1 | 0.XXXX |
| task_2 | 0.XXXX |
| task_3 | 0.XXXX |

## Setup

pip install -r requirements.txt
uvicorn api.main:app --port 8000

## UI Frontend (Interactive Demo)

This project now includes a browser UI to demo how the environment works step-by-step.

- URL: `http://127.0.0.1:8000/ui`
- Features:
	- Task selector (`task_1`, `task_2`, `task_3`)
	- Manual action builder and submit
	- Auto Next and full Run Episode
	- Live metrics + timeline
	- Human-readable observation and final task response panels

### Run Locally (Windows PowerShell)

From `email-triage-env/`:

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/ui
```

If your terminal is not in `email-triage-env/`, use absolute paths:

```powershell
& "C:\path\to\email-triage-env\.venv\Scripts\python.exe" -m uvicorn api.main:app --app-dir "C:\path\to\email-triage-env" --host 127.0.0.1 --port 8000
```

## Run Baseline Agent

export GEMINI_API_KEY=your_key
export GEMINI_MODEL=gemini-1.5-flash
export GEMINI_API_BASE=https://generativelanguage.googleapis.com/v1beta
export ENV_URL=https://YOUR_USERNAME-email-triage-env.hf.space
python inference.py
