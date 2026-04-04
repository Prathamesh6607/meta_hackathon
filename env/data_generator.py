# env/data_generator.py
from __future__ import annotations

import random
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


def _sample(fixtures: List[Dict[str, Any]], seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    return fixtures[rng.randrange(len(fixtures))]


def build_task_1_case(seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    shuffled = TASK1_EMAIL_FIXTURES[:]
    rng.shuffle(shuffled)
    return {'emails': shuffled}


def build_task_2_case(seed: int) -> Dict[str, Any]:
    return _sample(TASK2_POLICY_FIXTURES, seed)


def build_task_3_case(seed: int) -> Dict[str, Any]:
    return _sample(TASK3_RESOLUTION_FIXTURES, seed)
