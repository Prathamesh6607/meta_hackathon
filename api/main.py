# api/main.py
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import re
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
from env.environment import EmailTriageEnv
from env.models import Action
from env.rl_agent import Task1ReinforcementAgent
from env.support_kb import SupportKnowledgeBase
from env.tasks import TASKS

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
TASK1_AGENT = Task1ReinforcementAgent()
TRAINING_LOG_PATH = BASE_DIR / 'datasets' / 'epoch_training_log.jsonl'

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
HF_EMAIL_CLASSIFIER_SPACE_URL = os.environ.get(
    'HF_EMAIL_CLASSIFIER_SPACE_URL',
    'https://gayathrisoorya-email-classification-new.hf.space',
).rstrip('/')


class AutoStepRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    use_api: bool = False


class SupportSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class TrainingRunRequest(BaseModel):
    epochs: int = 1
    use_api: bool = False


class PipelineRunRequest(BaseModel):
    use_api: bool = False


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


def _post_to_hf_space(payload: dict) -> Any:
    endpoints = [
        ('/classify', payload),
        ('/predict', payload),
        ('/api/predict', {'data': [payload]}),
        ('/run/predict', {'data': [payload]}),
    ]
    for endpoint, body in endpoints:
        url = f'{HF_EMAIL_CLASSIFIER_SPACE_URL}{endpoint}'
        try:
            response = requests.post(url, json=body, timeout=20)
            if response.status_code >= 400:
                continue
            data = response.json()
            if data is not None:
                return data
        except Exception:
            continue
    return None


def _coerce_hf_payload_to_dict(payload: Any) -> dict:
    if isinstance(payload, dict):
        return payload

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
            if isinstance(item, str):
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    continue

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {'text': payload}

    return {}


def _classify_email_via_hf_space(current_email: dict) -> Optional[dict]:
    payload = {
        'mode': 'classify_email',
        'subject': current_email.get('subject', ''),
        'body': current_email.get('body', ''),
        'text': f"{current_email.get('subject', '')}\n{current_email.get('body', '')}".strip(),
    }
    raw = _post_to_hf_space(payload)
    if raw is None:
        return None

    if isinstance(raw, dict) and 'data' in raw:
        candidate = _coerce_hf_payload_to_dict(raw.get('data'))
    else:
        candidate = _coerce_hf_payload_to_dict(raw)

    if not candidate:
        return None

    normalized = {
        'action_type': 'classify_email',
        'category': candidate.get('category') or candidate.get('label'),
        'priority': candidate.get('priority'),
        'order_id': candidate.get('order_id') or _extract_order_id(payload['text']),
    }
    return _sanitize_task_1_action(normalized, current_email)


def _generate_response_via_hf_space(ticket: dict, should_approve: bool, window_days: int) -> Optional[str]:
    payload = {
        'mode': 'generate_response',
        'subject': ticket.get('subject', ''),
        'message': ticket.get('message', ''),
        'should_approve': should_approve,
        'window_days': window_days,
    }
    raw = _post_to_hf_space(payload)
    if raw is None:
        return None

    if isinstance(raw, dict) and 'data' in raw:
        candidate = _coerce_hf_payload_to_dict(raw.get('data'))
    else:
        candidate = _coerce_hf_payload_to_dict(raw)

    response_text = str(
        candidate.get('response_text')
        or candidate.get('response')
        or candidate.get('text')
        or ''
    ).strip()
    return response_text or None


def _build_policy_safe_response(
    should_approve: bool,
    window_days: int,
    external_text: Optional[str] = None,
) -> str:
    if should_approve:
        base = (
            f'Thanks for contacting support. Your return is approved under our {window_days}-day return policy. '
            'Please share your preferred return method so we can complete the request.'
        )
    else:
        base = (
            f'Thanks for contacting support. Your return is declined because it is outside our {window_days}-day return policy. '
            'We can still help with troubleshooting or warranty options.'
        )

    if not external_text:
        return base

    cleaned = ' '.join(str(external_text).replace('\n', ' ').split())
    lowered = cleaned.lower()
    mentions_window = str(window_days) in lowered and 'day' in lowered
    has_approve = any(word in lowered for word in ['approved', 'eligible', 'can return', 'within'])
    has_decline = any(word in lowered for word in ['declined', 'cannot', "can't", 'outside'])

    if should_approve and not (mentions_window and has_approve):
        return base
    if (not should_approve) and not (mentions_window and has_decline):
        return base

    if len(cleaned) > 500:
        cleaned = cleaned[:500].rsplit(' ', 1)[0].rstrip() + '.'
    return cleaned


def _extract_days_from_text(text: str):
    match = re.search(r'(\d+)\s*day', text or '', re.IGNORECASE)
    if not match:
        return None
    return _as_int(match.group(1), default=None)


def _run_task_episode(task_id: str, use_external_api: bool = False, case_override: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    env = envs[task_id]
    env.reset()
    if case_override is not None:
        env._case = case_override

    obs = env._build_observation().model_dump()
    total_reward = 0.0
    steps = 0
    done = False
    max_loops = int(TASKS[task_id]['max_steps']) + 4
    traces: list[dict[str, Any]] = []

    for _ in range(max_loops):
        if done:
            break
        action_data, source, confidence = _choose_auto_action(task_id, obs, use_external_api=use_external_api)
        action_data = _coerce_allowed_action(action_data, obs.get('available_actions') or [])
        action = Action(**action_data)

        result = env.step(action)
        reward_obj = result['reward'].model_dump()
        obs = result['observation'].model_dump()

        reward_value = float(reward_obj.get('value', 0.0) or 0.0)
        total_reward += reward_value
        done = bool(result.get('done', False))
        steps += 1

        traces.append({
            'step': steps,
            'action': action.model_dump(),
            'reward': reward_obj,
            'source': source,
            'confidence': confidence,
            'done': done,
        })

    score = total_reward / float(steps) if task_id == 'task_1' and steps > 0 else total_reward
    return {
        'task_id': task_id,
        'score': round(float(score), 4),
        'total_reward': round(float(total_reward), 4),
        'steps': steps,
        'done': done,
        'final_observation': obs,
        'trace': traces,
        'case_used': env._case,
    }


def _build_task2_case_from_task1(task1_result: dict[str, Any]) -> dict[str, Any]:
    case = task1_result.get('case_used') or {}
    emails = case.get('emails') or []
    trace = task1_result.get('trace') or []

    selected_email = emails[0] if emails else {}
    selected_action = {'category': 'General Inquiry', 'priority': 'Normal', 'order_id': None}

    if trace:
        for item in trace:
            action = item.get('action') or {}
            if action.get('priority') == 'Urgent':
                selected_action = action
                break
        else:
            selected_action = (trace[-1].get('action') or selected_action)

        chosen_order_id = selected_action.get('order_id')
        for email in emails:
            gt = email.get('ground_truth') or {}
            if chosen_order_id and gt.get('order_id') == chosen_order_id:
                selected_email = email
                break

    order_id = selected_action.get('order_id') or _extract_order_id(
        f"{selected_email.get('subject', '')} {selected_email.get('body', '')}"
    )
    if not order_id:
        order_id = 'ORD-PIPE-2001'

    days_since_delivery = _extract_days_from_text(selected_email.get('body', '') or '')
    if days_since_delivery is None:
        days_since_delivery = 14
    should_approve = bool(days_since_delivery <= 30)

    sender = str(selected_email.get('sender') or 'customer@example.com')
    local = sender.split('@', 1)[0]
    customer_name = ' '.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', local) if part]) or 'Valued Customer'

    triage_category = selected_action.get('category') or 'General Inquiry'
    triage_priority = selected_action.get('priority') or 'Normal'
    ticket_subject = f"Follow-up return request after triage: {triage_category} ({triage_priority})"
    ticket_message = (
        f"Based on triage, this case needs policy validation. Original message: {selected_email.get('body', '')} "
        f"Can I return this item under the 30-day policy? It has been {days_since_delivery} days since delivery."
    ).strip()

    return {
        'ticket': {
            'ticket_id': f"T2-PIPE-{str(selected_email.get('id') or '0001')[-4:]}",
            'customer_name': customer_name,
            'customer_email': sender,
            'subject': ticket_subject,
            'message': ticket_message,
            'reported_order_id': order_id,
        },
        'policy': {
            'name': 'Return Window',
            'window_days': 30,
            'summary': 'Returns are accepted within 30 days of delivery.',
        },
        'days_since_delivery': days_since_delivery,
        'should_approve_return': should_approve,
    }


def _build_task3_case_from_task2(task2_result: dict[str, Any]) -> dict[str, Any]:
    case = task2_result.get('case_used') or {}
    ticket = case.get('ticket') or {}
    order_id = ticket.get('reported_order_id') or 'ORD-PIPE-3001'
    should_approve = bool(case.get('should_approve_return'))

    final_response = ''
    for item in reversed(task2_result.get('trace') or []):
        action = item.get('action') or {}
        if action.get('action_type') == 'draft_response':
            final_response = str(action.get('response_text') or '')
            break

    sku = f"SKU-PIPE-{abs(hash(order_id)) % 10000:04d}"
    if should_approve:
        order_db = {order_id: {'order_exists': True, 'sku': sku, 'value_usd': 129.0}}
        inventory = {sku: {'in_stock': 2}}
    else:
        order_db = {order_id: {'order_exists': True, 'sku': sku, 'value_usd': 129.0}}
        inventory = {sku: {'in_stock': 0}}

    message = (
        'Customer now reports a defective item and asks for final resolution. '
        f'Policy response context: {final_response}'
    ).strip()

    return {
        'ticket': {
            'ticket_id': f"T3-PIPE-{str(ticket.get('ticket_id') or '0001')[-4:]}",
            'customer_name': ticket.get('customer_name') or 'Valued Customer',
            'customer_email': ticket.get('customer_email') or 'customer@example.com',
            'subject': 'Defective item escalation after policy decision',
            'message': message,
            'reported_order_id': order_id,
        },
        'order_db': order_db,
        'inventory': inventory,
    }


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


def _choose_task_2_action(ticket: dict, traces: list, context: dict, use_external_api: bool = False) -> dict:
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
        should_approve = True
    else:
        should_approve = False

    if use_external_api:
        external_text = _generate_response_via_hf_space(ticket, should_approve=should_approve, window_days=window_days)
        if external_text:
            safe_response = _build_policy_safe_response(
                should_approve=should_approve,
                window_days=window_days,
                external_text=external_text,
            )
            return {'action_type': 'draft_response', 'response_text': safe_response}

    fallback_response_text = _build_policy_safe_response(
        should_approve=should_approve,
        window_days=window_days,
        external_text=None,
    )
    return {'action_type': 'draft_response', 'response_text': fallback_response_text}


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


def _load_training_logs(limit: int = 100) -> list[dict[str, Any]]:
    if not TRAINING_LOG_PATH.exists():
        return []

    entries: list[dict[str, Any]] = []
    try:
        with TRAINING_LOG_PATH.open('r', encoding='utf-8') as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except Exception:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except Exception:
        return []

    if limit <= 0:
        return entries
    return entries[-limit:]


def _append_training_log(entry: dict[str, Any]) -> None:
    TRAINING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRAINING_LOG_PATH.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, sort_keys=True) + '\n')


def _next_epoch_index() -> int:
    history = _load_training_logs(limit=1)
    if not history:
        return 1
    last = history[0]
    return int(last.get('epoch', 0) or 0) + 1


def _choose_auto_action(task_id: str, obs: dict[str, Any], use_external_api: bool = False) -> tuple[dict[str, Any], str, Optional[float]]:
    current_email = obs.get('current_email') or {}
    ticket = obs.get('ticket') or {}
    traces = obs.get('tool_traces') or []
    context = obs.get('context') or {}

    if task_id == 'task_1':
        if use_external_api:
            external_action = _classify_email_via_hf_space(current_email)
            if external_action:
                return external_action, 'hf_space', None
        decision = TASK1_AGENT.choose_action(
            current_email=current_email,
            api_key=None,
            model_name=None,
            allow_external_fallback=False,
        )
        return decision.action, decision.source, decision.confidence

    if task_id == 'task_2':
        return _choose_task_2_action(ticket=ticket, traces=traces, context=context, use_external_api=use_external_api), 'policy', None

    return _choose_task_3_action(ticket=ticket, traces=traces), 'policy', None


def _run_training_episode(task_id: str, use_external_api: bool = False) -> dict[str, Any]:
    env = envs[task_id]
    obs = env.reset().model_dump()

    total_reward = 0.0
    steps = 0
    done = False
    last_action_type = 'none'
    max_loops = int(TASKS[task_id]['max_steps']) + 4

    for _ in range(max_loops):
        if done:
            break

        action_data, source, confidence = _choose_auto_action(task_id, obs, use_external_api=use_external_api)
        action_data = _coerce_allowed_action(action_data, obs.get('available_actions') or [])
        action = Action(**action_data)

        pre_obs = obs
        result = env.step(action)
        reward_obj = result['reward'].model_dump()
        obs = result['observation'].model_dump()

        if task_id == 'task_1':
            reward_payload = dict(reward_obj)
            reward_payload['context'] = pre_obs.get('context') or {}
            reward_payload['source'] = source
            reward_payload['confidence'] = confidence
            TASK1_AGENT.observe(pre_obs.get('current_email') or {}, action.model_dump(), reward_payload)

        reward_value = float(reward_obj.get('value', 0.0) or 0.0)
        total_reward += reward_value
        done = bool(result.get('done', False))
        steps += 1
        last_action_type = action.action_type

    score = total_reward
    if task_id == 'task_1' and steps > 0:
        score = total_reward / float(steps)

    return {
        'score': round(float(score), 4),
        'total_reward': round(float(total_reward), 4),
        'steps': steps,
        'done': done,
        'last_action': last_action_type,
    }


@app.get('/')
def health():
    return {'status': 'ok', 'environment': 'email-triage-env', 'tasks': list(envs.keys())}


@app.get('/ui')
def ui():
    return FileResponse(UI_DIR / 'index.html')


@app.get('/ui/logs')
def ui_logs():
    return FileResponse(UI_DIR / 'logs.html')


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


@app.get('/training/logs')
def training_logs(limit: int = 100):
    if limit <= 0:
        limit = 100
    entries = _load_training_logs(limit=limit)

    best_average = 0.0
    for item in entries:
        try:
            best_average = max(best_average, float(item.get('average_score', 0.0) or 0.0))
        except Exception:
            continue

    return {
        'limit': limit,
        'entries': entries,
        'summary': {
            'epochs': len(entries),
            'best_average_score': round(best_average, 4),
            'latest_epoch': entries[-1].get('epoch') if entries else None,
        },
    }


@app.post('/training/run')
def training_run(request: TrainingRunRequest):
    epochs = max(1, min(int(request.epochs or 1), 200))
    created: list[dict[str, Any]] = []

    epoch_idx = _next_epoch_index()
    task_ids = ['task_1', 'task_2', 'task_3']

    for _ in range(epochs):
        tasks_result: dict[str, Any] = {}
        score_sum = 0.0

        for task_id in task_ids:
            result = _run_training_episode(task_id=task_id, use_external_api=bool(request.use_api))
            tasks_result[task_id] = result
            score_sum += float(result.get('score', 0.0) or 0.0)

        avg_score = round(score_sum / float(len(task_ids)), 4)
        entry = {
            'epoch': epoch_idx,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'use_api': bool(request.use_api),
            'tasks': tasks_result,
            'average_score': avg_score,
        }
        _append_training_log(entry)
        created.append(entry)
        epoch_idx += 1

    return {
        'ran_epochs': epochs,
        'entries': created,
        'latest': created[-1] if created else None,
    }


@app.post('/pipeline/run')
@app.post('/pipeline/run/')
@app.post('/pipeline')
def pipeline_run(request: PipelineRunRequest):
    task1 = _run_task_episode('task_1', use_external_api=bool(request.use_api))
    task2_case = _build_task2_case_from_task1(task1)
    task2 = _run_task_episode('task_2', use_external_api=bool(request.use_api), case_override=task2_case)
    task3_case = _build_task3_case_from_task2(task2)
    task3 = _run_task_episode('task_3', use_external_api=bool(request.use_api), case_override=task3_case)

    avg = round((float(task1.get('score', 0.0)) + float(task2.get('score', 0.0)) + float(task3.get('score', 0.0))) / 3.0, 4)
    return {
        'use_api': bool(request.use_api),
        'pipeline_order': ['task_1', 'task_2', 'task_3'],
        'handoff': {
            'task1_to_task2': task2_case,
            'task2_to_task3': task3_case,
        },
        'results': {
            'task_1': task1,
            'task_2': task2,
            'task_3': task3,
        },
        'average_score': avg,
    }


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
        pre_step_obs = envs[task_id]._build_observation().model_dump()
        result = envs[task_id].step(action)
        obs_dump = result['observation'].model_dump()
        if task_id == 'task_1':
            reward_payload = result['reward'].model_dump()
            reward_payload['context'] = pre_step_obs.get('context') or {}
            reward_payload['source'] = 'manual'
            TASK1_AGENT.observe(pre_step_obs.get('current_email') or {}, action.model_dump(), reward_payload)
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
            decision = None
            if request.use_api:
                external_action = _classify_email_via_hf_space(current_email)
                if external_action:
                    action_data = external_action
                else:
                    decision = TASK1_AGENT.choose_action(
                        current_email=current_email,
                        api_key=None,
                        model_name=request.model_name,
                        allow_external_fallback=False,
                    )
                    action_data = decision.action
            else:
                decision = TASK1_AGENT.choose_action(
                    current_email=current_email,
                    api_key=None,
                    model_name=request.model_name,
                    allow_external_fallback=False,
                )
                action_data = decision.action
        elif task_id == 'task_2':
            action_data = _choose_task_2_action(
                ticket=ticket,
                traces=traces,
                context=context,
                use_external_api=request.use_api,
            )
        else:
            action_data = _choose_task_3_action(ticket=ticket, traces=traces)

        action_data = _coerce_allowed_action(action_data, obs.get('available_actions') or [])
        action = Action(**action_data)
        result = env.step(action)
        obs_dump = result['observation'].model_dump()
        if task_id == 'task_1':
            reward_payload = result['reward'].model_dump()
            reward_payload['context'] = obs.get('context') or {}
            reward_payload['source'] = decision.source if decision else ('hf_space' if request.use_api else 'policy')
            reward_payload['confidence'] = decision.confidence if decision else None
            TASK1_AGENT.observe(current_email, action.model_dump(), reward_payload)
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


@app.get('/agent/task_1')
def agent_task_1_state():
    stats = TASK1_AGENT.stats()
    stats['epoch_run'] = envs['task_1'].state().get('episode_run', 0)
    return stats


@app.get('/agent/task_1/logs')
def agent_task_1_logs(limit: int = 100):
    if limit <= 0:
        limit = 100
    return {
        'limit': limit,
        'entries': TASK1_AGENT.logs(limit=limit),
    }


@app.get('/state/{task_id}')
def state(task_id: str):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    return envs[task_id].state()
