"""任务：查询/创建/人工审核（人在环路）"""
import json
import re
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app import engine
from app.access import can_access_task, require_task, require_workspace
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


def _detail(conn, tid):
    row = conn.execute(
        "SELECT t.*,a.name agent_name,c.name creator_name,r.name reviewer_name "
        "FROM tasks t LEFT JOIN agents a ON a.id=t.agent_id "
        "LEFT JOIN people c ON c.id=t.creator_id LEFT JOIN people r ON r.id=t.reviewer_id "
        "WHERE t.id=?", (tid,)).fetchone()
    if not row:
        raise HTTPException(404, "任务不存在")
    return dict(row)


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
    return [_view(r) for r in conn.execute(sql, args) if can_access_task(conn, r, person)]


@router.get("/{tid}")
def get_task(tid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    """按 ID 读取单项任务，供外部 Agent 运行时使用。"""
    require_task(conn, tid, person)
    return _detail(conn, tid)


@router.post("")
def create_task(body: dict = Body(...), conn=Depends(db_conn), person=Depends(get_current_person)):
    """任务中心直建任务。

    - 带 agent_id：复用引擎执行逻辑，立即产出交付物并转「待审核」；
    - 不带 agent_id：允许创建（停留「待处理」），响应附带 hint 提示不会自动执行。
    """
    if person["tier"] == "staff":
        raise HTTPException(403, "普通员工请在已有工作区派活；创建任务请联系项目负责人")
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title 必填")
    priority = body.get("priority", "中")
    if priority not in HOURS_BY_PRIORITY:
        raise HTTPException(422, "priority 仅支持 高/中/低")
    reviewer_id = body.get("reviewer_id")
    if reviewer_id and not conn.execute(
            "SELECT 1 FROM people WHERE id=? AND status='在职'", (reviewer_id,)).fetchone():
        raise HTTPException(422, "指定审核人不存在或已停用")
    agent_id = body.get("agent_id")
    workspace_id = body.get("workspace_id")
    if workspace_id:
        require_workspace(conn, workspace_id, person)
    agent = None
    if agent_id:
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not agent:
            raise HTTPException(404, "数字员工不存在")
        if workspace_id and not conn.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id=? "
                "AND member_type='agent' AND member_id=?",
                (workspace_id, agent_id)).fetchone():
            raise HTTPException(422, "该数字员工尚未加入此工作区，请先由负责人配置成员")
    now = datetime.now().isoformat(timespec="seconds")
    # status 不信任客户端：直建任务一律从「待处理」起步，状态机由引擎/审核推进
    tid = conn.execute(
        "INSERT INTO tasks(workspace_id,title,agent_id,creator_id,reviewer_id,status,priority,"
        "requirement,deadline,created_at) VALUES(?,?,?,?,?,'待处理',?,?,?,?)",
        (workspace_id, title, agent_id, person["id"], reviewer_id, priority,
         body.get("requirement", ""), body.get("deadline"), now)).lastrowid
    conn.commit()
    audit(conn, person["name"], "创建任务", title, f"任务 #{tid}")

    if not agent:
        resp = _view(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
        resp["hint"] = "未指派数字员工，任务不会自动执行，建议到协作空间 @数字员工 派活"
        return resp

    # 立即执行：生成交付物 → 待审核
    requirement = body.get("requirement") or title
    deliverable, model_info = engine.generate_deliverable(conn, agent, requirement, tid)
    reviewer = engine._pick_reviewer(conn, workspace_id, person["id"])
    mode, exec_error, exec_ms = engine._execution_fields(model_info)
    conn.execute(
        "UPDATE tasks SET status='待审核',deliverable=?,reviewer_id=?,model_provider=?,"
        "model_name=?,execution_mode=?,execution_error=?,execution_ms=? WHERE id=?",
        (deliverable, reviewer, model_info.get("provider"), model_info.get("model"),
         mode, exec_error, exec_ms, tid),
    )
    if workspace_id:
        engine._add_message(conn, workspace_id, "agent", agent["id"], agent["name"],
                            "agent", "deliverable", deliverable,
                            {"task_id": tid, "status": "待审核", "version": 1,
                             "model_info": model_info})
        engine._add_message(conn, workspace_id, "system", None, "系统", "agent", "approval",
                            f"任务 #{tid} 交付物已生成，待人工审核"
                            f"（审核人：{engine._person_name(conn, reviewer)}）。")
    conn.commit()
    return _view(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


@router.post("/{tid}/external-events")
def external_event(tid: int, body: dict = Body(...), conn=Depends(db_conn),
                   person=Depends(get_current_person)):
    """外部执行控制面回传事件；任何交付物都只进入“待审核”。"""
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管或教练团身份可回传外部运行时事件")
    task = require_task(conn, tid, person)
    if task["status"] == "已通过":
        raise HTTPException(409, "任务已经人工审核通过，不能再写入外部事件")
    event_type = str(body.get("event_type") or "").strip().lower()
    if event_type not in ("started", "progress", "blocked", "deliverable", "cancelled"):
        raise HTTPException(400, "event_type 仅支持 started/progress/blocked/deliverable/cancelled")
    event_id = str(body.get("event_id") or "").strip()
    source = str(body.get("source") or "external-runtime").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", event_id):
        raise HTTPException(400, "event_id 仅允许 1-128 位字母、数字、点、下划线、冒号或短横线")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", source):
        raise HTTPException(400, "source 格式不合法")
    content = str(body.get("content") or "").strip()
    if len(content) > 20000:
        raise HTTPException(400, "content 不能超过 20000 字符")
    metadata = body.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(400, "metadata 必须是对象")
    # 幂等去重：runtime_events 按 (task_id, source, event_id) 唯一，同事件重复回传直接吞掉，
    # 但不同任务的相同 event_id 互不影响（旧 settings 键方案会跨任务误吞，已废弃）
    try:
        conn.execute(
            "INSERT INTO runtime_events(task_id,source,event_id,event_type,created_at)"
            " VALUES(?,?,?,?,?)",
            (tid, source, event_id, event_type,
             datetime.now().isoformat(timespec="seconds")))
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"ok": True, "idempotent": True, "task": _detail(conn, tid)}

    payload = {"task_id": tid, "runtime": "external", "source": source,
               "external_event_id": event_id, "metadata": metadata}
    if event_type == "started":
        conn.execute("UPDATE tasks SET status='进行中',deliverable=NULL,done_at=NULL,"
                     "execution_mode='external',execution_error=NULL WHERE id=?",
                     (tid,))
        message = content or f"任务 #{tid} 已进入 {source} 执行队列。"
    elif event_type == "progress":
        conn.execute("UPDATE tasks SET status='进行中' WHERE id=?", (tid,))
        message = content or f"任务 #{tid} 外部执行进度已更新。"
    elif event_type == "blocked":
        conn.execute("UPDATE tasks SET status='进行中' WHERE id=?", (tid,))
        message = content or f"任务 #{tid} 外部执行受阻，请人工处理。"
    elif event_type == "cancelled":
        message = content or f"任务 #{tid} 外部执行已取消。"
        conn.execute("UPDATE tasks SET status='已驳回',review_comment=? WHERE id=?",
                     (message, tid))
    else:
        if not content:
            raise HTTPException(400, "deliverable 事件必须包含 content")
        reviewer = task["reviewer_id"] or engine._pick_reviewer(
            conn, task["workspace_id"], task["creator_id"])
        conn.execute("UPDATE tasks SET status='待审核',deliverable=?,reviewer_id=?,"
                     "execution_mode='external',execution_error=NULL WHERE id=?",
                     (content, reviewer, tid))
        message = f"{source} 已完成任务 #{tid}，交付物已进入人工审核。"
        if task["workspace_id"]:
            version = engine._deliverable_version(conn, tid, task["workspace_id"])
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (task["agent_id"],)).fetchone()
            if agent:
                engine._add_message(conn, task["workspace_id"], "agent", agent["id"], agent["name"],
                                    "agent", "deliverable", content,
                                    {**payload, "status": "待审核", "version": version})
            engine._add_message(
                conn, task["workspace_id"], "system", None, "系统", "agent", "approval",
                f"{message}审核人：{engine._person_name(conn, reviewer)}。", payload)

    if task["workspace_id"] and event_type != "deliverable":
        engine._add_message(conn, task["workspace_id"], "system", None, "系统", "agent",
                            "runtime_event", message, payload)
    conn.execute(
        "INSERT INTO audits(actor,action,target,detail,created_at) VALUES(?,?,?,?,?)",
        (person["name"], "外部运行时事件", f"任务#{tid}",
         json.dumps({"event_type": event_type, "source": source, "event_id": event_id},
                    ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    return {"ok": True, "idempotent": False, "task": _detail(conn, tid)}


def _latest_deliverable_is_external(conn, task):
    if not task["workspace_id"]:
        return False
    row = conn.execute(
        "SELECT payload FROM messages WHERE workspace_id=? AND msg_type='deliverable' "
        "AND (payload LIKE ? OR payload LIKE ?) ORDER BY id DESC LIMIT 1",
        (task["workspace_id"], f'%"task_id": {task["id"]},%',
         f'%"task_id": {task["id"]}}}%')).fetchone()
    if not row or not row["payload"]:
        return False
    try:
        return json.loads(row["payload"]).get("runtime") == "external"
    except (TypeError, json.JSONDecodeError):
        return False


@router.post("/{tid}/review")
def review_task(tid: int, body: dict = Body(...), conn=Depends(db_conn),
                person=Depends(get_current_person)):
    """人工审核：approve 通过计产出 / reject 驳回并触发数字员工重做。

    权限：仅 tier ∈ {boss, coach, backbone}，且不能审核自己发起的任务。
    """
    task = require_task(conn, tid, person)
    if person["tier"] not in ("boss", "coach", "backbone"):
        raise HTTPException(403, "当前身份无权审核任务，仅高管/教练团/骨干可审核")
    if task["creator_id"] == person["id"]:
        raise HTTPException(403, "不能审核自己发起的任务")
    if task["reviewer_id"] and person["id"] != task["reviewer_id"] and person["tier"] != "boss":
        raise HTTPException(403, f"该任务已指派给 {engine._person_name(conn, task['reviewer_id'])} 审核")
    action = body.get("action")
    comment = body.get("comment", "")
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action 仅支持 approve/reject")
    if task["status"] != "待审核":
        raise HTTPException(400, f"任务当前状态为「{task['status']}」，仅待审核任务可审核")
    now = datetime.now().isoformat(timespec="seconds")

    if action == "approve":
        hours = HOURS_BY_PRIORITY.get(task["priority"], 2.0)
        # 条件 UPDATE 原子抢占：并发审核只有一方 rowcount=1，失败方 409，不计产出
        cur = conn.execute(
            "UPDATE tasks SET status='已通过', review_comment=?, reviewer_id=?, done_at=? "
            "WHERE id=? AND status='待审核'",
            (comment, person["id"], now, tid))
        if cur.rowcount == 0:
            raise HTTPException(409, "任务状态已被变更，请刷新后重试")
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
        cur = conn.execute(
            "UPDATE tasks SET status='已驳回', review_comment=?, reviewer_id=? "
            "WHERE id=? AND status='待审核'",
            (comment, person["id"], tid))
        if cur.rowcount == 0:
            raise HTTPException(409, "任务状态已被变更，请刷新后重试")
        conn.commit()
        audit(conn, person["name"], "审核驳回", f"任务#{tid}", comment)
        if task["agent_id"]:
            if _latest_deliverable_is_external(conn, task):
                if task["workspace_id"]:
                    engine._add_message(
                        conn, task["workspace_id"], "system", None, "系统", "agent", "runtime_event",
                        f"任务 #{tid} 的外部交付物已驳回，等待外部 Agent 按意见重做。",
                        {"task_id": tid, "runtime": "external", "review_comment": comment})
            else:  # 原有本地任务仍由本地执行引擎自动重做
                engine.rework(conn, tid)
            conn.commit()
    return _view(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
