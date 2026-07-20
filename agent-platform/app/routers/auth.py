"""认证与公共依赖：登录、当前用户、审计工具"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

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
    person = conn.execute("SELECT * FROM people WHERE id=?", (int(row["value"]),)).fetchone()
    if not person:
        raise HTTPException(401, "账号不存在")
    return person_view(conn, person)


def audit(conn, actor, action, target, detail=""):
    """写操作统一记审计"""
    conn.execute(
        "INSERT INTO audits(actor,action,target,detail,created_at) VALUES(?,?,?,?,?)",
        (actor, action, target, detail, datetime.now().isoformat(timespec="seconds")))
    conn.commit()


class LoginIn(BaseModel):
    person_id: int


@router.post("/login")
def login(body: LoginIn, conn=Depends(db_conn)):
    person = conn.execute("SELECT * FROM people WHERE id=?", (body.person_id,)).fetchone()
    if not person:
        raise HTTPException(404, "人员不存在")
    token = uuid.uuid4().hex
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?)", (f"token:{token}", str(person["id"])))
    conn.commit()
    # 登录是高频流水，不写 audits，避免刷屏淹没真实操作审计
    return {"token": token, "person": person_view(conn, person)}


@router.get("/me")
def me(person=Depends(get_current_person)):
    return person
