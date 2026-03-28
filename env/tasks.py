# env/tasks.py
# Task definitions and configurations

TASKS = {
    'task_1': {
        'name': 'Email Classification',
        'difficulty': 'easy',
        'description': 'Classify each email into the correct category',
        'max_steps': 10,
        'grader': 'grade_classification'
    },
    'task_2': {
        'name': 'Reply Drafting',
        'difficulty': 'medium',
        'description': 'Draft professional replies that address key concerns',
        'max_steps': 15,
        'grader': 'grade_reply'
    },
    'task_3': {
        'name': 'Full Inbox Triage',
        'difficulty': 'hard',
        'description': 'Classify, escalate, and route 10 emails correctly',
        'max_steps': 25,
        'grader': 'grade_full_triage'
    }
}