# env/data_generator.py
from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List


TASK1_EMAIL_FIXTURES = [
    {
        'id': 'email_001',
        'sender': 'alex.rivera@example.com',
        'subject': 'Where is my package for Order ORD-1001?',
        'body': 'My tracking has not updated in 9 days. Order_ID: ORD-1001. Please help.',
        'ground_truth': {
            'category': 'Shipping Delay',
            'priority': 'Normal',
            'order_id': 'ORD-1001',
        },
    },
    {
        'id': 'email_002',
        'sender': 'chris.lane@example.com',
        'subject': 'Charged twice',
        'body': 'I see two charges on my card after checkout. This is a billing issue.',
        'ground_truth': {
            'category': 'Billing Issue',
            'priority': 'Normal',
            'order_id': None,
        },
    },
    {
        'id': 'email_003',
        'sender': 'mia.chen@example.com',
        'subject': 'Laptop arrived damaged',
        'body': (
            'The screen is cracked right out of the box. Order_ID ORD-2007. '
            'I need this fixed today.'
        ),
        'ground_truth': {
            'category': 'Product Defect',
            'priority': 'Urgent',
            'order_id': 'ORD-2007',
        },
    },
    {
        'id': 'email_004',
        'sender': 'oliver.king@example.com',
        'subject': 'Need help logging in',
        'body': 'Two-factor authentication is failing and I cannot access my account.',
        'ground_truth': {
            'category': 'Account Access',
            'priority': 'Normal',
            'order_id': None,
        },
    },
]


TASK2_POLICY_FIXTURES = [
    {
        'ticket': {
            'ticket_id': 'T2-001',
            'customer_name': 'Sofia Patel',
            'customer_email': 'sofia.patel@example.com',
            'subject': 'Return request after 40 days',
            'message': (
                'I received this item 40 days ago and it does not fit. '
                'Can I still return it for a refund?'
            ),
            'reported_order_id': 'ORD-9012',
        },
        'policy': {
            'name': 'Return Window',
            'window_days': 30,
            'summary': 'Returns are accepted within 30 days of delivery.',
        },
        'days_since_delivery': 40,
        'should_approve_return': False,
    },
    {
        'ticket': {
            'ticket_id': 'T2-002',
            'customer_name': 'Liam Brooks',
            'customer_email': 'liam.brooks@example.com',
            'subject': 'Can I return this?',
            'message': (
                'Package arrived 14 days ago and the color is different than expected. '
                'Can I return it?'
            ),
            'reported_order_id': 'ORD-7781',
        },
        'policy': {
            'name': 'Return Window',
            'window_days': 30,
            'summary': 'Returns are accepted within 30 days of delivery.',
        },
        'days_since_delivery': 14,
        'should_approve_return': True,
    },
]


TASK3_RESOLUTION_FIXTURES = [
    {
        'ticket': {
            'ticket_id': 'T3-001',
            'customer_name': 'Harper Jones',
            'customer_email': 'harper.jones@example.com',
            'subject': 'Defective blender',
            'message': (
                'My blender stopped working after two uses and smells burnt. '
                'Please replace or refund.'
            ),
            'reported_order_id': 'ORD-5001',
        },
        'order_db': {
            'ORD-5001': {'order_exists': True, 'sku': 'SKU-BLEND-01', 'value_usd': 129.0},
        },
        'inventory': {'SKU-BLEND-01': {'in_stock': 5}},
    },
    {
        'ticket': {
            'ticket_id': 'T3-002',
            'customer_name': 'Noah Wright',
            'customer_email': 'noah.wright@example.com',
            'subject': 'Headphones are dead on arrival',
            'message': 'The left side never powered on. I need a replacement fast.',
            'reported_order_id': 'ORD-5002',
        },
        'order_db': {
            'ORD-5002': {'order_exists': True, 'sku': 'SKU-AUDIO-77', 'value_usd': 89.0},
        },
        'inventory': {'SKU-AUDIO-77': {'in_stock': 0}},
    },
    {
        'ticket': {
            'ticket_id': 'T3-003',
            'customer_name': 'Ava Scott',
            'customer_email': 'ava.scott@example.com',
            'subject': 'Defective order cannot be found',
            'message': 'The item is faulty but I may have mistyped the order number.',
            'reported_order_id': 'ORD-9999',
        },
        'order_db': {},
        'inventory': {},
    },
]


ORDER_RE = re.compile(r"\bORD[-_ ]?\d+\b", re.IGNORECASE)
TASK1_DATASET_SAMPLE_SIZE = 4
_TASK1_DATASET_CACHE: list[dict[str, Any]] | None = None
_DATASET_ROW_CACHE: list[dict[str, Any]] | None = None


def _dataset_dir() -> Path:
    return Path(__file__).resolve().parent.parent / 'datasets'


def _extract_order_id(text: str) -> str | None:
    match = ORDER_RE.search(text or '')
    if not match:
        return None
    value = match.group(0).upper().replace('_', '-').replace(' ', '-')
    if value.startswith('ORD') and not value.startswith('ORD-'):
        digits = re.sub(r'[^0-9]', '', value)
        if digits:
            return f'ORD-{digits}'
    return value


def _map_priority(raw_priority: Any) -> str:
    value = str(raw_priority or '').strip().lower()
    if value in {'urgent', 'high', 'critical', 'p1'}:
        return 'Urgent'
    if value in {'low', 'minor', 'p3'}:
        return 'Low'
    return 'Normal'


def _map_category(raw_category: Any, subject: str, body: str) -> str:
    value = str(raw_category or '').strip().lower()
    text = f"{subject} {body}".lower()

    if value in {'billing', 'payment', 'invoice', 'charge'}:
        return 'Billing Issue'
    if value in {'technical_support', 'tech_support', 'account_access', 'account'}:
        return 'Account Access'
    if value in {'shipping', 'delivery', 'shipping_delay'}:
        return 'Shipping Delay'
    if value in {'refund', 'refund_request', 'returns', 'return'}:
        return 'Refund Request'
    if value in {'defect', 'product_defect', 'broken_product'}:
        return 'Product Defect'
    if value in {'complaint'}:
        if any(token in text for token in ['defect', 'broken', 'damaged', 'cracked', 'faulty']):
            return 'Product Defect'
        if any(token in text for token in ['refund', 'return']):
            return 'Refund Request'
        return 'General Inquiry'

    if any(token in text for token in ['invoice', 'payment', 'charged', 'billing', 'card declined', 'double charge']):
        return 'Billing Issue'
    if any(token in text for token in ['login', 'password', 'authentication', 'cannot access', 'account']):
        return 'Account Access'
    if any(token in text for token in ['shipping', 'tracking', 'delayed', 'where is my package', 'delivery']):
        return 'Shipping Delay'
    if any(token in text for token in ['damaged', 'defective', 'broken', 'cracked', 'faulty']):
        return 'Product Defect'
    if 'refund' in text or 'return' in text:
        return 'Refund Request'
    return 'General Inquiry'


def _normalize_task1_row(row: Dict[str, Any], idx: int) -> Dict[str, Any] | None:
    subject = str(row.get('subject') or row.get('title') or '').strip()
    body = str(row.get('body') or row.get('text') or row.get('message') or '').strip()
    sender = str(row.get('sender') or row.get('customer_email') or row.get('email') or 'support-user@example.com').strip()
    if not subject and not body:
        return None

    row_id = str(row.get('id') or row.get('ticket_id') or f'dataset_email_{idx:06d}')
    label = row.get('true_category') or row.get('label') or row.get('category')
    priority = row.get('true_priority') or row.get('priority')
    category = _map_category(label, subject, body)
    mapped_priority = _map_priority(priority)
    order_id = _extract_order_id(f'{subject} {body}')

    return {
        'id': row_id,
        'sender': sender,
        'subject': subject or 'Support request',
        'body': body or 'Customer requested assistance.',
        'ground_truth': {
            'category': category,
            'priority': mapped_priority,
            'order_id': order_id,
        },
    }


def _title_to_name(email_or_sender: str) -> str:
    local = (email_or_sender or 'valued.customer').split('@', 1)[0]
    chunks = [piece for piece in re.split(r'[^a-zA-Z0-9]+', local) if piece]
    if not chunks:
        return 'Valued Customer'
    return ' '.join(piece.capitalize() for piece in chunks[:2])


def _looks_like_return_refund_intent(row: dict[str, Any]) -> bool:
    text = f"{row.get('subject', '')} {row.get('body', '')}".lower()
    raw_category = str(row.get('raw_category') or '').strip().lower()

    strong_raw = {
        'refund',
        'refund_request',
        'return',
        'returns',
    }
    if raw_category in strong_raw:
        return True

    required_terms = ['refund', 'return']
    has_policy_context = any(token in text for token in ['day', 'window', 'delivery', 'eligible'])
    return any(term in text for term in required_terms) and has_policy_context


def _looks_like_defect_intent(row: dict[str, Any]) -> bool:
    text = f"{row.get('subject', '')} {row.get('body', '')}".lower()
    raw_category = str(row.get('raw_category') or '').strip().lower()

    strong_raw = {
        'defect',
        'product_defect',
        'broken_product',
    }
    if raw_category in strong_raw:
        return True

    defect_terms = [
        'defect',
        'defective',
        'broken',
        'damaged',
        'faulty',
        'stopped working',
        'not working',
        'dead on arrival',
    ]
    return any(token in text for token in defect_terms)


def _load_dataset_rows(max_records: int = 8000) -> list[dict[str, Any]]:
    global _DATASET_ROW_CACHE
    if _DATASET_ROW_CACHE is not None:
        return _DATASET_ROW_CACHE

    datasets_dir = _dataset_dir()
    rows: list[dict[str, Any]] = []

    csv_paths = [
        datasets_dir / 'meta_support_subset.csv',
        datasets_dir / 'inbox_vast_100k.csv',
    ]
    for path in csv_paths:
        if not path.exists():
            continue
        try:
            with path.open('r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle)
                for idx, row in enumerate(reader):
                    if len(rows) >= max_records:
                        break
                    subject = str(row.get('subject') or row.get('title') or '').strip()
                    body = str(row.get('body') or row.get('text') or row.get('message') or '').strip()
                    sender = str(row.get('sender') or row.get('customer_email') or row.get('email') or 'support-user@example.com').strip()
                    if not subject and not body:
                        continue

                    label = row.get('true_category') or row.get('label') or row.get('category')
                    priority = row.get('true_priority') or row.get('priority')
                    rows.append({
                        'id': str(row.get('id') or row.get('ticket_id') or f'dataset_row_{idx:06d}'),
                        'sender': sender,
                        'subject': subject or 'Support request',
                        'body': body or 'Customer requested assistance.',
                        'raw_category': str(label or '').strip(),
                        'category': _map_category(label, subject, body),
                        'priority': _map_priority(priority),
                        'order_id': _extract_order_id(f'{subject} {body}') or f'ORD-{8000 + len(rows)}',
                    })
        except Exception:
            continue
        if len(rows) >= max_records:
            break

    seed_json_path = datasets_dir / 'inbox_seed42.json'
    if len(rows) < max_records and seed_json_path.exists():
        try:
            payload = json.loads(seed_json_path.read_text(encoding='utf-8'))
            if isinstance(payload, list):
                for idx, row in enumerate(payload):
                    if len(rows) >= max_records or not isinstance(row, dict):
                        break
                    subject = str(row.get('subject') or '').strip()
                    body = str(row.get('body') or row.get('message') or '').strip()
                    sender = str(row.get('sender') or row.get('customer_email') or row.get('email') or 'support-user@example.com').strip()
                    if not subject and not body:
                        continue

                    label = row.get('true_category') or row.get('label') or row.get('category')
                    priority = row.get('true_priority') or row.get('priority')
                    rows.append({
                        'id': str(row.get('id') or row.get('ticket_id') or f'seed_row_{idx:06d}'),
                        'sender': sender,
                        'subject': subject or 'Support request',
                        'body': body or 'Customer requested assistance.',
                        'raw_category': str(label or '').strip(),
                        'category': _map_category(label, subject, body),
                        'priority': _map_priority(priority),
                        'order_id': _extract_order_id(f'{subject} {body}') or f'ORD-{9000 + len(rows)}',
                    })
        except Exception:
            pass

    _DATASET_ROW_CACHE = rows
    return rows


def _load_task1_dataset_pool(max_records: int = 6000) -> list[dict[str, Any]]:
    global _TASK1_DATASET_CACHE
    if _TASK1_DATASET_CACHE is not None:
        return _TASK1_DATASET_CACHE

    datasets_dir = _dataset_dir()
    pool: list[dict[str, Any]] = []

    csv_paths = [
        datasets_dir / 'meta_support_subset.csv',
        datasets_dir / 'inbox_vast_100k.csv',
    ]
    for path in csv_paths:
        if not path.exists():
            continue
        try:
            with path.open('r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle)
                for idx, row in enumerate(reader):
                    if len(pool) >= max_records:
                        break
                    normalized = _normalize_task1_row(row, idx)
                    if normalized:
                        pool.append(normalized)
        except Exception:
            continue
        if len(pool) >= max_records:
            break

    seed_json_path = datasets_dir / 'inbox_seed42.json'
    if len(pool) < max_records and seed_json_path.exists():
        try:
            payload = json.loads(seed_json_path.read_text(encoding='utf-8'))
            if isinstance(payload, list):
                for idx, row in enumerate(payload):
                    if len(pool) >= max_records:
                        break
                    if not isinstance(row, dict):
                        continue
                    normalized = _normalize_task1_row(row, idx)
                    if normalized:
                        pool.append(normalized)
        except Exception:
            pass

    _TASK1_DATASET_CACHE = pool
    return pool


def _sample(fixtures: List[Dict[str, Any]], seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    return fixtures[rng.randrange(len(fixtures))]


def build_task_1_case(seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    dataset_pool = _load_task1_dataset_pool()

    if dataset_pool:
        sample_size = min(TASK1_DATASET_SAMPLE_SIZE, len(dataset_pool))
        sampled = rng.sample(dataset_pool, k=sample_size)
        rng.shuffle(sampled)

        if sample_size < TASK1_DATASET_SAMPLE_SIZE:
            fixtures = TASK1_EMAIL_FIXTURES[:]
            rng.shuffle(fixtures)
            sampled.extend(fixtures[: TASK1_DATASET_SAMPLE_SIZE - sample_size])
        return {'emails': sampled}

    shuffled = TASK1_EMAIL_FIXTURES[:]
    rng.shuffle(shuffled)
    return {'emails': shuffled[:TASK1_DATASET_SAMPLE_SIZE]}


def build_task_2_case(seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    rows = _load_dataset_rows()

    if rows:
        candidates = [
            row for row in rows
            if row.get('category') == 'Refund Request' and _looks_like_return_refund_intent(row)
        ]
        if not candidates:
            candidates = [row for row in rows if _looks_like_return_refund_intent(row)]
        picked = rng.choice(candidates or rows)

        window_days = 30
        days_since_delivery = rng.randint(7, 55)
        should_approve = days_since_delivery <= window_days
        customer_name = _title_to_name(picked.get('sender', 'valued.customer@example.com'))
        ticket_id = f"T2-{str(picked.get('id', '0000'))[-4:]}"

        base_subject = picked.get('subject', 'Return request').strip()
        if not any(token in base_subject.lower() for token in ['return', 'refund']):
            subject = f'Return request: {base_subject}'
        else:
            subject = base_subject

        base_message = picked.get('body', '').strip()
        if not base_message:
            base_message = 'I need help with a return request.'
        if not any(token in base_message.lower() for token in ['return', 'refund']):
            base_message = (
                f'{base_message} I want to return this item and request a refund if it is still eligible.'
            )

        message = base_message
        if 'day' not in message.lower():
            message = f"{message} It has been {days_since_delivery} days since delivery."

        return {
            'ticket': {
                'ticket_id': ticket_id,
                'customer_name': customer_name,
                'customer_email': picked.get('sender', 'customer@example.com'),
                'subject': subject,
                'message': message,
                'reported_order_id': picked.get('order_id'),
            },
            'policy': {
                'name': 'Return Window',
                'window_days': window_days,
                'summary': 'Returns are accepted within 30 days of delivery.',
            },
            'days_since_delivery': days_since_delivery,
            'should_approve_return': should_approve,
        }

    return _sample(TASK2_POLICY_FIXTURES, seed)


def build_task_3_case(seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    rows = _load_dataset_rows()

    if rows:
        defect_rows = [
            row for row in rows
            if row.get('category') == 'Product Defect' and _looks_like_defect_intent(row)
        ]
        if not defect_rows:
            defect_rows = [row for row in rows if _looks_like_defect_intent(row)]
        picked = rng.choice(defect_rows or rows)
        order_id = picked.get('order_id') or f'ORD-{10000 + seed}'
        customer_name = _title_to_name(picked.get('sender', 'valued.customer@example.com'))

        sku = f"SKU-{abs(hash(order_id)) % 10000:04d}"
        scenario = seed % 3

        if scenario == 0:
            order_db = {order_id: {'order_exists': True, 'sku': sku, 'value_usd': round(rng.uniform(39, 219), 2)}}
            inventory = {sku: {'in_stock': rng.randint(1, 8)}}
        elif scenario == 1:
            order_db = {order_id: {'order_exists': True, 'sku': sku, 'value_usd': round(rng.uniform(39, 219), 2)}}
            inventory = {sku: {'in_stock': 0}}
        else:
            order_db = {}
            inventory = {}

        message = picked.get('body', '').strip()
        if not any(token in message.lower() for token in ['defect', 'broken', 'damaged', 'faulty', 'not working']):
            message = f"{message} The item appears defective and not working correctly.".strip()

        return {
            'ticket': {
                'ticket_id': f"T3-{str(picked.get('id', '0000'))[-4:]}",
                'customer_name': customer_name,
                'customer_email': picked.get('sender', 'customer@example.com'),
                'subject': picked.get('subject', 'Defective product received'),
                'message': message,
                'reported_order_id': order_id,
            },
            'order_db': order_db,
            'inventory': inventory,
        }

    return _sample(TASK3_RESOLUTION_FIXTURES, seed)
