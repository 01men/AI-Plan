"""任务：查询/创建/人工审核（人在环路）"""
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app import engine
from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 审核通过折算节省工时（小时/件）
HOURS_BY_PRIORITY = {"高": 3.0, "中": 2.0, "低": 1.0}


def _view(row):
    return dict(row)


def _get_task_or_404(conn, tid):
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        raise HTTPException(404, "任务不存在")
    return row


@router.get("")
def list_tasks(status: str = None, agent_id: int = None, reviewer_id: int = None,
               workspace_id: int = None, conn=Depends(db_conn),
               person=Depends(get_current_person)):
    sql = ("SELECT t.*, a.name agent_name, c.name creator_name, r.name reviewer_name "
           "FROM tasks t LEFT JOIN agents a ON a.id=t.agent_id "
           "LEFT JOIN people c ON c.id=t.creator_id LEFT JOIN people r ON r.id=t.reviewer_id")
    cond, args = [], []
    if status:
        cond.append("t.status=?")
        args.append(status)
    if agent_id:
        cond.append("t.agent_id=?")
        args.append(agent_id)
    if reviewer_id:
        cond.append("t.reviewer_id=?")
        args.append(reviewer_id)
    if workspace_id:
        cond.append("t.workspace_id=?")
        args.append(workspace_id)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY t.id DESC"
    return [_view(r) for r in conn.execute(sql, args)]


@router.post("")
def create_task(body: dict = Body(...), conn=Depends(db_conn), person=Depends(get_current_person)):
    """任务中心直建任务。

    - 带 agent_id：复用引擎执行逻辑，立即产出交付物并转「待审核」；
    - 不带 agent_id：允许创建（停留「待处理」），响应附带 hint 提示不会自动执行。
    """
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title 必填")
    agent_id = body.get("agent_id")
    agent = None
    if agent_id:
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not agent:
            raise HTTPException(404, "数字员工不存在")
    now = datetime.now().isoformat(timespec="seconds")
    tid = conn.execute(
        "INSERT INTO tasks(workspace_id,title,agent_id,creator_id,reviewer_id,status,priority,"
        "requirement,deadline,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (body.get("workspace_id"), title, agent_id, person["id"],
         body.get("reviewer_id"), body.get("status", "待处理"), body.get("priority", "中"),
         body.get("requirement", ""), body.get("deadline"), now)).lastrowid
    conn.commit()
    audit(conn, person["name"], "创建任务", title, f"任务 #{tid}")

    if not agent:
        resp = _view(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
        resp["hint"] = "未指派数字员工，任务不会自动执行，建议到协作空间 @数字员工 派活"
        return resp

    # 立即执行：生成交付物 → 待审核
    requirement = body.get("requirement") or title
    deliverable = engine.generate_deliverable(conn, agent, requirement)
    reviewer = engine._pick_reviewer(conn, body.get("workspace_id"), person["id"])
    conn.execute("UPDATE tasks SET status='待审核', deliverable=?, reviewer_id=? WHERE id=?",
                 (deliverable, reviewer, tid))
    if body.get("workspace_id"):
        engine._add_message(conn, body["workspace_id"], "agent", agent["id"], agent["name"],
                            "agent", "deliverable", deliverable,
                            {"task_id": tid, "status": "待审核", "version": 1})
        engine._add_message(conn, body["workspace_id"], "system", None, "系统", "agent", "approval",
                            f"任务 #{tid} 交付物已生成，待人工审核"
                            f"（审核人：{engine._person_name(conn, reviewer)}）。")
    conn.commit()
    return _view(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


@router.post("/{tid}/review")
def review_task(tid: int, body: dict = Body(...), conn=Depends(db_conn),
                person=Depends(get_current_person)):
    """人工审核：approve 通过计产出 / reject 驳回并触发数字员工重做。

    权限：仅 tier ∈ {boss, coach, backbone}，且不能审核自己发起的任务。
    """
    task = _get_task_or_404(conn, tid)
    if person["tier"] not in ("boss", "coach", "backbone"):
        raise HTTPException(403, "当前身份无权审核任务，仅高管/教练团/骨干可审核")
    if task["creator_id"] == person["id"]:
        raise HTTPException(403, "不能审核自己发起的任务")
    action = body.get("action")
    comment = body.get("comment", "")
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action 仅支持 approve/reject")
    if task["status"] != "待审核":
        raise HTTPException(400, f"任务当前状态为「{task['status']}」，仅待审核任务可审核")
    now = datetime.now().isoformat(timespec="seconds")

    if action == "approve":
        hours = HOURS_BY_PRIORITY.get(task["priority"], 2.0)
        conn.execute(
            "UPDATE tasks SET status='已通过', review_comment=?, reviewer_id=?, done_at=? WHERE id=?",
            (comment, person["id"], now, tid))
        if task["agent_id"]:
            # 累计档案产出 + 当日指标
            conn.execute("UPDATE agents SET tasks_done=tasks_done+1, hours_saved=ROUND(hours_saved+?,1)"
                         " WHERE id=?", (hours, task["agent_id"]))
            today = datetime.now().date().isoformat()
            row = conn.execute("SELECT id FROM metrics_daily WHERE date=? AND agent_id=?",
                               (today, task["agent_id"])).fetchone()
            if row:
                conn.execute("UPDATE metrics_daily SET tasks_done=tasks_done+1,"
                             " hours_saved=ROUND(hours_saved+?,1) WHERE id=?", (hours, row["id"]))
            else:
                conn.execute("INSERT INTO metrics_daily(date,agent_id,tasks_done,hours_saved,token_cost,"
                             "accuracy) VALUES(?,?,1,?,0,0)", (today, task["agent_id"], hours))
        if task["workspace_id"]:
            engine._add_message(conn, task["workspace_id"], "system", None, "系统", "discussion",
                                "text",
                                f"任务 #{tid}「{task['title']}」已通过 {person['name']} 审核"
                                + (f"，批注：{comment}" if comment else "") + "。")
        conn.commit()
        audit(conn, person["name"], "审核通过", f"任务#{tid}", comment)
    else:
        conn.execute("UPDATE tasks SET status='已驳回', review_comment=?, reviewer_id=? WHERE id=?",
                     (comment, person["id"], tid))
        conn.commit()
        audit(conn, person["name"], "审核驳回", f"任务#{tid}", comment)
        if task["agent_id"]:  # 触发数字员工重做一轮：新交付物，状态回待审核
            engine.rework(conn, tid)
            conn.commit()
    return _view(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
