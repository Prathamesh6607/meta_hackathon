from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests

TOKEN_RE = re.compile(r"[a-z0-9]+")
CATEGORY_OPTIONS = [
    'Refund Request',
    'Shipping Delay',
    'Account Access',
    'Product Defect',
    'Billing Issue',
    'General Inquiry',
]
PRIORITY_OPTIONS = ['Low', 'Normal', 'Urgent']


@dataclass(frozen=True)
class Task1Decision:
    action: Dict[str, Any]
    source: str
    confidence: float


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or '').lower())


def build_email_text(current_email: dict) -> str:
    subject = current_email.get('subject') or ''
    body = current_email.get('body') or ''
    return f'{subject} {body}'.strip()


def extract_order_id(text: str) -> Optional[str]:
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


def heuristic_task_1_action(current_email: dict) -> dict:
    text = build_email_text(current_email).lower()

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

    order_id = extract_order_id(build_email_text(current_email))
    return {'action_type': 'classify_email', 'category': category, 'priority': priority, 'order_id': order_id}


def parse_action(text: str) -> dict:
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {'action_type': 'classify_email', 'category': 'General Inquiry', 'priority': 'Low', 'order_id': None}


def sanitize_task_1_action(candidate: dict, current_email: dict) -> dict:
    heuristic = heuristic_task_1_action(current_email)
    if not isinstance(candidate, dict):
        return heuristic

    category = candidate.get('category')
    if category not in CATEGORY_OPTIONS:
        category = heuristic.get('category')

    priority = candidate.get('priority')
    if priority not in PRIORITY_OPTIONS:
        priority = heuristic.get('priority')

    order_id = candidate.get('order_id') or extract_order_id(build_email_text(current_email))
    return {'action_type': 'classify_email', 'category': category, 'priority': priority, 'order_id': order_id}


def call_gemini_task_1(current_email: dict, api_key: str, model_name: Optional[str] = None) -> dict:
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
        return heuristic_task_1_action(current_email)
    parts = candidates[0].get('content', {}).get('parts', [])
    text = '\n'.join([p.get('text', '') for p in parts if isinstance(p, dict)]).strip()
    return sanitize_task_1_action(parse_action(text), current_email)


class Task1ReinforcementAgent:
    def __init__(
        self,
        policy_path: Optional[Path] = None,
        log_path: Optional[Path] = None,
        learning_rate: float = 0.18,
        fallback_threshold: Optional[float] = None,
    ):
        self.policy_path = policy_path or self._default_policy_path()
        self.log_path = log_path or self._default_log_path()
        self.learning_rate = learning_rate
        self.fallback_threshold = fallback_threshold if fallback_threshold is not None else float(
            os.environ.get('TASK1_FALLBACK_THRESHOLD', '0.62')
        )
        self.policy = self._load_policy()
        self.learning_log = self._load_learning_log()
        self.recommended_model = 'TF-IDF + Logistic Regression'
        self.recommended_model_reason = 'Best fit for short support-ticket text classification with a small label set.'
        self.model_in_use = 'Online linear policy with heuristic features and Gemini fallback'
        self.is_using_recommended_model = False

    @staticmethod
    def _default_policy_path() -> Path:
        return Path(__file__).resolve().parent.parent / 'datasets' / 'task1_agent_policy.json'

    @staticmethod
    def _default_log_path() -> Path:
        return Path(__file__).resolve().parent.parent / 'datasets' / 'task1_agent_log.jsonl'

    @staticmethod
    def _empty_policy() -> Dict[str, Any]:
        return {
            'examples_seen': 0,
            'updates': 0,
            'category_bias': {label: 0.0 for label in CATEGORY_OPTIONS},
            'priority_bias': {label: 0.0 for label in PRIORITY_OPTIONS},
            'category_weights': {label: {} for label in CATEGORY_OPTIONS},
            'priority_weights': {label: {} for label in PRIORITY_OPTIONS},
        }

    def _load_policy(self) -> Dict[str, Any]:
        if not self.policy_path.exists():
            return self._empty_policy()
        try:
            data = json.loads(self.policy_path.read_text(encoding='utf-8'))
        except Exception:
            return self._empty_policy()

        policy = self._empty_policy()
        for key in ['examples_seen', 'updates']:
            policy[key] = int(data.get(key, 0) or 0)
        for key in ['category_bias', 'priority_bias']:
            policy[key].update({str(k): float(v) for k, v in (data.get(key, {}) or {}).items()})
        for kind in ['category_weights', 'priority_weights']:
            for label, token_map in (data.get(kind, {}) or {}).items():
                if label not in policy[kind]:
                    policy[kind][label] = {}
                policy[kind][label].update({str(token): float(weight) for token, weight in (token_map or {}).items()})
        return policy

    def save(self) -> None:
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.policy_path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(self.policy, indent=2, sort_keys=True), encoding='utf-8')
        temp_path.replace(self.policy_path)

    def _load_learning_log(self) -> list[Dict[str, Any]]:
        if not self.log_path.exists():
            return []

        entries: list[Dict[str, Any]] = []
        try:
            with self.log_path.open('r', encoding='utf-8') as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(payload, dict):
                        entries.append(payload)
        except Exception:
            return []
        return entries

    def _append_learning_log(self, entry: Dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.learning_log.append(entry)
        with self.log_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, sort_keys=True) + '\n')

    @staticmethod
    def _heuristic_scores(kind: str, tokens: list[str]) -> Dict[str, float]:
        token_set = set(tokens)
        joined = ' '.join(tokens)
        if kind == 'category':
            scores = {label: 0.0 for label in CATEGORY_OPTIONS}
            if token_set & {'defective', 'damaged', 'cracked', 'broke', 'faulty', 'working', 'broken'}:
                scores['Product Defect'] += 4.0
            if token_set & {'tracking', 'shipment', 'shipping', 'delayed', 'late', 'lost'}:
                scores['Shipping Delay'] += 4.0
            if token_set & {'login', 'password', 'account', 'authentication', '2fa', 'access'}:
                scores['Account Access'] += 4.0
            if token_set & {'charged', 'billing', 'invoice', 'payment', 'card', 'overcharged'}:
                scores['Billing Issue'] += 4.0
            if 'refund' in token_set or 'refund' in joined:
                scores['Refund Request'] += 4.0
            if not any(value > 0 for value in scores.values()):
                scores['General Inquiry'] += 1.0
            return scores

        scores = {label: 0.0 for label in PRIORITY_OPTIONS}
        if token_set & {'urgent', 'asap', 'immediately', 'today', 'lawsuit', 'legal', 'threat'}:
            scores['Urgent'] += 3.5
        elif token_set & {'no', 'rush', 'whenever', 'fyi'}:
            scores['Low'] += 2.5
        else:
            scores['Normal'] += 1.5
        return scores

    def _score_labels(self, tokens: list[str], kind: str) -> Dict[str, float]:
        weights = self.policy[f'{kind}_weights']
        bias = self.policy[f'{kind}_bias']
        scores: Dict[str, float] = {label: float(bias.get(label, 0.0)) for label in bias}
        heuristic = self._heuristic_scores(kind, tokens)
        for label in scores:
            scores[label] += heuristic.get(label, 0.0)
            token_weights = weights.get(label, {})
            for token in tokens:
                scores[label] += float(token_weights.get(token, 0.0))
        return scores

    @staticmethod
    def _pick_label(scores: Dict[str, float]) -> str:
        return max(scores.items(), key=lambda item: (item[1], item[0]))[0]

    @staticmethod
    def _confidence(scores: Dict[str, float]) -> float:
        ranked = sorted(scores.values(), reverse=True)
        if not ranked:
            return 0.0
        top = ranked[0]
        second = ranked[1] if len(ranked) > 1 else 0.0
        margin = max(top - second, 0.0)
        confidence = 0.45 + math.tanh(margin / 3.0) * 0.5
        return round(max(0.0, min(0.99, confidence)), 4)

    def choose_action(
        self,
        current_email: dict,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        allow_gemini_fallback: bool = True,
    ) -> Task1Decision:
        tokens = tokenize(build_email_text(current_email))
        category_scores = self._score_labels(tokens, 'category')
        priority_scores = self._score_labels(tokens, 'priority')
        category = self._pick_label(category_scores)
        priority = self._pick_label(priority_scores)
        confidence = min(self._confidence(category_scores), self._confidence(priority_scores))

        action = {
            'action_type': 'classify_email',
            'category': category,
            'priority': priority,
            'order_id': extract_order_id(build_email_text(current_email)),
        }

        if confidence < self.fallback_threshold:
            if allow_gemini_fallback and api_key:
                try:
                    fallback_action = call_gemini_task_1(current_email=current_email, api_key=api_key, model_name=model_name)
                    return Task1Decision(action=fallback_action, source='gemini', confidence=confidence)
                except Exception:
                    pass
            return Task1Decision(action=heuristic_task_1_action(current_email), source='heuristic', confidence=confidence)

        return Task1Decision(action=action, source='policy', confidence=confidence)

    def observe(self, current_email: dict, action: Dict[str, Any], reward: Dict[str, Any]) -> None:
        if not isinstance(action, dict) or action.get('action_type') != 'classify_email':
            return

        tokens = tokenize(build_email_text(current_email))
        if not tokens:
            return

        breakdown = reward.get('breakdown') or {}
        category_reward = float(breakdown.get('category', 0.0) or 0.0)
        priority_reward = float(breakdown.get('priority', 0.0) or 0.0)
        total_reward = float(reward.get('value', 0.0) or 0.0)

        self.policy['examples_seen'] += 1
        self._update_component('category', action.get('category'), tokens, category_reward, total_reward)
        self._update_component('priority', action.get('priority'), tokens, priority_reward, total_reward)
        self.policy['updates'] += 1
        self.save()

        context = reward.get('context') or {}
        epoch_run = context.get('episode_run', context.get('epoch_run'))
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'epoch_run': epoch_run,
            'step_number': context.get('step_number'),
            'source': reward.get('source') or 'policy',
            'confidence': reward.get('confidence'),
            'recommended_model': self.recommended_model,
            'model_in_use': self.model_in_use,
            'is_using_recommended_model': self.is_using_recommended_model,
            'examples_seen': self.policy['examples_seen'],
            'updates': self.policy['updates'],
            'action': action,
            'reward': {
                'value': reward.get('value', 0.0),
                'breakdown': breakdown,
                'feedback': reward.get('feedback'),
            },
            'email': {
                'subject': current_email.get('subject'),
                'sender': current_email.get('sender'),
                'id': current_email.get('id'),
            },
            'context': context,
        }
        self._append_learning_log(entry)

    def _update_component(
        self,
        kind: str,
        label: Optional[str],
        tokens: Iterable[str],
        component_reward: float,
        total_reward: float,
    ) -> None:
        if label not in self.policy[f'{kind}_weights']:
            return

        signal = 1.0 if component_reward > 0 else -0.45
        scale = self.learning_rate * (0.5 + max(total_reward, 0.0)) * signal
        weight_map = self.policy[f'{kind}_weights'][label]
        bias_map = self.policy[f'{kind}_bias']
        token_list = list(tokens)
        divisor = max(len(token_list), 1)

        for token in token_list:
            weight_map[token] = float(weight_map.get(token, 0.0)) + (scale / divisor)
            if abs(weight_map[token]) < 1e-6:
                weight_map.pop(token, None)

        bias_map[label] = float(bias_map.get(label, 0.0)) + (scale * 0.25)

    def stats(self) -> Dict[str, Any]:
        return {
            'examples_seen': self.policy.get('examples_seen', 0),
            'updates': self.policy.get('updates', 0),
            'log_entries': len(self.learning_log),
            'fallback_threshold': self.fallback_threshold,
            'policy_path': str(self.policy_path),
            'log_path': str(self.log_path),
            'recommended_model': self.recommended_model,
            'recommended_model_reason': self.recommended_model_reason,
            'model_in_use': self.model_in_use,
            'is_using_recommended_model': self.is_using_recommended_model,
            'token_counts': {
                kind: {label: len(weights) for label, weights in self.policy[f'{kind}_weights'].items()}
                for kind in ['category', 'priority']
            },
            'biases': {
                'category': self.policy.get('category_bias', {}),
                'priority': self.policy.get('priority_bias', {}),
            },
        }

    def logs(self, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        entries = list(self.learning_log)
        if limit is not None and limit > 0:
            return entries[-limit:]
        return entries