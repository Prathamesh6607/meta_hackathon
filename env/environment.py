# env/environment.py
from .models import Observation, Action, Reward, Email
from .data_generator import generate_inbox
from .graders import grade_classification, grade_reply, grade_full_triage


class EmailTriageEnv:

    MAX_STEPS = {'task_1': 10, 'task_2': 15, 'task_3': 25}

    def __init__(self, task_id: str = 'task_1', seed: int = 42):
        self.task_id = task_id
        self.seed = seed
        self._inbox = []
        self._current_step = 0
        self._done = False
        self._actions_taken = []
        self._total_reward = 0.0

    def reset(self) -> Observation:
        """Called at the start of every episode. Returns clean initial state."""
        self._inbox = generate_inbox(size=10, seed=self.seed)
        self._current_step = 0
        self._done = False
        self._actions_taken = []
        self._total_reward = 0.0

        # Convert raw dicts to Email models
        email_objects = [Email(**{k: v for k, v in e.items()
                                  if k in Email.model_fields})
                          for e in self._inbox]

        return Observation(
            task_id=self.task_id,
            step_number=0,
            inbox=email_objects[:3],
            current_email=email_objects[0],
            context={'emails_remaining': len(self._inbox)},
        )

    def step(self, action: Action) -> dict:
        """Core method: receives action, returns obs/reward/done/info."""
        if self._done:
            raise ValueError('Episode is done. Call reset() first.')

        self._actions_taken.append(action.model_dump())
        reward_value = 0.0
        feedback = ''
        current_email = self._inbox[self._current_step % len(self._inbox)]

        if self.task_id == 'task_1':
            reward_value = grade_classification(
                action.classification or '',
                current_email.get('true_category', '')
            )
            feedback = (f'Expected: {current_email.get("true_category")}, '
                        f'Got: {action.classification}, Score: {reward_value:.2f}')

        elif self.task_id == 'task_2':
            reward_value = grade_reply(
                action.reply_text or '',
                current_email.get('body', ''),
                required_elements=['apolog', 'help', 'contact', 'resolve']
            )
            feedback = f'Reply quality score: {reward_value:.2f}'

        elif self.task_id == 'task_3':
            if self._current_step >= len(self._inbox) - 1:
                reward_value = grade_full_triage(self._actions_taken, self._inbox)
                feedback = f'Full triage complete. Score: {reward_value:.2f}'
            else:
                reward_value = 0.05  # small step reward to signal progress
                feedback = f'Step {self._current_step} recorded.'

        self._total_reward += reward_value
        self._current_step += 1
        max_steps = self.MAX_STEPS.get(self.task_id, 10)
        self._done = self._current_step >= max_steps

        next_idx = min(self._current_step, len(self._inbox) - 1)
        next_email_raw = self._inbox[next_idx]
        next_email = Email(**{k: v for k, v in next_email_raw.items()
                              if k in Email.model_fields})

        email_objects = [Email(**{k: v for k, v in e.items()
                                  if k in Email.model_fields})
                          for e in self._inbox[:3]]

        observation = Observation(
            task_id=self.task_id,
            step_number=self._current_step,
            inbox=email_objects,
            current_email=next_email,
            context={
                'emails_remaining': max_steps - self._current_step,
                'total_reward_so_far': round(self._total_reward, 4),
            }
        )

        reward = Reward(
            value=round(reward_value, 4),
            breakdown={'step_reward': round(reward_value, 4)},
            feedback=feedback
        )

        return {
            'observation': observation,
            'reward': reward,
            'done': self._done,
            'info': {
                'step': self._current_step,
                'total_reward': round(self._total_reward, 4)
            }
        }

    def state(self) -> dict:
        """Snapshot of current state. Can be called anytime, changes nothing."""
        return {
            'task_id': self.task_id,
            'step': self._current_step,
            'done': self._done,
            'total_reward': round(self._total_reward, 4),
            'actions_taken': len(self._actions_taken),
            'max_steps': self.MAX_STEPS.get(self.task_id, 10),
        }