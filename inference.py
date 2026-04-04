# inference.py
import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()  # reads from .env file

# Gemini configuration
MODEL_NAME = os.environ.get('GEMINI_MODEL', os.environ.get('MODEL_NAME', 'gemini-1.5-flash'))
HF_TOKEN = os.environ.get('HF_TOKEN', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', os.environ.get('GOOGLE_API_KEY', ''))
GEMINI_API_BASE = os.environ.get('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com/v1beta')
USE_GEMINI_TASK1 = os.environ.get('USE_GEMINI_TASK1', os.environ.get('USE_GEMINI', '0')) == '1'

if USE_GEMINI_TASK1 and not GEMINI_API_KEY:
    raise RuntimeError('USE_GEMINI_TASK1=1 requires GEMINI_API_KEY (or GOOGLE_API_KEY).')

# Where your environment is running
ENV_URL = os.environ.get('ENV_URL', 'http://127.0.0.1:8000')
MAX_STEPS = 15
TEMPERATURE = 0.0

TASKS = ['task_1', 'task_2', 'task_3']
CATEGORY_OPTIONS = [
    'Refund Request',
    'Shipping Delay',
    'Account Access',
    'Product Defect',
    'Billing Issue',
    'General Inquiry',
]
PRIORITY_OPTIONS = ['Low', 'Normal', 'Urgent']


def parse_action(text: str) -> dict:
    """Extract a JSON action dict from model text."""
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {'action_type': 'classify_email', 'category': 'General Inquiry', 'priority': 'Low', 'order_id': None}


def as_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def extract_order_id(text: str):
    raw = text or ''
    patterns = [
        r'\bORD[-_ ]?\d+\b',
        r'\border[_\s-]*id[:#\s-]*([A-Za-z0-9-]{4,})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1) if match.lastindex else match.group(0)
        value = value.strip().upper().replace(' ', '-').replace('_', '-')
        if value.startswith('ORD') and not value.startswith('ORD-'):
            digits = re.sub(r'[^0-9]', '', value)
            if digits:
                value = f'ORD-{digits}'
        return value
    return None


def extract_days_from_text(text: str):
    match = re.search(r'(\d+)\s*day', text or '', re.IGNORECASE)
    if not match:
        return None
    return as_int(match.group(1), default=None)


def latest_tool_trace(traces: list, tool_name: str) -> dict:
    for item in reversed(traces):
        if isinstance(item, dict) and item.get('tool_name') == tool_name:
            return item
    return {}


def infer_order_exists(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    for key in ['order_exists', 'exists', 'found', 'is_valid', 'valid']:
        if key in result:
            return bool(result.get(key))
    return bool(result.get('order_id') or result.get('sku'))


def infer_in_stock(result: dict) -> int:
    if not isinstance(result, dict):
        return 0
    for key in ['in_stock', 'stock', 'available_qty', 'quantity', 'qty']:
        if key in result:
            return as_int(result.get(key), default=0)
    if isinstance(result.get('available'), bool):
        return 1 if result.get('available') else 0
    return 0


def call_gemini(messages: list, step_num: int) -> str:
    transcript = []
    for msg in messages:
        role = msg.get('role', 'user').upper()
        content = msg.get('content', '')
        transcript.append(f'{role}:\n{content}')
    prompt = '\n\n'.join(transcript)

    try:
        response = requests.post(
            f'{GEMINI_API_BASE}/models/{MODEL_NAME}:generateContent',
            params={'key': GEMINI_API_KEY},
            json={
                'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': TEMPERATURE, 'maxOutputTokens': 512},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get('candidates', [])
        if not candidates:
            return ''
        parts = candidates[0].get('content', {}).get('parts', [])
        texts = [p.get('text', '') for p in parts if isinstance(p, dict)]
        return '\n'.join([t for t in texts if t]).strip()
    except Exception as exc:
        print(f'  Gemini error at step {step_num}: {exc}')
        return ''


def choose_task_1_action_heuristic(current_email: dict) -> dict:
    subject = (current_email.get('subject') or '').lower()
    body = (current_email.get('body') or '').lower()
    text = f'{subject} {body}'

    if any(k in text for k in ['defective', 'damaged', 'cracked', 'broke', 'faulty', 'not working', 'stopped working']):
        category = 'Product Defect'
    elif any(k in text for k in ['tracking', 'where is my package', 'shipping', 'shipment', 'delayed', 'not updated', 'late', 'lost']):
        category = 'Shipping Delay'
    elif any(k in text for k in ['login', 'log in', 'password', 'account', 'two-factor', '2fa', 'authentication']):
        category = 'Account Access'
    elif any(k in text for k in ['charged', 'billing', 'invoice', 'payment', 'card', 'double charge', 'overcharged']):
        category = 'Billing Issue'
    elif 'refund' in text:
        category = 'Refund Request'
    else:
        category = 'General Inquiry'

    if any(k in text for k in ['urgent', 'asap', 'immediately', 'today', 'lawsuit', 'legal', 'angry', 'threat']):
        priority = 'Urgent'
    elif any(k in text for k in ['no rush', 'whenever', 'fyi']):
        priority = 'Low'
    else:
        priority = 'Normal'

    order_id = extract_order_id(f'{subject} {body}')
    return {'action_type': 'classify_email', 'category': category, 'priority': priority, 'order_id': order_id}


def sanitize_task_1_action(candidate: dict, current_email: dict) -> dict:
    heuristic = choose_task_1_action_heuristic(current_email)
    if not isinstance(candidate, dict):
        return heuristic
    category = candidate.get('category')
    if category not in CATEGORY_OPTIONS:
        category = heuristic.get('category')
    priority = candidate.get('priority')
    if priority not in PRIORITY_OPTIONS:
        priority = heuristic.get('priority')
    order_id = candidate.get('order_id') or extract_order_id(
        f'{current_email.get("subject", "")} {current_email.get("body", "")}'
    )
    return {'action_type': 'classify_email', 'category': category, 'priority': priority, 'order_id': order_id}


def choose_task_1_action(current_email: dict, step_num: int, use_gemini: bool) -> dict:
    if not use_gemini:
        return choose_task_1_action_heuristic(current_email)
    prompt = (
        'Extract support triage fields and return JSON only.\n'
        f'Allowed categories: {CATEGORY_OPTIONS}\n'
        f'Allowed priorities: {PRIORITY_OPTIONS}\n'
        'Return keys: action_type, category, priority, order_id.\n'
        'action_type must be "classify_email". order_id should be null when absent.\n'
        f'Subject: {current_email.get("subject", "")}\n'
        f'Body: {current_email.get("body", "")}\n'
    )
    llm_text = call_gemini(
        messages=[
            {'role': 'system', 'content': 'Return JSON only.'},
            {'role': 'user', 'content': prompt},
        ],
        step_num=step_num,
    )
    return sanitize_task_1_action(parse_action(llm_text), current_email=current_email)


def choose_task_2_action(ticket: dict, traces: list, context: dict) -> dict:
    policy_trace = latest_tool_trace(traces, 'query_policy')
    if not policy_trace:
        return {
            'action_type': 'query_policy',
            'policy_question': ticket.get('message') or 'What is the return window policy?',
        }

    result = policy_trace.get('result', {}) or {}
    window_days = as_int(result.get('window_days', result.get('return_window_days', 30)), default=30)
    days_since_delivery = context.get('days_since_delivery')
    days_since_delivery = as_int(days_since_delivery, default=-1)
    if days_since_delivery < 0:
        parsed_days = extract_days_from_text(ticket.get('message', ''))
        days_since_delivery = parsed_days if parsed_days is not None else (window_days + 1)

    if days_since_delivery <= window_days:
        response_text = (
            f'Your return is approved because it is within {window_days} days of delivery. '
            'Please share your preferred return method so we can proceed.'
        )
    else:
        response_text = (
            f'Your return is declined because it is outside {window_days} days from delivery. '
            'We can still help with troubleshooting or warranty options.'
        )
    return {'action_type': 'draft_response', 'response_text': response_text}


def choose_task_3_action(ticket: dict, traces: list) -> dict:
    order_id = ticket.get('reported_order_id')
    order_trace = latest_tool_trace(traces, 'query_order_db')
    if not order_trace:
        return {'action_type': 'query_order_db', 'order_id': order_id}

    order_result = order_trace.get('result', {}) or {}
    order_exists = infer_order_exists(order_result)
    sku = order_result.get('sku')

    if not order_exists:
        return {'action_type': 'issue_refund', 'order_id': order_id, 'reason': 'order_not_found_defective_claim'}

    inventory_trace = latest_tool_trace(traces, 'query_inventory')
    if not inventory_trace:
        if sku:
            return {'action_type': 'query_inventory', 'sku': sku}
        return {'action_type': 'issue_refund', 'order_id': order_id, 'reason': 'missing_sku_for_replacement'}

    in_stock = infer_in_stock(inventory_trace.get('result', {}) or {})
    if in_stock > 0:
        return {'action_type': 'ship_replacement', 'order_id': order_id, 'reason': 'defective_item'}
    return {'action_type': 'issue_refund', 'order_id': order_id, 'reason': 'replacement_out_of_stock'}


def choose_action(task_id: str, current_email: dict, ticket: dict, traces: list, context: dict, step_num: int, use_gemini_task1: bool) -> dict:
    if task_id == 'task_1':
        return choose_task_1_action(current_email=current_email, step_num=step_num, use_gemini=use_gemini_task1)
    if task_id == 'task_2':
        return choose_task_2_action(ticket=ticket, traces=traces, context=context)
    if task_id == 'task_3':
        return choose_task_3_action(ticket=ticket, traces=traces)
    return {'action_type': 'classify_email', 'category': 'General Inquiry', 'priority': 'Low', 'order_id': None}


def coerce_allowed_action(action: dict, available_actions: list, fallback_action: dict) -> dict:
    if not isinstance(available_actions, list) or not available_actions:
        return action
    action_type = (action or {}).get('action_type')
    if action_type in available_actions:
        return action
    return fallback_action


def run_task(task_id: str) -> float:
    print(f'\n{"="*50}')
    print(f'Running {task_id}')
    print(f'{"="*50}')

    response = requests.post(f'{ENV_URL}/reset/{task_id}', timeout=30)
    response.raise_for_status()
    obs = response.json()

    total_reward = 0.0
    steps_executed = 0

    for step_num in range(MAX_STEPS):
        current_email = obs.get('current_email') or {}
        if not isinstance(current_email, dict):
            current_email = {}

        ticket = obs.get('ticket') or {}
        if not isinstance(ticket, dict):
            ticket = {}

        traces = obs.get('tool_traces') or []
        if not isinstance(traces, list):
            traces = []

        context = obs.get('context') or {}
        if not isinstance(context, dict):
            context = {}

        deterministic_fallback = choose_action(
            task_id=task_id,
            current_email=current_email,
            ticket=ticket,
            traces=traces,
            context=context,
            step_num=step_num,
            use_gemini_task1=False,
        )
        action = choose_action(
            task_id=task_id,
            current_email=current_email,
            ticket=ticket,
            traces=traces,
            context=context,
            step_num=step_num,
            use_gemini_task1=USE_GEMINI_TASK1,
        )
        action = coerce_allowed_action(action, obs.get('available_actions') or [], deterministic_fallback)

        print(f'  Step {step_num:2d}: {action.get("action_type", "?")} ', end='')

        try:
            step_resp = requests.post(f'{ENV_URL}/step/{task_id}', json=action, timeout=30)
            step_resp.raise_for_status()
        except requests.RequestException:
            step_resp = requests.post(f'{ENV_URL}/step/{task_id}', json=deterministic_fallback, timeout=30)
            step_resp.raise_for_status()

        result = step_resp.json()
        reward = (result.get('reward', {}) or {}).get('value', 0.0) or 0.0
        total_reward += float(reward)
        steps_executed += 1
        done = bool(result.get('done', False))
        obs = result.get('observation', {}) or {}

        print(f'| reward {reward:.3f} | done={done}')
        if done:
            print('  Episode complete.')
            break

    normalized_reward = total_reward
    if task_id == 'task_1' and steps_executed > 0:
        normalized_reward = total_reward / float(steps_executed)
    print(f'  Final reward for {task_id}: {normalized_reward:.4f}')
    return normalized_reward


def main():
    print('Email Triage OpenEnv - Baseline Inference')
    print(f'Model: {MODEL_NAME}')
    print(f'Environment: {ENV_URL}')
    print(f'Use Gemini for Task 1: {USE_GEMINI_TASK1}')

    try:
        health = requests.get(f'{ENV_URL}/', timeout=5)
        health.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f'Cannot reach environment at {ENV_URL}. '
            'Start the API first with: '
            '`python -m uvicorn api.main:app --host 127.0.0.1 --port 8000` '
            'and ensure ENV_URL matches.'
        ) from exc

    scores = {}
    for task in TASKS:
        scores[task] = run_task(task)

    print('\n' + '=' * 50)
    print('FINAL BASELINE SCORES:')
    for task, score in scores.items():
        print(f'  {task}: {score:.4f}')
    avg = sum(scores.values()) / len(scores)
    print(f'  Average: {avg:.4f}')
    print('=' * 50)


if __name__ == '__main__':
    main()
