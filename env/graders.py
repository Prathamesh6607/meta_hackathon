# env/graders.py


def grade_classification(predicted: str, true_category: str) -> float:
    """
    Task 1 grader (easy).
    Full credit for exact match. Partial credit for related categories.
    """
    if predicted == true_category:
        return 1.0

    # Partial credit for understandable mistakes
    RELATED = {
        'billing':           ['account'],
        'technical_support': ['account'],
        'complaint':         ['billing'],
        'spam':              [],
    }
    if predicted in RELATED.get(true_category, []):
        return 0.3

    return 0.0


def grade_reply(reply_text: str, email_body: str, required_elements: list) -> float:
    """
    Task 2 grader (medium).
    Scores on: required elements addressed, appropriate length, professionalism.
    """
    if not reply_text or len(reply_text.strip()) < 10:
        return 0.0

    score = 0.0

    # 40% of score: required elements addressed
    addressed = sum(
        1 for elem in required_elements
        if elem.lower() in reply_text.lower()
    )
    score += 0.4 * (addressed / max(len(required_elements), 1))

    # 30% of score: appropriate length
    word_count = len(reply_text.split())
    if 20 <= word_count <= 200:
        score += 0.3
    elif word_count > 5:
        score += 0.1

    # 30% of score: professionalism
    caps_ratio = sum(1 for c in reply_text if c.isupper()) / max(len(reply_text), 1)
    exclamation_count = reply_text.count('!')
    if caps_ratio < 0.3 and exclamation_count < 3:
        score += 0.3
    elif caps_ratio < 0.5:
        score += 0.15

    return min(score, 1.0)


def grade_full_triage(actions_taken: list, inbox: list) -> float:
    """
    Task 3 grader (hard).
    Scores the full workflow across all emails.
    Penalises false escalations.
    """
    score = 0.0
    total_emails = len(inbox)

    correct_classifications = 0
    appropriate_escalations = 0
    false_escalations = 0
    high_priority_emails = [e for e in inbox if e.get('true_priority') == 'high']

    for email, action in zip(inbox, actions_taken):
        action_type = action.get('action_type', '')

        if action_type == 'classify':
            if action.get('classification') == email.get('true_category'):
                correct_classifications += 1

        if action_type == 'escalate':
            if email.get('true_priority') == 'high':
                appropriate_escalations += 1
            else:
                false_escalations += 1

    # 50% weight: classification accuracy
    score += 0.5 * (correct_classifications / max(total_emails, 1))

    # 30% weight: correctly escalating high-priority emails
    score += 0.3 * (appropriate_escalations / max(len(high_priority_emails), 1))

    # 20% weight: completion bonus
    score += 0.2

    # Penalty for false escalations
    score -= 0.05 * false_escalations

    return max(0.0, min(score, 1.0))