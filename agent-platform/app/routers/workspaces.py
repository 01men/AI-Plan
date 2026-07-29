"""协作工作区：三区消息 + @数字员工派活"""
import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app import engine
from app.access import require_workspace, workspace_scope_sql
from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _msg_view(row):
    d = dict(row)
    if d.get("payload"):
        try:
            d["payload"] = json.loads(d["payload"])
        except Exception:
            pass
    return d


def _members(conn, wid):
    """成员列表，解析 human/agent 名称"""
    out = []
    for m in conn.execute("SELECT * FROM workspace_members WHERE workspace_id=?", (wid,)):
        d = dict(m)
        if m["member_type"] == "human":
            r = conn.execute("SELECT name FROM people WHERE id=?", (m["member_id"],)).fetchone()
        else:
            r = conn.execute(
                "SELECT name,status,model_key FROM agents WHERE id=?", (m["member_id"],)
            ).fetchone()
        d["name"] = r["name"] if r else f"{m['member_type']}#{m['member_id']}"
        if r and m["member_type"] == "agent":
            d["status"] = r["status"]
            d["model_key"] = r["model_key"]
        out.append(d)
    return out


@router.get("")
def list_workspaces(type: str = None, conn=Depends(db_conn), person=Depends(get_current_person)):
    sql = ("SELECT w.*, p.name creator_name, s.name scenario_name FROM workspaces w "
           "LEFT JOIN people p ON p.id=w.created_by LEFT JOIN scenarios s ON s.id=w.scenario_id")
    args = []
    conds = []
    if type:
        conds.append("w.type=?")
        args.append(type)
    scope, scope_args = workspace_scope_sql(person, "w")
    if scope:
        conds.append(scope)
        args.extend(scope_args)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY w.id"
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        d["member_count"] = conn.execute(
            "SELECT COUNT(*) c FROM workspace_members WHERE workspace_id=?", (r["id"],)).fetchone()["c"]
        out.append(d)
    return out


@router.post("")
def create_workspace(body: dict = Body(...), conn=Depends(db_conn),
                     person=Depends(get_current_person)):
    if person["tier"] == "staff":
        raise HTTPException(403, "普通员工请在已有工作区派活；创建工作区请联系项目负责人")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name 必填")
    now = datetime.now().isoformat(timespec="seconds")
    wid = conn.execute(
        "INSERT INTO workspaces(name,type,scenario_id,created_by,created_at) VALUES(?,?,?,?,?)",
        (name, body.get("type", "临时"), body.get("scenario_id"), person["id"], now)).lastrowid
    conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                 (wid, "human", person["id"]))
    # 可选：初始成员 {"humans":[id...], "agents":[id...]}
    for pid in sorted(set(body.get("humans", [])) - {person["id"]}):
        if not conn.execute("SELECT 1 FROM people WHERE id=? AND status='在职'", (pid,)).fetchone():
            raise HTTPException(422, f"人员 #{pid} 不存在或已停用")
        conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                     (wid, "human", pid))
    for aid in sorted(set(body.get("agents", []))):
        if not conn.execute("SELECT 1 FROM agents WHERE id=?", (aid,)).fetchone():
            raise HTTPException(422, f"数字员工 #{aid} 不存在")
        conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                     (wid, "agent", aid))
    conn.execute(
        "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,created_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (wid, "system", None, "系统", "discussion", "text",
         f"工作区「{name}」由 {person['name']} 创建。", now))
    conn.commit()
    audit(conn, person["name"], "创建工作区", name)
    return {"id": wid, "name": name}


@router.get("/{wid}")
def get_workspace(wid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    row = conn.execute(
        "SELECT w.*, p.name creator_name, s.name scenario_name FROM workspaces w "
        "LEFT JOIN people p ON p.id=w.created_by LEFT JOIN scenarios s ON s.id=w.scenario_id "
        "WHERE w.id=?", (wid,)).fetchone()
    if not row:
        raise HTTPException(404, "工作区不存在")
    require_workspace(conn, wid, person)
    d = dict(row)
    d["members"] = _members(conn, wid)
    return d


@router.get("/{wid}/messages")
def list_messages(wid: int, zone: str = None, limit: int = 200, conn=Depends(db_conn),
                  person=Depends(get_current_person)):
    if not conn.execute("SELECT id FROM workspaces WHERE id=?", (wid,)).fetchone():
        raise HTTPException(404, "工作区不存在")
    require_workspace(conn, wid, person)
    sql = "SELECT * FROM messages WHERE workspace_id=?"
    args = [wid]
    if zone:
        sql += " AND zone=?"
        args.append(zone)
        if zone == "private":
            # 私聊仅发起者本人可见（历史 NULL owner 数据视为无效私聊，不展示）
            sql += " AND private_owner_id=?"
            args.append(person["id"])
    sql += " ORDER BY id ASC LIMIT ?"  # 按时间升序
    args.append(min(limit, 500))
    return [_msg_view(r) for r in conn.execute(sql, args)]


def _find_mentioned_agents(conn, wid, content):
    """从消息内容中识别本工作区 @数字员工（按名称最长匹配优先）"""
    agents = conn.execute(
        "SELECT a.id,a.name FROM workspace_members wm JOIN agents a ON a.id=wm.member_id "
        "WHERE wm.workspace_id=? AND wm.member_type='agent' AND a.status NOT IN ('已下线') "
        "ORDER BY LENGTH(a.name) DESC", (wid,)).fetchall()
    hits, seen = [], set()
    for a in agents:
        if f"@{a['name']}" in content and a["id"] not in seen:
            hits.append(a)
            seen.add(a["id"])
    return hits


@router.post("/{wid}/messages")
def post_message(wid: int, body: dict = Body(...), conn=Depends(db_conn),
                 person=Depends(get_current_person)):
    """发言；Agent 区支持 chat（连续模型对话）与 task（正式派活）两种模式。"""
    ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
    if not ws:
        raise HTTPException(404, "工作区不存在")
    require_workspace(conn, wid, person)
    content = (body.get("content") or "").strip()
    zone = body.get("zone", "discussion")
    if not content:
        raise HTTPException(400, "content 必填")
    if len(content) > 20000:
        raise HTTPException(422, "content 不能超过 20000 字符")
    if zone not in ("discussion", "agent", "private"):
        raise HTTPException(400, "zone 仅支持 discussion/agent/private")
    interaction_mode = body.get("interaction_mode")
    if interaction_mode is None:
        interaction_mode = "task"  # 兼容 R1-R5 客户端；R6 前端会显式传 chat
    if interaction_mode not in ("chat", "task"):
        raise HTTPException(422, "interaction_mode 仅支持 chat/task")

    # 触发数字员工：显式 @ / target_agent_id 优先；否则沿用本区可用数字员工。
    # 全部校验必须在消息落库之前完成，避免 422 时用户消息已发出。
    targets = _find_mentioned_agents(conn, wid, content)
    target_agent_id = body.get("target_agent_id")
    if target_agent_id and not targets:
        target = conn.execute(
            "SELECT a.id,a.name FROM workspace_members wm JOIN agents a ON a.id=wm.member_id "
            "WHERE wm.workspace_id=? AND wm.member_type='agent' AND a.id=? "
            "AND a.status NOT IN ('已下线')", (wid, target_agent_id)
        ).fetchone()
        if not target:
            raise HTTPException(422, "所选数字员工不是本工作区可用成员")
        targets = [target]
    if zone == "agent" and not targets:
        targets = [dict(r) for r in conn.execute(
            "SELECT a.id, a.name FROM workspace_members wm JOIN agents a ON a.id=wm.member_id "
            "WHERE wm.workspace_id=? AND wm.member_type='agent' AND a.status NOT IN ('已下线')", (wid,))]

    msg_id = conn.execute(
        "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,"
        "private_owner_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (wid, "human", person["id"], person["name"], zone, "text", content,
         person["id"] if zone == "private" else None,  # 私聊归发起者本人可见
         datetime.now().isoformat(timespec="seconds"))).lastrowid
    conn.commit()

    # 私聊区：不直接派活，由项目管理智能体把需求打磨成任务草稿并给出派活建议
    if zone == "private":
        reply_id = engine.private_assist(conn, wid, person, content)
        conn.commit()
        resp = {"message": _msg_view(conn.execute("SELECT * FROM messages WHERE id=?",
                                                  (msg_id,)).fetchone()),
                "dispatched": []}
        if reply_id:
            resp["reply"] = _msg_view(conn.execute("SELECT * FROM messages WHERE id=?",
                                                   (reply_id,)).fetchone())
        return resp

    dispatched, replies = [], []
    if interaction_mode == "chat":
        if not targets:
            message = (
                "当前工作区没有可用的数字员工，无法发起真实模型对话。"
                "请联系项目负责人将已启用的数字员工加入本工作区。"
            )
            engine._add_message(
                conn, wid, "system", None, "系统", "agent", "text", message,
                {"interaction_mode": "chat", "model_info": {
                    "ok": False, "reason": "工作区无可用数字员工",
                }},
            )
        else:
            for a in targets:
                reply = engine.chat_with_agent(conn, wid, a["id"], person, content)
                if reply:
                    replies.append(reply)
        conn.commit()
    else:
        for a in targets:
            task_id = engine.dispatch(conn, wid, a["id"], person["name"], content,
                                      creator_id=person["id"])
            if task_id:
                dispatched.append({"task_id": task_id, "agent_id": a["id"], "agent_name": a["name"]})
    if dispatched:
        audit(conn, person["name"], "派发任务", f"工作区#{wid}",
              f"派发 {len(dispatched)} 个任务：" + ",".join(str(t["task_id"]) for t in dispatched))
    if replies:
        audit(conn, person["name"], "数字员工模型对话", f"工作区#{wid}",
              "、".join(r["agent_name"] for r in replies))
    resp = {"message": _msg_view(conn.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()),
            "interaction_mode": interaction_mode, "dispatched": dispatched, "replies": replies}
    if zone == "agent" and interaction_mode == "chat" and not targets:
        resp["chat_error"] = "工作区无可用数字员工"
    # R5 兜底：agent 区发言未派发成功时，不静默成功——说明原因、推荐在线员工、登记待处理需求
    if zone == "agent" and interaction_mode == "task" and not dispatched:
        resp["undispatched"] = engine.handle_undispatched(conn, wid, person, content)
        conn.commit()
        audit(conn, person["name"], "派活兜底登记", f"工作区#{wid}",
              f"未派发，登记待处理任务 #{resp['undispatched']['pending_task_id']}")
    return resp


@router.get("/{wid}/chain")
def workspace_chain(wid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    """R4-6 执行链路（前端可视化）：过去（任务事件）→ 现在（进行中/待审核）→ 未来（流程后续 6 节点）"""
    if not conn.execute("SELECT id FROM workspaces WHERE id=?", (wid,)).fetchone():
        raise HTTPException(404, "工作区不存在")
    require_workspace(conn, wid, person)
    past, present = [], []
    tasks = conn.execute(
        "SELECT t.*, a.name agent_name FROM tasks t LEFT JOIN agents a ON a.id=t.agent_id "
        "WHERE t.workspace_id=? ORDER BY t.created_at, t.id", (wid,)).fetchall()
    for t in tasks:
        dmsgs = conn.execute(
            "SELECT created_at FROM messages WHERE workspace_id=? AND msg_type='deliverable' "
            "AND (payload LIKE ? OR payload LIKE ?) ORDER BY id",
            (wid, f'%"task_id": {t["id"]},%', f'%"task_id": {t["id"]}}}%')).fetchall()
        version = len(dmsgs) or (1 if t["deliverable"] else 0)
        base = {"type": "task_event", "task_id": t["id"],
                "agent_name": t["agent_name"] or "未指派", "version": version}
        past.append({**base, "time": t["created_at"], "title": f"任务创建：{t['title']}",
                     "status": "已创建"})
        if t["deliverable"]:
            past.append({**base, "time": dmsgs[0]["created_at"] if dmsgs else t["created_at"],
                         "title": f"交付物生成：{t['title']}", "status": "已交付"})
        if t["status"] == "已通过":
            past.append({**base, "time": t["done_at"] or t["created_at"],
                         "title": f"审核通过：{t['title']}", "status": "已通过"})
        elif t["status"] == "已驳回":
            past.append({**base,
                         "time": t["done_at"] or (dmsgs[-1]["created_at"] if dmsgs else t["created_at"]),
                         "title": f"审核驳回：{t['title']}", "status": "已驳回"})
        if t["status"] in ("进行中", "待审核"):
            present.append({"id": t["id"], "title": t["title"], "status": t["status"],
                            "agent_name": t["agent_name"] or "未指派",
                            "priority": t["priority"], "deadline": t["deadline"],
                            "version": version})
    past.sort(key=lambda e: e["time"] or "")

    flow = conn.execute(
        "SELECT * FROM project_flows WHERE workspace_id=? ORDER BY id DESC LIMIT 1",
        (wid,)).fetchone()
    future, flow_id = [], None
    if flow:
        flow_id = flow["id"]
        future = [{"code": n["code"], "title": n["title"], "role_name": n["role_name"],
                   "exec_type": n["exec_type"], "stage": n["stage"], "status": n["status"]}
                  for n in conn.execute(
                      "SELECT * FROM flow_nodes WHERE flow_id=? AND status<>'已完成' "
                      "ORDER BY stage, id LIMIT 6", (flow_id,))]
    return {"past": past, "present": present, "future": future, "flow_id": flow_id}
