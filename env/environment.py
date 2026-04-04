# env/environment.py
from __future__ import annotations

from typing import Any
from uuid import uuid4

from .data_generator import build_task_1_case, build_task_2_case, build_task_3_case
from .graders import grade_task_1_email, grade_task_2, grade_task_3
from .models import Action, Observation, Reward, SupportEmail, SupportTicket, ToolTrace
from .tasks import TASKS


class EmailTriageEnv:
    """Tier-2 support benchmark environment with 3 graded tasks."""

    def __init__(self, task_id: str = 'task_1', seed: int = 42):
        if task_id not in TASKS:
            raise ValueError(f'Unknown task_id: {task_id}')
        self.task_id = task_id
        self.seed = seed
        self._episode_index = 0
        self._current_step = 0
        self._done = False
        self._total_reward = 0.0
        self._last_error: str | None = None
        self._tool_traces: list[ToolTrace] = []
        self._actions_taken: list[dict[str, Any]] = []
        self._case: dict[str, Any] = {}

        # Task-specific runtime fields.
        self._task1_idx = 0
        self._task1_scores: list[float] = []
        self._queried_policy_first = False
        self._policy_already_queried = False
        self._drafted_response: str | None = None
        self._queried_order_db = False
        self._queried_inventory = False
        self._last_order_lookup: dict[str, Any] | None = None
        self._last_inventory_lookup: dict[str, Any] | None = None
        self._final_action: str | None = None

    @property
    def max_steps(self) -> int:
        return int(TASKS[self.task_id]['max_steps'])

    def reset(self) -> Observation:
        episode_seed = self.seed + self._episode_index
        self._episode_index += 1
        self._current_step = 0
        self._done = False
        self._total_reward = 0.0
        self._last_error = None
        self._tool_traces = []
        self._actions_taken = []

        self._task1_idx = 0
        self._task1_scores = []
        self._queried_policy_first = False
        self._policy_already_queried = False
        self._drafted_response = None
        self._queried_order_db = False
        self._queried_inventory = False
        self._last_order_lookup = None
        self._last_inventory_lookup = None
        self._final_action = None

        if self.task_id == 'task_1':
            self._case = build_task_1_case(seed=episode_seed)
        elif self.task_id == 'task_2':
            self._case = build_task_2_case(seed=episode_seed)
        else:
            self._case = build_task_3_case(seed=episode_seed)

        return self._build_observation()

    def step(self, action: Action) -> dict[str, Any]:
        if self._done:
            raise ValueError('Episode is done. Call reset() first.')

        self._last_error = None
        self._actions_taken.append(action.model_dump())
        reward_value = 0.0
        breakdown: dict[str, float] = {'step_reward': 0.0}
        feedback = 'No-op.'

        if action.action_type not in TASKS[self.task_id]['allowed_actions']:
            self._last_error = (
                f'Action "{action.action_type}" not allowed for {self.task_id}. '
                f'Allowed actions: {TASKS[self.task_id]["allowed_actions"]}.'
            )
            feedback = self._last_error
        elif self.task_id == 'task_1':
            reward_value, breakdown, feedback = self._step_task_1(action)
        elif self.task_id == 'task_2':
            reward_value, breakdown, feedback = self._step_task_2(action)
        else:
            reward_value, breakdown, feedback = self._step_task_3(action)

        self._total_reward += reward_value
        self._current_step += 1
        if self._current_step >= self.max_steps:
            self._done = True

        observation = self._build_observation()
        reward = Reward(value=round(reward_value, 4), breakdown=breakdown, feedback=feedback)
        return {
            'observation': observation,
            'reward': reward,
            'done': self._done,
            'info': {
                'step': self._current_step,
                'total_reward': round(self._total_reward, 4),
                'task_done': self._done,
            },
        }

    def _step_task_1(self, action: Action) -> tuple[float, dict[str, float], str]:
        emails = self._case['emails']
        if self._task1_idx >= len(emails):
            self._done = True
            return 0.0, {'category': 0.0, 'priority': 0.0, 'order_id': 0.0}, 'All emails already triaged.'

        record = emails[self._task1_idx]
        score, breakdown = grade_task_1_email(
            predicted_category=action.category,
            predicted_priority=action.priority,
            predicted_order_id=action.order_id,
            expected=record['ground_truth'],
        )
        self._task1_scores.append(score)
        self._task1_idx += 1
        if self._task1_idx >= len(emails):
            self._done = True
        feedback = (
            f"Email {record['id']} graded. "
            f"Expected category={record['ground_truth']['category']}, "
            f"priority={record['ground_truth']['priority']}, "
            f"order_id={record['ground_truth']['order_id']}."
        )
        return score, breakdown, feedback

    def _step_task_2(self, action: Action) -> tuple[float, dict[str, float], str]:
        if action.action_type == 'query_policy':
            policy = self._case['policy']
            result = {
                'policy_name': policy['name'],
                'window_days': policy['window_days'],
                'summary': policy['summary'],
            }
            self._tool_traces.append(
                ToolTrace(
                    tool_name='query_policy',
                    request={'question': action.policy_question or self._case['ticket']['message']},
                    result=result,
                )
            )
            if self._drafted_response is None:
                self._queried_policy_first = True
            self._policy_already_queried = True
            return 0.0, {'used_query_policy': 0.0, 'correct_policy_outcome': 0.0}, 'Policy returned.'

        # draft_response
        self._drafted_response = action.response_text or ''
        score, breakdown, policy_feedback = grade_task_2(
            queried_policy_first=self._queried_policy_first and self._policy_already_queried,
            drafted_response=self._drafted_response,
            should_approve_return=bool(self._case['should_approve_return']),
        )
        self._done = True
        return score, breakdown, policy_feedback

    def _step_task_3(self, action: Action) -> tuple[float, dict[str, float], str]:
        ticket = self._case['ticket']
        order_id = ticket.get('reported_order_id')

        if action.action_type == 'query_order_db':
            lookup_id = action.order_id or order_id
            result = self._case['order_db'].get(lookup_id)
            payload = {'order_id': lookup_id, 'order_exists': bool(result)}
            if result:
                payload.update(result)
            self._last_order_lookup = payload
            self._queried_order_db = True
            self._tool_traces.append(
                ToolTrace(
                    tool_name='query_order_db',
                    request={'order_id': lookup_id},
                    result=payload,
                )
            )
            return 0.0, {'query_order_db': 0.0, 'query_inventory': 0.0, 'final_action': 0.0}, 'Order lookup completed.'

        if action.action_type == 'query_inventory':
            sku = action.sku
            if not sku and self._last_order_lookup:
                sku = self._last_order_lookup.get('sku')
            if not sku:
                self._last_error = 'No SKU available. Query order DB first or provide sku.'
                return 0.0, {'query_order_db': 0.0, 'query_inventory': 0.0, 'final_action': 0.0}, self._last_error

            inventory_record = self._case['inventory'].get(sku, {'in_stock': 0})
            payload = {'sku': sku, 'in_stock': int(inventory_record.get('in_stock', 0))}
            self._last_inventory_lookup = payload
            self._queried_inventory = True
            self._tool_traces.append(
                ToolTrace(
                    tool_name='query_inventory',
                    request={'sku': sku},
                    result=payload,
                )
            )
            return 0.0, {'query_order_db': 0.0, 'query_inventory': 0.0, 'final_action': 0.0}, 'Inventory lookup completed.'

        # Final action: ship_replacement or issue_refund
        self._final_action = action.action_type
        final_tool_result = {'status': 'executed'}
        if action.action_type == 'ship_replacement':
            final_tool_result['shipment_id'] = f'SHP-{uuid4().hex[:8].upper()}'
        else:
            final_tool_result['refund_id'] = f'RFD-{uuid4().hex[:8].upper()}'
        self._tool_traces.append(
            ToolTrace(
                tool_name=action.action_type,
                request={'order_id': action.order_id or order_id, 'reason': action.reason or 'defective_item'},
                result=final_tool_result,
            )
        )

        hidden_order = self._case['order_db'].get(order_id)
        order_exists = bool(hidden_order and hidden_order.get('order_exists'))
        hidden_sku = hidden_order.get('sku') if hidden_order else None
        inventory_available = bool(
            hidden_sku and self._case['inventory'].get(hidden_sku, {}).get('in_stock', 0) > 0
        )
        score, breakdown, feedback = grade_task_3(
            queried_order_db=self._queried_order_db,
            queried_inventory=self._queried_inventory,
            final_action=self._final_action,
            order_exists=order_exists,
            inventory_available=inventory_available,
        )
        self._done = True
        return score, breakdown, feedback

    def _build_observation(self) -> Observation:
        allowed_actions = TASKS[self.task_id]['allowed_actions']
        context: dict[str, Any] = {
            'task_description': TASKS[self.task_id]['description'],
            'max_steps': self.max_steps,
            'steps_remaining': max(self.max_steps - self._current_step, 0),
            'total_reward_so_far': round(self._total_reward, 4),
        }
        ticket: SupportTicket | None = None
        inbox: list[SupportEmail] = []
        current_email: SupportEmail | None = None

        if self.task_id == 'task_1':
            emails = self._case.get('emails', [])
            inbox = [
                SupportEmail(
                    id=e['id'],
                    sender=e['sender'],
                    subject=e['subject'],
                    body=e['body'],
                )
                for e in emails
            ]
            if emails:
                idx = min(self._task1_idx, len(emails) - 1)
                current = emails[idx]
                current_email = SupportEmail(
                    id=current['id'],
                    sender=current['sender'],
                    subject=current['subject'],
                    body=current['body'],
                )
            context['emails_total'] = len(emails)
            context['emails_processed'] = min(self._task1_idx, len(emails))
            if self._task1_scores:
                context['avg_email_score'] = round(sum(self._task1_scores) / len(self._task1_scores), 4)

        elif self.task_id == 'task_2':
            ticket = SupportTicket(**self._case['ticket'])
            context['days_since_delivery'] = self._case['days_since_delivery']
            context['asked_question'] = 'Can I still return this item?'
            context['queried_policy'] = self._policy_already_queried

        else:
            ticket = SupportTicket(**self._case['ticket'])
            context['issue_type'] = 'defective_item'
            context['queried_order_db'] = self._queried_order_db
            context['queried_inventory'] = self._queried_inventory
            context['final_action_taken'] = self._final_action

        return Observation(
            task_id=self.task_id,
            step_number=self._current_step,
            inbox=inbox,
            current_email=current_email,
            ticket=ticket,
            available_actions=allowed_actions,
            tool_traces=self._tool_traces,
            context=context,
            last_action_error=self._last_error,
        )

    def state(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'done': self._done,
            'step': self._current_step,
            'max_steps': self.max_steps,
            'total_reward': round(self._total_reward, 4),
            'actions_taken': len(self._actions_taken),
            'tool_calls': len(self._tool_traces),
        }
