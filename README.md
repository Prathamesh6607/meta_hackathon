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

| Task | Deterministic Agent Score | Notes |
|------|------------------------|-------|
| task_1 | 1.0 | All emails triaged correctly (4/4) |
| task_2 | 1.0 | Policy queried & response approved correctly |
| task_3 | 1.0 | Order/inventory queries + correct final action (ship replacement) |
| **Pipeline Avg** | **1.0** | Full task_1 -> task_2 -> task_3 chained flow |

*Baseline represents ideal deterministic policy behavior. Agents using external LLM assistance may vary.*

## Setup

Python runtime target: **3.10.1**

pip install -r requirements.txt
uvicorn api.main:app --port 8000

## Hugging Face Space Integration (Docker)

This project is Docker-ready for HF Spaces.

### Deployment files
- `Dockerfile` for Space runtime
- `docker-compose.deploy.yml` for local Docker deploy parity
- `.dockerignore` for lean image builds
- `scripts/deploy_hf_space.ps1` for push-to-Space automation

### Local Docker validation

```powershell
docker info
docker compose -f docker-compose.deploy.yml up --build
```

Open:

```text
http://127.0.0.1:7860/
http://127.0.0.1:7860/ui
```

### Deploy to Hugging Face Space

1. Login:

```powershell
huggingface-cli login
```

2. Push to Space:

```powershell
Set-Location "c:\Users\prath\OneDrive\Desktop\openenv\openenv\email-triage-env"
.\scripts\deploy_hf_space.ps1 -RepoId "your-username/email-triage-env" -Branch "main"
```

3. In HF Space settings, set variables if you use optional LLM path:
- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

4. Verify after deploy:

```powershell
$space = "https://your-username-email-triage-env.hf.space"
Invoke-RestMethod -Method GET -Uri "$space/"
Invoke-RestMethod -Method POST -Uri "$space/reset/task_1"
```

## Round 1 Submission Pack (Hackathon-Ready)

Use this section as your quick submission guide for OpenEnv Round 1.

### 1) Environment Summary

- Environment name: `email-triage-env`
- Domain: customer support workflow automation
- Tasks: `task_1`, `task_2`, `task_3`
- API style: Gym-like reset/step over HTTP
- Deterministic grading: yes (see reward logic below)

### 2) Observation, Action, Reward, Done

Observation fields:
- `task_id`, `step_number`
- `inbox`, `current_email` (`task_1`)
- `ticket` (`task_2`, `task_3`)
- `available_actions`, `tool_traces`, `context`, `last_action_error`

Action space:
- `task_1`: `classify_email`
- `task_2`: `query_policy`, `draft_response`
- `task_3`: `query_order_db`, `query_inventory`, `ship_replacement`, `issue_refund`

Reward function (range `[0.0, 1.0]`):
- `task_1`: `0.33 category + 0.33 priority + 0.34 order_id`
- `task_2`: `0.5` if policy queried before response + `0.5` policy-correct outcome
- `task_3`: `0.2` order query + `0.2` inventory query + `0.6` correct final action

Done conditions:
- Episode ends when `max_steps` is reached, or early when task logic is complete.
- `task_2` and `task_3` terminate on final decision action.

### 3) Hard Fail Safety Rules (Task 3)

Immediate zero score if:
- refund is issued while inventory is available
- replacement is shipped for a non-existent order

### 4) Evaluator Quick-Run

Start backend:

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Run baseline agent loop:

```bash
python inference.py
```

Core endpoints:
- `POST /reset/{task_id}`
- `POST /step/{task_id}`
- `GET /state/{task_id}`
- `POST /pipeline/run` (runs chained `task_1 -> task_2 -> task_3` with handoff)

### Chained Task Flow (Task 1 -> Task 2 -> Task 3)

The backend now supports a strict chained pipeline where each task's output becomes the next task's input:

**Flow:**
1. `task_1` generates triage actions (classify emails) and outputs best classification
2. `task_1` output is converted into a return-policy ticket for `task_2`
3. `task_2` queries policy and drafts a response
4. `task_2` policy decision becomes context for `task_3`
5. `task_3` receives a defective-item ticket and executes order/inventory queries + final action

**Run via API:**
```bash
curl -X POST http://127.0.0.1:7860/pipeline/run -H "Content-Type: application/json" -d '{"use_api": true}'
```

**Or use UI:**
- Open http://127.0.0.1:7860/ui
- Click **Run Full Pipeline** button

**Response Structure:**
```json
{
  "use_api": boolean,
  "pipeline_order": ["task_1", "task_2", "task_3"],
  "average_score": float,
  "handoff": {
    "task1_to_task2": {...synthesized task_2 case...},
    "task2_to_task3": {...synthesized task_3 case...}
  },
  "results": {
    "task_1": {score, steps, done, trace},
    "task_2": {score, steps, done, trace},
    "task_3": {score, steps, done, trace}
  }
}
```

### 5) Submission Checklist

- [ ] `openenv.yaml` metadata is complete (author, version, tags)
- [ ] README includes task/action/observation/reward descriptions
- [ ] Deterministic grader logic is documented and reproducible
- [ ] Environment runs locally with no external API key requirement
- [ ] At least one successful sample trace is included per task
- [ ] Any optional LLM path is clearly marked as optional fallback
- [ ] Dependencies are pinned and install cleanly

### 6) Sample Episode Traces (Expected Good Behavior)

`task_1` minimal trace:
1. `POST /reset/task_1`
2. Repeatedly call `POST /step/task_1` with `classify_email`
3. Episode ends after inbox emails are triaged or `max_steps`

`task_2` minimal trace:
1. `POST /reset/task_2`
2. `query_policy`
3. `draft_response` with correct 30-day decision
4. Episode ends with graded score

`task_3` minimal trace:
1. `POST /reset/task_3`
2. `query_order_db`
3. `query_inventory`
4. `ship_replacement` if in stock, otherwise `issue_refund`
5. Episode ends with graded score

For a submission handoff template you can fill in quickly, see `ROUND1_SUBMISSION.md`.

## UI Frontend (Interactive Demo)

This project now includes a browser UI to demo how the environment works step-by-step, with a Meta-blue theme and a corpus-backed support search.

- URL: `http://127.0.0.1:8000/ui`
- Features:
	- Task selector (`task_1`, `task_2`, `task_3`)
	- Optional Hugging Face Space + ML assistance toggle for auto-step
	- Manual action builder and submit
	- Auto Next and full Run Episode
	- Run Full Pipeline (`task_1 -> task_2 -> task_3`) with explicit handoff
	- Live metrics + timeline
	- Human-readable observation and final task response panels
	- Corpus-backed support recommendations from the local dataset index
	- Browser support search panel for querying the corpus directly
	- Corpus stats card showing records and top labels
	- Meta-blue visual theme for pitch/demo use

When **Hugging Face Space + ML assistance** is enabled (checkbox in UI or `use_api=true` in API):
- `task_1` attempts external email classification via HF Space, falls back to deterministic heuristic if unavailable
- `task_2` attempts external response generation, validates against policy, falls back to safe template
- `task_3` uses deterministic order/inventory logic (no external calls)
- Full pipeline runs end-to-end even if external service is unavailable

**Verified live behavior:**
- Task_1: 4 emails triaged correctly (score 1.0)
- Task_2: Policy query + approved response (score 1.0)
- Task_3: Order lookup + inventory check + ship replacement (score 1.0)
- **All three tasks chained with deterministic actions: average score 1.0**

HF Space integration is also supported for API-assisted behavior in auto-step:
- Space URL: `https://gayathrisoorya-email-classification-new.hf.space`
- Space repo id: `gayathrisoorya/email_classification_new`
- Set `HF_EMAIL_CLASSIFIER_SPACE_URL` in your environment to override target Space.

When `POST /auto-step/{task_id}` is called with `use_api=true`:
- `task_1` first attempts external email classification via the HF Space API.
- `task_2` attempts external response generation, then validates policy correctness.
- If the Space is unavailable or output is malformed, the backend falls back to deterministic logic.

The backend builds an inverted index over the local support corpus in `datasets/` and returns a retrieval-backed support recommendation for each step. That makes the demo easier to pitch to Meta because it shows explainable, corpus-grounded support triage instead of a pure black-box reply.

The active corpus file is `datasets/meta_support_subset.csv`. It was generated from the local support corpus and is preferred by the loader.

If you download a Kaggle Twitter support dataset later, place it in `datasets/` as `twcs.csv`, `customer_support_on_twitter.csv`, or `twitter_customer_support.csv` and the same index will pick it up automatically.

If you generate `datasets/meta_support_subset.csv`, the backend will prefer it first.

Backend endpoint used by the UI:
- `POST /auto-step/{task_id}` with body:
  - `use_api` (boolean)

Useful API for inspection:
- `POST /support/search` with body:
	- `query` (required)
	- `top_k` (optional)
- `GET /support/stats` for corpus size, unique tokens, and top labels

Meta subset generator:
- `python scripts/build_meta_support_subset.py <input> <output> [max_rows]`
- It keeps rows mentioning Meta-related support keywords such as Facebook, Instagram, WhatsApp, Messenger, account, login, privacy, and ads.

### Run Locally (Windows PowerShell)

From `email-triage-env/`:

```powershell
py -3.10 -m venv .venv
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

export API_BASE_URL=https://your-openai-compatible-endpoint/v1
export MODEL_NAME=your-model-id
export HF_TOKEN=your_api_token
export ENV_URL=https://YOUR_USERNAME-email-triage-env.hf.space
python inference.py

You can start from `.env.example` and load those values via your shell or `.env`.

The task_1 agent now learns online from environment rewards and persists its
policy to `datasets/task1_agent_policy.json`.

In `inference.py`, optional LLM usage for task_1 goes through an
OpenAI-compatible client using `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN`.
By default, deterministic policy behavior is used for reproducible scoring.

Useful overrides:
- `USE_LLM_TASK1=1` enables the optional LLM path for task_1 in `inference.py`.
- `TASK1_AGENT` can be instantiated with a custom policy path in code if you want to store the policy elsewhere.

### Round 1 Inference Logging

`inference.py` emits structured stdout records using three markers:
- `[START]` at run and task start
- `[STEP]` for each environment step and summary rows
- `[END]` at task completion and run completion

This format is intended for evaluator parsing and reproducible baseline scoring.

## POC Demo

See [POC.md](POC.md) for the current demo flow and pitch script.

## Regenerate UI Diagrams

The flow and feature diagrams shown in the UI are generated with Python
`matplotlib` and exported as SVG assets.

```powershell
& ".\.venv\Scripts\python.exe" -m pip install matplotlib
& ".\.venv\Scripts\python.exe" "scripts\generate_ui_diagrams.py"
```
