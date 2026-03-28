# inference.py
import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # reads from .env file

# These 3 variables are required by the spec
API_BASE_URL = os.environ['API_BASE_URL']
MODEL_NAME   = os.environ['MODEL_NAME']
HF_TOKEN     = os.environ.get('HF_TOKEN', '')
OPENAI_KEY   = os.environ['OPENAI_API_KEY']

# Where your environment is running
ENV_URL    = os.environ.get('ENV_URL', 'http://localhost:8000')
MAX_STEPS  = 15
TEMPERATURE = 0.0   # 0.0 = deterministic = reproducible

client = OpenAI(api_key=OPENAI_KEY, base_url=API_BASE_URL)
TASKS  = ['task_1', 'task_2', 'task_3']


def parse_action(text: str) -> dict:
    """Extract a JSON action dict from the LLM's text response."""
    try:
        start = text.find('{')
        end   = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    # Fallback action if parsing fails
    return {'action_type': 'classify', 'classification': 'spam'}


SYSTEM_PROMPT = """
You are an email triage agent. You will receive details about an email in the inbox.
Your job is to decide what action to take.

Always respond with ONLY a JSON object. Valid action types are:
  classify  - requires 'classification' field (billing/spam/technical_support/complaint)
  reply     - requires 'reply_text' field (professional email reply)
  escalate  - requires 'escalation_reason' field
  archive   - no extra fields needed
  merge     - no extra fields needed

Example valid response:
  {"action_type": "classify", "classification": "billing"}

Do not include any text outside the JSON object.
"""


def run_task(task_id: str) -> float:
    print(f'\n{"="*50}')
    print(f'Running {task_id}')
    print(f'{"="*50}')

    # Reset the environment
    response = requests.post(f'{ENV_URL}/reset/{task_id}')
    response.raise_for_status()
    obs = response.json()

    total_reward = 0.0
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]

    for step_num in range(MAX_STEPS):
        current_email = obs.get('current_email', {})

        user_msg = (
            f'Task: {task_id}\n'
            f'Step: {obs.get("step_number", step_num)}\n'
            f'Current email:\n'
            f'  From: {current_email.get("sender", "unknown")}\n'
            f'  Subject: {current_email.get("subject", "")}\n'
            f'  Body: {current_email.get("body", "")}\n'
            f'Context: {obs.get("context", {})}\n\n'
            f'What action do you take? Respond with JSON only.'
        )
        messages.append({'role': 'user', 'content': user_msg})

        # LLM call using the OpenAI client
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=512
            )
            response_text = completion.choices[0].message.content or ''
        except Exception as exc:
            print(f'  LLM error at step {step_num}: {exc}')
            response_text = '{"action_type": "classify", "classification": "spam"}'

        messages.append({'role': 'assistant', 'content': response_text})

        action = parse_action(response_text)
        print(f'  Step {step_num:2d}: {action.get("action_type", "?")} ', end='')

        # Send action to environment
        step_resp = requests.post(f'{ENV_URL}/step/{task_id}', json=action)
        step_resp.raise_for_status()
        result = step_resp.json()

        reward = result.get('reward', {}).get('value', 0.0)
        total_reward += reward
        done = result.get('done', False)
        obs  = result.get('observation', {})

        print(f'| reward {reward:.3f} | done={done}')

        if done:
            print('  Episode complete.')
            break

    print(f'  Final reward for {task_id}: {total_reward:.4f}')
    return total_reward


def main():
    print('Email Triage OpenEnv - Baseline Inference')
    print(f'Model: {MODEL_NAME}')
    print(f'Environment: {ENV_URL}')

    scores = {}
    for task in TASKS:
        scores[task] = run_task(task)

    print('\n' + '='*50)
    print('FINAL BASELINE SCORES:')
    for task, score in scores.items():
        print(f'  {task}: {score:.4f}')
    avg = sum(scores.values()) / len(scores)
    print(f'  Average: {avg:.4f}')
    print('='*50)


if __name__ == '__main__':
    main()