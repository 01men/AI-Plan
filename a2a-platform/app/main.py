import asyncio

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import CONFIG
from app.database import init_db
from app.security import PolicyError, verify_token
from app.service import ControlError, ControlPlane


app = FastAPI(title='榕器 A2A 协作控制面', version='3.1.0')
plane = ControlPlane(CONFIG)


def actor(x_actor: str = Header(default='管理员')): return x_actor or '管理员'
def admin(x_a2a_token: str = Header(default='')):
    if CONFIG.admin_token and x_a2a_token != CONFIG.admin_token: raise HTTPException(401, 'X-A2A-Token 无效')
def call(fn):
    try: return fn()
    except ControlError as exc: raise HTTPException(400, str(exc)) from exc


@app.get('/health')
def health(): return {'ok': True, 'mode':'sqlite-single-instance' if CONFIG.single_instance else 'unsupported', 'worker_interval_seconds':CONFIG.worker_interval_seconds}

@app.get('/api/resources', dependencies=[Depends(admin)])
def resources(): return plane.list_resources()
@app.post('/api/resources', dependencies=[Depends(admin)])
def register(body: dict=Body(...), who: str=Depends(actor)): return call(lambda:plane.register(body,who))
@app.post('/api/resources/{resource_id}/discover', dependencies=[Depends(admin)])
def discover(resource_id:str, who:str=Depends(actor)): return call(lambda:plane.discover(resource_id,who))
@app.post('/api/resources/{resource_id}/sandbox-validate', dependencies=[Depends(admin)])
def sandbox(resource_id:str, who:str=Depends(actor)): return call(lambda:plane.sandbox_validate(resource_id,who))
@app.post('/api/resources/{resource_id}/enable', dependencies=[Depends(admin)])
def enable(resource_id:str, body:dict=Body(default={}), who:str=Depends(actor)): return call(lambda:plane.enable(resource_id,who,body.get('approval_ticket_id','')))
@app.post('/api/resources/{resource_id}/pause', dependencies=[Depends(admin)])
def pause(resource_id:str, body:dict=Body(default={}), who:str=Depends(actor)): return call(lambda:plane.pause(resource_id,who,body.get('reason','')))
@app.post('/api/resources/{resource_id}/unbind', dependencies=[Depends(admin)])
def unbind(resource_id:str, who:str=Depends(actor)): return call(lambda:plane.unbind(resource_id,who))

@app.post('/api/approvals', dependencies=[Depends(admin)])
def ticket(body:dict=Body(...),who:str=Depends(actor)): return call(lambda:plane.create_ticket(body,who))
@app.post('/api/approvals/{ticket_id}/decision', dependencies=[Depends(admin)])
def decision(ticket_id:str,body:dict=Body(...),who:str=Depends(actor)): return call(lambda:plane.decide_ticket(ticket_id,who,bool(body.get('approve'))))

@app.post('/api/contracts', dependencies=[Depends(admin)])
def create_contract(body:dict=Body(...),who:str=Depends(actor)): return call(lambda:plane.create_contract(body,who))
@app.get('/api/contracts/{contract_id}', dependencies=[Depends(admin)])
def contract(contract_id:str): return call(lambda:plane.contract(contract_id))
@app.post('/api/contracts/{contract_id}/review', dependencies=[Depends(admin)])
def review(contract_id:str,body:dict=Body(...),who:str=Depends(actor)): return call(lambda:plane.review(contract_id,who,bool(body.get('approve')),body.get('comment','')))
@app.post('/api/contracts/{contract_id}/input', dependencies=[Depends(admin)])
def input_required(contract_id:str,body:dict=Body(...),who:str=Depends(actor)): return call(lambda:plane.provide_input(contract_id,who,body))
@app.post('/api/contracts/{contract_id}/takeover', dependencies=[Depends(admin)])
def takeover(contract_id:str,body:dict=Body(...),who:str=Depends(actor)): return call(lambda:plane.takeover(contract_id,who,str(body.get('summary',''))))

@app.post('/api/worker/tick', dependencies=[Depends(admin)])
def tick(body:dict=Body(default={})): return plane.process_outbox('manual-worker',max(1,min(int(body.get('limit',20)),100)))
@app.get('/api/runs', dependencies=[Depends(admin)])
def runs(): return plane.runs()
@app.post('/api/runs/{run_id}/events')
def event(run_id:str, body:dict=Body(...), who:str=Depends(actor), authorization:str=Header(default='')):
    """回调使用该任务的短期授权，而非管理令牌，避免把控制面管理员权限交给远端。"""
    if not authorization.startswith('Bearer '): raise HTTPException(401, '缺少任务回调授权')
    try: claims=verify_token(authorization[7:], CONFIG.signing_key, CONFIG.issuer)
    except PolicyError as exc: raise HTTPException(401, str(exc)) from exc
    run=next((r for r in plane.runs() if r['id']==run_id),None)
    if not run or claims.get('contract_id') != run['contract_id']: raise HTTPException(403, '授权与运行记录不匹配')
    return call(lambda:plane.receive_event(run_id,body,who))

@app.on_event('startup')
async def startup():
    init_db(CONFIG.db_path)
    async def worker():
        while True:
            await asyncio.sleep(max(1,CONFIG.worker_interval_seconds)); await asyncio.to_thread(plane.process_outbox)
    asyncio.create_task(worker())


app.mount('/static', StaticFiles(directory=str(__import__('pathlib').Path(__file__).parent/'static')), name='static')
@app.get('/')
def console(): return FileResponse(__import__('pathlib').Path(__file__).parent/'static/index.html')
