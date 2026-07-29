"""FastAPI 入口：路由挂载、静态目录、启动建库播种、心跳后台任务"""
import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import crypto, engine
from app.database import get_db, init_db
from app.routers import (agents, auth, flows, governance, imbind, knowledge, mcp,
                         metrics, models, org, roadmap, scenarios, skills, tasks,
                         workspaces)
from app.routers.auth import audit, db_conn, get_current_person
from app.seed import run_flow_seed, run_r4_seed, run_r5_seed, run_r6_seed, run_seed

app = FastAPI(title="Agent 人机协作平台", version="1.6.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 参数校验错误统一中文化（pydantic 英文原文兜底，B-4）"""
    fields = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("body", "query", "path"))
        fields.append(loc or "参数")
    detail = f"参数校验失败：{('、'.join(sorted(set(fields))))} 缺失或格式错误"
    return JSONResponse(status_code=422, content={"detail": detail})

# 仅允许本机交付地址跨源访问，避免任意网页携带本地 Token 调用平台。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

for r in (auth, org, agents, scenarios, workspaces, tasks, skills, knowledge,
          metrics, governance, roadmap, flows, models, mcp, imbind):
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


@app.get("/api/health")
def health():
    """部署/验收探针，不读取业务数据。"""
    return {"ok": True, "service": "rongqi-agent-platform", "version": app.version}


@app.post("/api/heartbeat/run")
def heartbeat_run(conn=Depends(db_conn), person=Depends(get_current_person)):
    """立即执行一次心跳（日报 + 催办），返回执行摘要"""
    if person["tier"] not in ("boss", "coach", "backbone"):
        from fastapi import HTTPException
        raise HTTPException(403, "仅高管、教练团或业务骨干可手动触发全局心跳")
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
    run_flow_seed(conn)  # 流程引擎演示数据，settings.flow_seeded 标记，只跑一次
    run_r4_seed(conn)  # R4 增量种子（模型/MCP/IM 授权配置），settings.r4_seeded 标记
    run_r5_seed(conn)  # R5：按方案文档补齐 232 个场景容量位（幂等、不覆盖）
    run_r6_seed(conn)  # R6：每次部署幂等补齐 1000 条制造业务展示数据
    crypto.migrate_credentials(conn)  # R5：明文凭证自动改写为 enc:v1 密文（幂等）
    conn.close()
    asyncio.create_task(_heartbeat_loop())
