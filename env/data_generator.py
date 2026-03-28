# env/data_generator.py
from faker import Faker
import random

fake = Faker()

CATEGORIES = ['billing', 'technical_support', 'account',
              'spam', 'complaint', 'feature_request']


def generate_billing_email():
    return {
        'subject': f'Invoice #{fake.random_number(digits=5)} - payment failed',
        'body': (f'Hi, my card ending {fake.credit_card_number()[-4:]} was declined. '
                 f'My order reference is {fake.uuid4()[:8].upper()}. Please help urgently.'),
        'sender': fake.email(),
        'true_category': 'billing',
        'true_priority': 'high'
    }


def generate_spam_email():
    return {
        'subject': fake.catch_phrase() + ' - LIMITED OFFER!!!',
        'body': 'Click here NOW to claim your prize! ' + fake.url(),
        'sender': fake.free_email(),
        'true_category': 'spam',
        'true_priority': 'low'
    }


def generate_support_email():
    return {
        'subject': 'Cannot login to my account',
        'body': (f'Hello, I have been trying to login since {fake.date()} '
                 f'and keep getting error 403. My username is {fake.user_name()}.'),
        'sender': fake.email(),
        'true_category': 'technical_support',
        'true_priority': 'medium'
    }


def generate_complaint_email():
    return {
        'subject': f'Terrible experience with your product',
        'body': (f'I purchased {fake.catch_phrase()} on {fake.date()} and it broke. '
                 f'I demand a full refund of {fake.pricetag()}.'),
        'sender': fake.email(),
        'true_category': 'complaint',
        'true_priority': 'high'
    }


EMAIL_GENERATORS = {
    'billing':           generate_billing_email,
    'spam':              generate_spam_email,
    'technical_support': generate_support_email,
    'complaint':         generate_complaint_email,
}


def generate_inbox(size=10, seed=42):
    """Generate a deterministic inbox. Same seed = same emails every time."""
    random.seed(seed)
    Faker.seed(seed)
    inbox = []
    for i in range(size):
        category = random.choice(list(EMAIL_GENERATORS.keys()))
        email_data = EMAIL_GENERATORS[category]()
        email_data['id'] = f'email_{i:03d}'
        inbox.append(email_data)
    return inbox