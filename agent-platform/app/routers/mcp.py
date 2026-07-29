"""MCP 服务台账（R4-2）：本迭代只做绑定与展示，不做真实 MCP 调用"""
import json

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

MCP_STATUS_ALLOWED = ("启用", "停用")


def expand_mcp(conn, mcp_ids):
    """把 agents.mcp_ids（id 数组）展开为 MCP 对象数组，忽略已删除的 id"""
    out = []
    for mid in mcp_ids or []:
        row = conn.execute("SELECT * FROM mcp_servers WHERE id=?", (mid,)).fetchone()
        if row:
            out.append(dict(row))
    return out


def parse_mcp_ids(v):
    """mcp_ids 入参归一化为 int 数组；非法抛 422"""
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            raise HTTPException(422, "mcp_ids 需为 MCP 服务 id 数组")
    if not isinstance(v, list):
        raise HTTPException(422, "mcp_ids 需为 MCP 服务 id 数组")
    try:
        return [int(x) for x in v]
    except (TypeError, ValueError):
        raise HTTPException(422, "mcp_ids 需为 MCP 服务 id 数组")


@router.get("")
def list_mcp(conn=Depends(db_conn), person=Depends(get_current_person)):
    return [dict(r) for r in conn.execute("SELECT * FROM mcp_servers ORDER BY id")]


@router.post("")
def create_mcp(body: dict = Body(...), conn=Depends(db_conn), person=Depends(get_current_person)):
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可维护 MCP 服务")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name 必填")
    mid = conn.execute(
        "INSERT INTO mcp_servers(name,endpoint,description,status) VALUES(?,?,?,?)",
        (name, body.get("endpoint", ""), body.get("description", ""),
         body.get("status", "停用"))).lastrowid
    conn.commit()
    audit(conn, person["name"], "新增MCP服务", name)
    return dict(conn.execute("SELECT * FROM mcp_servers WHERE id=?", (mid,)).fetchone())


@router.patch("/{mid}")
def update_mcp(mid: int, body: dict = Body(...), conn=Depends(db_conn),
               person=Depends(get_current_person)):
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可维护 MCP 服务")
    row = conn.execute("SELECT * FROM mcp_servers WHERE id=?", (mid,)).fetchone()
    if not row:
        raise HTTPException(404, "MCP 服务不存在")
    if "status" in body and body["status"] not in MCP_STATUS_ALLOWED:
        raise HTTPException(422, f"status 仅允许：{'/'.join(MCP_STATUS_ALLOWED)}")
    sets, args = [], []
    for k in ("name", "endpoint", "description", "status"):
        if k in body:
            sets.append(f"{k}=?")
            args.append(body[k])
    if not sets:
        raise HTTPException(400, "没有可更新的字段")
    args.append(mid)
    conn.execute(f"UPDATE mcp_servers SET {', '.join(sets)} WHERE id=?", args)
    conn.commit()
    audit(conn, person["name"], "更新MCP服务", row["name"], f"更新字段：{','.join(body.keys())}")
    return dict(conn.execute("SELECT * FROM mcp_servers WHERE id=?", (mid,)).fetchone())
