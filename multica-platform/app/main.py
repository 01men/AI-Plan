import asyncio

from fastapi import Body, Depends, FastAPI, Header, HTTPException

from app.bridge import Bridge, BridgeError
from app.config import CONFIG
from app.database import init_db


app = FastAPI(title="Multica × 榕器 Agent 运行时桥接", version="0.1.0")
bridge = Bridge(CONFIG)


def require_admin(x_bridge_token: str = Header(default="")):
    if CONFIG.bridge_admin_token and x_bridge_token != CONFIG.bridge_admin_token:
        raise HTTPException(401, "X-Bridge-Token 无效")


@app.get("/health")
def health():
    rongqi = {"available": False}
    try:
        agents = bridge.rongqi.list_agents()
        rongqi = {"available": True, "agent_count": len(agents)}
    except Exception as exc:
        rongqi = {"available": False, "detail": str(exc)}
    return {"ok": rongqi["available"], "rongqi": rongqi,
            "multica": bridge.multica.health(), "auto_sync": CONFIG.bridge_auto_sync,
            "poll_seconds": CONFIG.bridge_poll_seconds}


@app.get("/api/bindings")
def bindings():
    return bridge.list_bindings()


@app.put("/api/bindings/{agent_id}", dependencies=[Depends(require_admin)])
def put_binding(agent_id: int, body: dict = Body(...)):
    try:
        return bridge.upsert_binding(agent_id, body)
    except BridgeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/tasks/{task_id}/dispatch", dependencies=[Depends(require_admin)])
def dispatch(task_id: int):
    try:
        return bridge.dispatch(task_id)
    except BridgeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/sync", dependencies=[Depends(require_admin)])
def sync(body: dict = Body(default={})):
    try:
        return {"ok": True, "results": bridge.sync(
            task_id=body.get("task_id"), limit=int(body.get("limit", 50)))}
    except (BridgeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/runs")
def runs(limit: int = 100):
    return bridge.list_runs(limit)


@app.get("/api/events")
def events(limit: int = 100):
    return bridge.list_events(limit)


async def _sync_loop():
    while True:
        await asyncio.sleep(max(5, CONFIG.bridge_poll_seconds))
        if CONFIG.bridge_auto_sync:
            await asyncio.to_thread(bridge.sync)


@app.on_event("startup")
async def startup():
    init_db(CONFIG.bridge_db_path)
    asyncio.create_task(_sync_loop())
