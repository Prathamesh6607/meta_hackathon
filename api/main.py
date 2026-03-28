# api/main.py
from fastapi import FastAPI, HTTPException
from env.environment import EmailTriageEnv
from env.models import Action

app = FastAPI(
    title='Email Triage OpenEnv',
    version='1.0.0',
    description='Real-world email triage environment for AI agent benchmarking'
)

# One environment instance per task
envs = {
    'task_1': EmailTriageEnv(task_id='task_1'),
    'task_2': EmailTriageEnv(task_id='task_2'),
    'task_3': EmailTriageEnv(task_id='task_3'),
}


@app.get('/')
def health():
    return {'status': 'ok', 'environment': 'email-triage-env', 'tasks': list(envs.keys())}


@app.post('/reset/{task_id}')
def reset(task_id: str):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    obs = envs[task_id].reset()
    return obs.model_dump()


@app.post('/step/{task_id}')
def step(task_id: str, action: Action):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    try:
        result = envs[task_id].step(action)
        return {
            'observation': result['observation'].model_dump(),
            'reward': result['reward'].model_dump(),
            'done': result['done'],
            'info': result['info']
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get('/state/{task_id}')
def state(task_id: str):
    if task_id not in envs:
        raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
    return envs[task_id].state()