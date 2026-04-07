# Round 1 Submission Template (OpenEnv)

Use this as your final copy/paste submission note.

## 1) Project Identity

- Project name: Email Triage OpenEnv
- Environment id: `email-triage-env`
- Team name: <fill>
- Members: <fill>
- Repository: <fill>
- Demo link (optional): <fill>

## 2) Problem Statement

We built a mini RL-style customer support environment where an agent must:
- triage incoming emails
- apply support policy correctly
- resolve defective-item cases using multiple tool calls

This simulates realistic support workflows instead of single-turn QA.

## 3) Task Definitions

### Task 1: Email Triage
- Goal: predict category, priority, order_id
- Allowed action: `classify_email`
- Reward:
  - category match: 0.33
  - priority match: 0.33
  - order_id match: 0.34

### Task 2: Policy-Based Response
- Goal: query policy first, then give policy-correct response
- Allowed actions: `query_policy`, `draft_response`
- Reward:
  - queried policy before answer: 0.5
  - correct outcome (30-day logic): 0.5

### Task 3: Multi-System Resolution
- Goal: use order + inventory tools before final action
- Allowed actions: `query_order_db`, `query_inventory`, `ship_replacement`, `issue_refund`
- Reward:
  - queried order DB: 0.2
  - queried inventory: 0.2
  - correct final action: 0.6
- Hard fail conditions:
  - refund while stock is available
  - replacement for non-existent order

## 4) Observation and Action Space

Observation includes:
- `task_id`, `step_number`
- `inbox` and `current_email` for task_1
- `ticket` for task_2/task_3
- `available_actions`
- `tool_traces`
- `context`
- `last_action_error`

Action format:
- JSON object with `action_type` and task-specific fields

## 5) Episode Termination

Episodes end when:
- max steps are reached, or
- final task decision is made (task_2/task_3), or
- all task_1 emails are triaged

## 6) Reproducibility

Run locally:

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
python inference.py
```

Core endpoints:
- `POST /reset/{task_id}`
- `POST /step/{task_id}`
- `GET /state/{task_id}`

No API key is required for deterministic baseline behavior.
Optional LLM usage is only a fallback path.

## 7) Baseline Results

Fill this table with your local run outputs.

| Task | Score | Notes |
|------|-------|-------|
| task_1 | <fill> | RL-style learner + heuristic features |
| task_2 | <fill> | deterministic policy-first sequence |
| task_3 | <fill> | deterministic tool-use sequence |

## 8) Design Choices

- Why this environment: combines classification + policy reasoning + tool-driven execution
- Why deterministic grading: stable evaluator outcomes and easier judge verification
- Why optional LLM fallback: robustness without making external APIs mandatory

## 9) Known Limitations and Next Steps

- Limited domain breadth in synthetic/support corpus mix
- Rule coverage can expand for more edge cases
- Future work: richer stochastic dynamics, adversarial tickets, multi-agent support routing

## 10) Final Checklist

- [ ] README updated and accurate
- [ ] openenv.yaml metadata complete
- [ ] setup works on clean environment
- [ ] sample traces captured
- [ ] baseline scores filled
- [ ] repo link and team details filled

## 11) Strict Pre-Submission Runbook

Run these in PowerShell from project root:

```powershell
Set-Location "c:\Users\prath\OneDrive\Desktop\openenv\openenv\email-triage-env"
```

### A) Start Docker daemon and confirm image builds

1. Open Docker Desktop and wait until it says "Engine running".
2. Verify daemon:

```powershell
docker info
```

3. Build image:

```powershell
docker build -t email-triage-env-smoke .
```

### B) Deploy to Hugging Face Space and verify health + reset

1. Login:

```powershell
huggingface-cli login
huggingface-cli whoami
```

2. Push/deploy (example):

```powershell
openenv push --repo-id your-username/email-triage-env
```

3. Verify 200 + reset (replace URL):

```powershell
$space = "https://your-username-email-triage-env.hf.space"
Invoke-RestMethod -Method GET -Uri "$space/"
Invoke-RestMethod -Method POST -Uri "$space/reset/task_1"
```

### C) Compare inference logs to expected structured format

1. Run local API and inference:

```powershell
& ".\.venv\Scripts\python.exe" -m uvicorn api.main:app --app-dir "." --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
$env:ENV_URL = "http://127.0.0.1:8000"
$env:USE_LLM_TASK1 = "0"
& ".\.venv\Scripts\python.exe" "inference.py" | Tee-Object -FilePath "inference_run.log"
```

2. Validate structured tags and required task markers:

```powershell
& ".\.venv\Scripts\python.exe" "scripts\validate_inference_log.py" --log "inference_run.log"
```

3. Final manual check: compare your `inference.py` field ordering with the official sample script exactly before final submit.

### One-command local smoke check

```powershell
.
\scripts\pre_submission_smoke.ps1 -SpaceUrl "https://your-username-email-triage-env.hf.space"
```
