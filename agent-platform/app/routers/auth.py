"""认证与公共依赖：登录、当前用户、会话撤销、审计工具"""
import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import demo_login_enabled, public_environment
from app.database import get_db

router = APIRouter(prefix="/api", tags=["auth"])


def db_conn():
    """FastAPI 依赖：每请求一个 sqlite 连接"""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def person_view(conn, person):
    """人员字典附带部门/平台名，便于前端展示"""
    d = dict(person)
    row = conn.execute(
        "SELECT dep.name dept_name, p.name platform_name, p.id platform_id FROM departments dep "
        "JOIN platforms p ON p.id=dep.platform_id WHERE dep.id=?", (d["dept_id"],)).fetchone()
    if row:
        d.update(dict(row))
    return d


def get_current_person(authorization: str = Header(None), conn=Depends(db_conn)):
    """依赖注入：从 Authorization: Bearer <token> 解析当前人"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录或缺少 Token")
    token = authorization[7:].strip()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (f"token:{token}",)).fetchone()
    if not row:
        raise HTTPException(401, "Token 无效或已过期")
    try:
        payload = json.loads(row["value"])
        if isinstance(payload, dict):
            if datetime.fromisoformat(payload["expires_at"]) < datetime.now():
                conn.execute("DELETE FROM settings WHERE key=?", (f"token:{token}",))
                conn.commit()
                raise HTTPException(401, "登录已过期，请重新进入")
            person_id = int(payload["person_id"])
        else:
            person_id = int(payload)
    except (json.JSONDecodeError, TypeError):
        person_id = int(row["value"])  # 兼容旧会话
    person = conn.execute(
        "SELECT * FROM people WHERE id=? AND status='在职'", (person_id,)
    ).fetchone()
    if not person:
        raise HTTPException(401, "账号不存在或已停用")
    return person_view(conn, person)


def audit(conn, actor, action, target, detail=""):
    """写操作统一记审计"""
    conn.execute(
        "INSERT INTO audits(actor,action,target,detail,created_at) VALUES(?,?,?,?,?)",
        (actor, action, target, detail, datetime.now().isoformat(timespec="seconds")))
    conn.commit()


class LoginIn(BaseModel):
    person_id: int


def issue_session(conn, person_id: int, hours: int = 12):
    person = conn.execute(
        "SELECT * FROM people WHERE id=? AND status='在职'", (person_id,)
    ).fetchone()
    if not person:
        raise HTTPException(404, "人员不存在或账号已停用")
    token = secrets.token_urlsafe(32)
    payload = {
        "person_id": person["id"],
        "expires_at": (datetime.now() + timedelta(hours=hours)).isoformat(timespec="seconds"),
    }
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?)",
                 (f"token:{token}", json.dumps(payload, ensure_ascii=False)))
    conn.commit()
    return {"token": token, "person": person_view(conn, person)}


@router.post("/login")
def login(body: LoginIn, conn=Depends(db_conn)):
    if not demo_login_enabled():
        raise HTTPException(403, "生产模式已关闭演示身份登录，请使用企业 IM 授权登录")
    # 登录是高频流水，不写 audits，避免刷屏淹没真实操作审计
    return issue_session(conn, body.person_id)


@router.get("/environment")
def environment():
    """公开返回安全的运行模式与演示登录能力，供登录页选择认证方式。"""
    return public_environment()


@router.get("/me")
def me(person=Depends(get_current_person)):
    return person


@router.post("/logout")
def logout(authorization: str = Header(None), conn=Depends(db_conn)):
    if authorization and authorization.startswith("Bearer "):
        conn.execute("DELETE FROM settings WHERE key=?",
                     (f"token:{authorization[7:].strip()}",))
        conn.commit()
    return {"ok": True}
