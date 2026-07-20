"""数字员工档案：列表/详情/状态维护"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/agents", tags=["agents"])

# 数字员工状态枚举（PATCH 仅允许这些值）
AGENT_STATUS_ALLOWED = ("规划中", "开发中", "试运行", "已上线", "已下线")


def _view(row):
    d = dict(row)
    try:
        d["skills"] = json.loads(d.get("skills") or "[]")
    except Exception:
        d["skills"] = []
    return d


@router.get("")
def list_agents(platform_id: int = None, status: str = None, wave: int = None,
                category: str = None, conn=Depends(db_conn),
                person=Depends(get_current_person)):
    sql = ("SELECT a.*, d.name dept_name, d.platform_id, p.name platform_name, pe.name owner_name "
           "FROM agents a JOIN departments d ON d.id=a.dept_id "
           "JOIN platforms p ON p.id=d.platform_id LEFT JOIN people pe ON pe.id=a.owner_id")
    cond, args = [], []
    if platform_id:
        cond.append("d.platform_id=?")
        args.append(platform_id)
    if status:
        cond.append("a.status=?")
        args.append(status)
    if wave:
        cond.append("a.wave=?")
        args.append(wave)
    if category:
        cond.append("a.category=?")
        args.append(category)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY a.id"
    return [_view(r) for r in conn.execute(sql, args)]


@router.get("/{aid}")
def get_agent(aid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    row = conn.execute(
        "SELECT a.*, d.name dept_name, d.platform_id, p.name platform_name, pe.name owner_name "
        "FROM agents a JOIN departments d ON d.id=a.dept_id "
        "JOIN platforms p ON p.id=d.platform_id LEFT JOIN people pe ON pe.id=a.owner_id "
        "WHERE a.id=?", (aid,)).fetchone()
    if not row:
        raise HTTPException(404, "数字员工不存在")
    d = _view(row)
    # 绑定场景
    d["scenarios"] = [dict(r) for r in conn.execute(
        "SELECT id,name,status,priority,batch,expected_benefit FROM scenarios WHERE agent_id=?", (aid,))]
    # 近 14 天指标
    since = (datetime.now().date() - timedelta(days=13)).isoformat()
    d["metrics_14d"] = [dict(r) for r in conn.execute(
        "SELECT date,tasks_done,hours_saved,token_cost,accuracy FROM metrics_daily "
        "WHERE agent_id=? AND date>=? ORDER BY date", (aid, since))]
    # 最近 10 条任务
    d["recent_tasks"] = [dict(r) for r in conn.execute(
        "SELECT id,workspace_id,title,status,priority,created_at,done_at FROM tasks "
        "WHERE agent_id=? ORDER BY id DESC LIMIT 10", (aid,))]
    return d


@router.patch("/{aid}")
def update_agent(aid: int, body: dict = Body(...), conn=Depends(db_conn),
                 person=Depends(get_current_person)):
    """状态维护：仅 boss/coach 或该数字员工的 owner 本人；status 有枚举校验。"""
    row = conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone()
    if not row:
        raise HTTPException(404, "数字员工不存在")
    if person["tier"] not in ("boss", "coach") and row["owner_id"] != person["id"]:
        raise HTTPException(403, "仅高管/教练团或该数字员工的负责人本人可修改")
    if "status" in body and body["status"] not in AGENT_STATUS_ALLOWED:
        raise HTTPException(422, f"status 仅允许：{'/'.join(AGENT_STATUS_ALLOWED)}，"
                                 f"收到「{body['status']}」")
    allowed = {"status", "description", "owner_id", "wave", "accuracy", "category", "name"}
    sets, args = [], []
    for k, v in body.items():
        if k in allowed:
            sets.append(f"{k}=?")
            args.append(v)
        elif k == "skills":  # skills 允许传数组，落库为 JSON 字符串
            sets.append("skills=?")
            args.append(json.dumps(v, ensure_ascii=False))
    if not sets:
        raise HTTPException(400, "没有可更新的字段")
    args.append(aid)
    conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE id=?", args)
    conn.commit()
    audit(conn, person["name"], "更新数字员工", row["name"], f"更新字段：{','.join(body.keys())}")
    return _view(conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone())
