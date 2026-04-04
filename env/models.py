# env/models.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


CategoryLabel = Literal[
    'Refund Request',
    'Shipping Delay',
    'Account Access',
    'Product Defect',
    'Billing Issue',
    'General Inquiry',
]
PriorityLabel = Literal['Low', 'Normal', 'Urgent']
ActionType = Literal[
    'classify_email',
    'query_policy',
    'draft_response',
    'query_order_db',
    'query_inventory',
    'ship_replacement',
    'issue_refund',
]


class SupportEmail(BaseModel):
    id: str
    sender: str
    subject: str
    body: str


class SupportTicket(BaseModel):
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    message: str
    reported_order_id: Optional[str] = None


class ToolTrace(BaseModel):
    tool_name: str
    request: Dict[str, Any]
    result: Dict[str, Any]


class Observation(BaseModel):
    """What the agent sees at each step."""
    task_id: str
    step_number: int
    inbox: List[SupportEmail] = Field(default_factory=list)
    current_email: Optional[SupportEmail] = None
    ticket: Optional[SupportTicket] = None
    available_actions: List[ActionType]
    tool_traces: List[ToolTrace] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    last_action_error: Optional[str] = None


class Action(BaseModel):
    """Single structured action from the agent."""
    action_type: ActionType

    # Task 1 fields
    category: Optional[CategoryLabel] = None
    priority: Optional[PriorityLabel] = None
    order_id: Optional[str] = None

    # Task 2 fields
    policy_question: Optional[str] = None
    response_text: Optional[str] = None

    # Task 3 fields
    sku: Optional[str] = None
    reason: Optional[str] = None


class Reward(BaseModel):
    value: float
    breakdown: Dict[str, float]
    feedback: str
