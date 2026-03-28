# env/models.py
from pydantic import BaseModel
from typing import Optional, List, Literal


class Email(BaseModel):
    """A single email in the inbox."""
    id: str
    subject: str
    body: str
    sender: str
    category: Optional[str] = None      # e.g. billing, support, spam
    priority: Optional[str] = None      # e.g. high, medium, low


class Observation(BaseModel):
    """What the agent sees at each step."""
    task_id: str                         # which of the 3 tasks we are on
    step_number: int                     # how many steps taken so far
    inbox: List[Email]                   # all emails in the inbox
    current_email: Optional[Email]       # the specific email to act on
    context: dict                        # extra info like emails_remaining
    last_action_error: Optional[str] = None  # populated if last action failed


class Action(BaseModel):
    """What the agent can do."""
    action_type: Literal[
        'classify',   # label this email with a category
        'reply',      # draft a reply
        'escalate',   # mark as urgent, flag for human
        'archive',    # remove from active inbox
        'merge'       # combine with a related thread
    ]
    classification: Optional[str] = None      # for classify action
    reply_text: Optional[str] = None           # for reply action
    escalation_reason: Optional[str] = None   # for escalate action


class Reward(BaseModel):
    """The score after an action."""
    value: float          # 0.0 to 1.0 — the actual reward
    breakdown: dict       # e.g. {accuracy: 0.8, tone: 0.6}
    feedback: str         # human-readable explanation of the score