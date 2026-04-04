# env/tasks.py
# Task definitions and configurations

TASKS = {
    'task_1': {
        'name': 'Email Triage',
        'difficulty': 'easy',
        'description': (
            'Categorize incoming email issues, assign priority, and extract '
            'Order_ID when present.'
        ),
        'max_steps': 8,
        'allowed_actions': ['classify_email'],
        'grader': 'grade_task_1_email',
    },
    'task_2': {
        'name': 'Policy-Based Support Response',
        'difficulty': 'medium',
        'description': (
            'Use query_policy before drafting an answer and apply the '
            'return-window rule correctly.'
        ),
        'max_steps': 4,
        'allowed_actions': ['query_policy', 'draft_response'],
        'grader': 'grade_task_2',
    },
    'task_3': {
        'name': 'Multi-System Resolution',
        'difficulty': 'hard',
        'description': (
            'Resolve a defective-item ticket by querying order DB and inventory, '
            'then taking the correct final action.'
        ),
        'max_steps': 6,
        'allowed_actions': [
            'query_order_db',
            'query_inventory',
            'ship_replacement',
            'issue_refund',
        ],
        'grader': 'grade_task_3',
    },
}
