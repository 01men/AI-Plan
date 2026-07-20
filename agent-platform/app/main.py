"""FastAPI 入口：路由挂载、静态目录、启动建库播种、心跳后台任务"""
import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import engine
from app.database import get_db, init_db
from app.routers import (agents, auth, governance, knowledge, metrics, org,
                         roadmap, scenarios, skills, tasks, workspaces)
from app.routers.auth import audit, db_conn, get_current_person
from app.seed import run_seed

app = FastAPI(title="Agent 人机协作平台", version="1.0.0")

# 前端本地开发联调方便起见放开 CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth, org, agents, scenarios, workspaces, tasks, skills, knowledge,
          metrics, governance, roadmap):
    app.include_router(r.router)

# 静态目录（前端构建产物放这里）
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    """GET /：index.html 存在则返回，否则兜底 JSON"""
    f = STATIC_DIR / "index.html"
    if f.exists():
        return FileResponse(str(f))
    return JSONResponse({"msg": "Agent 人机协作平台后端运行中；前端 index.html 尚未部署到 app/static"})


@app.post("/api/heartbeat/run")
def heartbeat_run(conn=Depends(db_conn), person=Depends(get_current_person)):
    """立即执行一次心跳（日报 + 催办），返回执行摘要"""
    summary = engine.heartbeat(conn)
    audit(conn, person["name"], "手动触发心跳", "heartbeat", str(summary))
    return summary


HEARTBEAT_INTERVAL = 6 * 3600  # 每 6 小时一次


async def _heartbeat_loop():
    """心跳后台任务：循环执行，异常不中断"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        try:
            conn = get_db()
            engine.heartbeat(conn)
            conn.close()
        except Exception:
            pass


@app.on_event("startup")
async def startup():
    """启动：建表 + 首次播种 + 启动心跳后台任务"""
    conn = get_db()
    init_db(conn)
    run_seed(conn)  # 内部用 settings.seeded 标记，只跑一次
    conn.close()
    asyncio.create_task(_heartbeat_loop())
