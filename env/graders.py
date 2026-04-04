# env/graders.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _normalize_order_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def grade_task_1_email(
    predicted_category: Optional[str],
    predicted_priority: Optional[str],
    predicted_order_id: Optional[str],
    expected: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    category_score = 0.33 if predicted_category == expected.get('category') else 0.0
    priority_score = 0.33 if predicted_priority == expected.get('priority') else 0.0
    order_score = (
        0.34
        if _normalize_order_id(predicted_order_id)
        == _normalize_order_id(expected.get('order_id'))
        else 0.0
    )
    total = round(category_score + priority_score + order_score, 4)
    return total, {
        'category': round(category_score, 2),
        'priority': round(priority_score, 2),
        'order_id': round(order_score, 2),
    }


def grade_task_2(
    queried_policy_first: bool,
    drafted_response: Optional[str],
    should_approve_return: bool,
) -> Tuple[float, Dict[str, float], str]:
    score = 0.0
    breakdown = {'used_query_policy': 0.0, 'correct_policy_outcome': 0.0}

    if queried_policy_first:
        score += 0.5
        breakdown['used_query_policy'] = 0.5

    response = (drafted_response or '').lower()
    mentions_30_days = '30 day' in response or '30-day' in response
    has_decline = any(word in response for word in ['declined', 'cannot', "can't", 'outside'])
    has_approve = any(word in response for word in ['approved', 'eligible', 'can return', 'within'])

    correct_outcome = (
        (should_approve_return and has_approve and mentions_30_days)
        or ((not should_approve_return) and has_decline and mentions_30_days)
    )
    if correct_outcome:
        score += 0.5
        breakdown['correct_policy_outcome'] = 0.5

    feedback = (
        'Return should be approved within 30 days.'
        if should_approve_return
        else 'Return should be declined outside the 30-day window.'
    )
    return round(score, 4), breakdown, feedback


def grade_task_3(
    queried_order_db: bool,
    queried_inventory: bool,
    final_action: Optional[str],
    order_exists: bool,
    inventory_available: bool,
) -> Tuple[float, Dict[str, float], str]:
    # Hard fail overrides.
    if inventory_available and final_action == 'issue_refund':
        return 0.0, {'query_order_db': 0.0, 'query_inventory': 0.0, 'final_action': 0.0}, (
            'Fail condition: refund issued while inventory was available.'
        )
    if (not order_exists) and final_action == 'ship_replacement':
        return 0.0, {'query_order_db': 0.0, 'query_inventory': 0.0, 'final_action': 0.0}, (
            "Fail condition: replacement shipped for an order that doesn't exist."
        )

    expected_final_action = 'issue_refund'
    if order_exists and inventory_available:
        expected_final_action = 'ship_replacement'

    score = 0.0
    breakdown = {'query_order_db': 0.0, 'query_inventory': 0.0, 'final_action': 0.0}
    if queried_order_db:
        score += 0.2
        breakdown['query_order_db'] = 0.2
    if queried_inventory:
        score += 0.2
        breakdown['query_inventory'] = 0.2
    if final_action == expected_final_action:
        score += 0.6
        breakdown['final_action'] = 0.6

    feedback = f'Expected final action: {expected_final_action}.'
    return round(score, 4), breakdown, feedback
