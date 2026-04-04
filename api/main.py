# api/main.py
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from env.environment import EmailTriageEnv
from env.models import Action

app = FastAPI(
    title='Tier-2 Support OpenEnv',
    version='1.0.0',
    description='Tier-2 customer support benchmark for policy and multi-system workflows'
)

# One environment instance per task
envs = {
    'task_1': EmailTriageEnv(task_id='task_1'),
    'task_2': EmailTriageEnv(task_id='task_2'),
    'task_3': EmailTriageEnv(task_id='task_3'),
}

BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / 'ui'

app.mount('/ui-assets', StaticFiles(directory=UI_DIR), name='ui-assets')


@app.get('/')
def health():
    return {'status': 'ok', 'environment': 'email-triage-env', 'tasks': list(envs.keys())}


@app.get('/ui')
def ui():
    return FileResponse(UI_DIR / 'index.html')


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
