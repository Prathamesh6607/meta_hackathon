# api/main.py
from pathlib import Path
import json
import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
from env.environment import EmailTriageEnv
from env.models import Action
from env.support_kb import SupportKnowledgeBase

app = FastAPI(
    title='Tier-2 Support OpenEnv',
    version='1.0.0',
    description='Tier-2 customer support benchmark for policy and multi-system workflows'
)

# One environment instance per task
envs = {
    'task_1': EmailTriageEnv(task_id='task_1'),
    'task_2': EmailTriageEnv(task_id='task_2'),
    'task_3': EmailTriageEnv(task_id='task_3'),
}

BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / 'ui'
SUPPORT_KB = SupportKnowledgeBase.from_datasets(BASE_DIR / 'datasets')

app.mount('/ui-assets', StaticFiles(directory=UI_DIR), name='ui-assets')

CATEGORY_OPTIONS = [
    'Refund Request',
    'Shipping Delay',
    'Account Access',
    'Product Defect',
    'Billing Issue',
    'General Inquiry',
]

PRIORITY_OPTIONS = ['Low', 'Normal', 'Urgent']


class AutoStepRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    use_api: bool = False


class SupportSearchRequest(BaseModel):
    query: str
    top_k: int = 5


def _as_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _extract_order_id(text: str):
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


def _parse_action(text: str) -> dict:
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {'action_type': 'classify_email', 'category': 'General Inquiry', 'priority': 'Low', 'order_id': None}


def _latest_tool_trace(traces: list, tool_name: str) -> dict:
    for item in reversed(traces):
        if isinstance(item, dict) and item.get('tool_name') == tool_name:
            return item
    return {}


def _choose_task_1_action_heuristic(current_email: dict) -> dict:
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

    order_id = _extract_order_id(f'{subject} {body}')
    return {'action_type': 'classify_email', 'category': category, 'priority': priority, 'order_id': order_id}


def _sanitize_task_1_action(candidate: dict, current_email: dict) -> dict:
    heuristic = _choose_task_1_action_heuristic(current_email)
    if not isinstance(candidate, dict):
        return heuristic
    category = candidate.get('category')
    if category not in CATEGORY_OPTIONS:
        category = heuristic.get('category')
    priority = candidate.get('priority')
    if priority not in PRIORITY_OPTIONS:
        priority = heuristic.get('priority')
    order_id = candidate.get('order_id') or _extract_order_id(
        f'{current_email.get("subject", "")} {current_email.get("body", "")}'
    )
    return {'action_type': 'classify_email', 'category': category, 'priority': priority, 'order_id': order_id}


def _call_gemini_for_task_1(current_email: dict, api_key: str, model_name: Optional[str]) -> dict:
    model = model_name or os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
    base_url = os.environ.get('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com/v1beta')
    prompt = (
        'Extract support triage fields and return JSON only.\n'
        f'Allowed categories: {CATEGORY_OPTIONS}\n'
        f'Allowed priorities: {PRIORITY_OPTIONS}\n'
        'Return keys: action_type, category, priority, order_id.\n'
        'action_type must be "classify_email". order_id should be null when absent.\n'
        f'Subject: {current_email.get("subject", "")}\n'
        f'Body: {current_email.get("body", "")}\n'
    )

    response = requests.post(
        f'{base_url}/models/{model}:generateContent',
        params={'key': api_key},
        json={
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.0, 'maxOutputTokens': 512},
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get('candidates', [])
    if not candidates:
        return _choose_task_1_action_heuristic(current_email)
    parts = candidates[0].get('content', {}).get('parts', [])
    text = '\n'.join([p.get('text', '') for p in parts if isinstance(p, dict)]).strip()
    return _sanitize_task_1_action(_parse_action(text), current_email)


def _extract_days_from_text(text: str):
    match = re.search(r'(\d+)\s*day', text or '', re.IGNORECASE)
    if not match:
        return None
    return _as_int(match.group(1), default=None)


def _infer_order_exists(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    for key in ['order_exists', 'exists', 'found', 'is_valid', 'valid']:
        if key in result:
            return bool(result.get(key))
    return bool(result.get('order_id') or result.get('sku'))


def _infer_in_stock(result: dict) -> int:
    if not isinstance(result, dict):
        return 0
    for key in ['in_stock', 'stock', 'available_qty', 'quantity', 'qty']:
        if key in result:
            return _as_int(result.get(key), default=0)
    if isinstance(result.get('available'), bool):
        return 1 if result.get('available') else 0
    return 0


def _choose_task_2_action(ticket: dict, traces: list, context: dict) -> dict:
    policy_trace = _latest_tool_trace(traces, 'query_policy')
    if not policy_trace:
        return {
            'action_type': 'query_policy',
            'policy_question': ticket.get('message') or 'What is the return window policy?',
        }

    result = policy_trace.get('result', {}) or {}
    window_days = _as_int(result.get('window_days', result.get('return_window_days', 30)), default=30)
    days_since_delivery = _as_int(context.get('days_since_delivery'), default=-1)
    if days_since_delivery < 0:
        parsed_days = _extract_days_from_text(ticket.get('message', ''))
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


def _choose_task_3_action(ticket: dict, traces: list) -> dict:
    order_id = ticket.get('reported_order_id')
    order_trace = _latest_tool_trace(traces, 'query_order_db')
    if not order_trace:
        return {'action_type': 'query_order_db', 'order_id': order_id}

    order_result = order_trace.get('result', {}) or {}
    order_exists = _infer_order_exists(order_result)
    sku = order_result.get('sku')

    if not order_exists:
        return {'action_type': 'issue_refund', 'order_id': order_id, 'reason': 'order_not_found_defective_claim'}

    inventory_trace = _latest_tool_trace(traces, 'query_inventory')
    if not inventory_trace:
        if sku:
            return {'action_type': 'query_inventory', 'sku': sku}
        return {'action_type': 'issue_refund', 'order_id': order_id, 'reason': 'missing_sku_for_replacement'}

    in_stock = _infer_in_stock(inventory_trace.get('result', {}) or {})
    if in_stock > 0:
        return {'action_type': 'ship_replacement', 'order_id': order_id, 'reason': 'defective_item'}
    return {'action_type': 'issue_refund', 'order_id': order_id, 'reason': 'replacement_out_of_stock'}


def _coerce_allowed_action(action: dict, available_actions: list) -> dict:
    if not isinstance(available_actions, list) or not available_actions:
        return action
    action_type = (action or {}).get('action_type')
    if action_type in available_actions:
        return action
    return {'action_type': available_actions[0]}


def _build_support_recommendation(task_id: str, obs: dict, action: Action) -> dict:
    if task_id == 'task_1':
        query = ' '.join([
            str((obs.get('current_email') or {}).get('subject', '')),
            str((obs.get('current_email') or {}).get('body', '')),
            str(action.category or ''),
            str(action.priority or ''),
        ]).strip()
    elif task_id == 'task_2':
        query = ' '.join([
            str((obs.get('ticket') or {}).get('message', '')),
            str(action.response_text or ''),
        ]).strip()
    else:
        query = ' '.join([
            str((obs.get('ticket') or {}).get('message', '')),
            str((obs.get('ticket') or {}).get('reported_order_id', '')),
            str(action.reason or ''),
        ]).strip()

    return SUPPORT_KB.suggest_response(query=query, task_id=task_id, action=action.model_dump(), context=obs.get('context') or {})


@app.get('/')
def health():
    return {'status': 'ok', 'environment': 'email-triage-env', 'tasks': list(envs.keys())}


@app.get('/ui')
def ui():
    return FileResponse(UI_DIR / 'index.html')


@app.post('/support/search')
def support_search(request: SupportSearchRequest):
    query = (request.query or '').strip()
    if not query:
        raise HTTPException(status_code=400, detail='query is required')
    top_k = request.top_k if request.top_k > 0 else 5
    return {
        'query': query,
        'top_k': top_k,
        'matches': SUPPORT_KB.search(query, top_k=top_k),
    }


@app.get('/support/stats')
def support_stats():
    return SUPPORT_KB.summary()


@app.post('/reset/{task_id}')
def reset(task_id: str):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    obs = envs[task_id].reset()
    return obs.model_dump()


@app.post('/step/{task_id}')
def step(task_id: str, action: Action):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    try:
        result = envs[task_id].step(action)
        obs_dump = result['observation'].model_dump()
        return {
            'observation': obs_dump,
            'reward': result['reward'].model_dump(),
            'done': result['done'],
            'info': result['info'],
            'support_recommendation': _build_support_recommendation(task_id, obs_dump, action),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/auto-step/{task_id}')
def auto_step(task_id: str, request: AutoStepRequest):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')

    env = envs[task_id]

    # Reset lazily so UI can call auto-step as a first action.
    if not getattr(env, '_case', None):
        env.reset()

    if getattr(env, '_done', False):
        raise HTTPException(status_code=400, detail='Episode is done. Call /reset/{task_id} first.')

    try:
        obs = env._build_observation().model_dump()
        current_email = obs.get('current_email') or {}
        ticket = obs.get('ticket') or {}
        traces = obs.get('tool_traces') or []
        context = obs.get('context') or {}

        if task_id == 'task_1':
            if request.use_api and request.api_key:
                try:
                    action_data = _call_gemini_for_task_1(
                        current_email=current_email,
                        api_key=request.api_key,
                        model_name=request.model_name,
                    )
                except Exception:
                    action_data = _choose_task_1_action_heuristic(current_email)
            else:
                action_data = _choose_task_1_action_heuristic(current_email)
        elif task_id == 'task_2':
            action_data = _choose_task_2_action(ticket=ticket, traces=traces, context=context)
        else:
            action_data = _choose_task_3_action(ticket=ticket, traces=traces)

        action_data = _coerce_allowed_action(action_data, obs.get('available_actions') or [])
        action = Action(**action_data)
        result = env.step(action)
        obs_dump = result['observation'].model_dump()
        return {
            'action_used': action.model_dump(),
            'observation': obs_dump,
            'reward': result['reward'].model_dump(),
            'done': result['done'],
            'info': result['info'],
            'support_recommendation': _build_support_recommendation(task_id, obs_dump, action),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get('/state/{task_id}')
def state(task_id: str):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    return envs[task_id].state()
