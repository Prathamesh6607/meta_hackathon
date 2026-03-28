# Email Triage OpenEnv

A real-world email triage environment for AI agent benchmarking.
Built for the OpenEnv hackathon.

## What This Environment Does

Simulates a customer support inbox where an AI agent must:
- Classify incoming emails by category
- Draft professional replies
- Escalate high-priority issues to humans
- Process a full inbox workflow efficiently

## Tasks

| Task | Difficulty | Description |
|------|-----------|-------------|
| task_1 | Easy | Classify each email into the correct category |
| task_2 | Medium | Draft a professional reply that addresses the email |
| task_3 | Hard | Full inbox triage: classify, escalate, route 10 emails |

## Action Space

Actions are JSON objects with an action_type field:
- classify: {action_type: classify, classification: billing}
- reply: {action_type: reply, reply_text: 'Dear customer...'}
- escalate: {action_type: escalate, escalation_reason: 'urgent'}

## Observation Space

Observations contain: task_id, step_number, inbox (list of emails),
current_email (the email to act on), context (remaining steps, total reward)

## Reward Function

Scores range from 0.0 to 1.0 with partial credit at every step.
See graders.py for the exact scoring logic.

## Baseline Scores

| Task | GPT-4o-mini Score |
|------|------------------|
| task_1 | 0.XXXX |
| task_2 | 0.XXXX |
| task_3 | 0.XXXX |

## Setup

pip install -r requirements.txt
uvicorn api.main:app --port 8000

## Run Baseline

export OPENAI_API_KEY=your_key
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export ENV_URL=https://YOUR_USERNAME-email-triage-env.hf.space
python inference.py