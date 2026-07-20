"""协作工作区：三区消息 + @数字员工派活"""
import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app import engine
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
            r = conn.execute("SELECT name FROM agents WHERE id=?", (m["member_id"],)).fetchone()
        d["name"] = r["name"] if r else f"{m['member_type']}#{m['member_id']}"
        out.append(d)
    return out


@router.get("")
def list_workspaces(type: str = None, conn=Depends(db_conn), person=Depends(get_current_person)):
    sql = ("SELECT w.*, p.name creator_name, s.name scenario_name FROM workspaces w "
           "LEFT JOIN people p ON p.id=w.created_by LEFT JOIN scenarios s ON s.id=w.scenario_id")
    args = []
    if type:
        sql += " WHERE w.type=?"
        args.append(type)
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
    for pid in body.get("humans", []):
        conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                     (wid, "human", pid))
    for aid in body.get("agents", []):
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
    d = dict(row)
    d["members"] = _members(conn, wid)
    return d


@router.get("/{wid}/messages")
def list_messages(wid: int, zone: str = None, limit: int = 200, conn=Depends(db_conn),
                  person=Depends(get_current_person)):
    if not conn.execute("SELECT id FROM workspaces WHERE id=?", (wid,)).fetchone():
        raise HTTPException(404, "工作区不存在")
    sql = "SELECT * FROM messages WHERE workspace_id=?"
    args = [wid]
    if zone:
        sql += " AND zone=?"
        args.append(zone)
    sql += " ORDER BY id ASC LIMIT ?"  # 按时间升序
    args.append(limit)
    return [_msg_view(r) for r in conn.execute(sql, args)]


def _find_mentioned_agents(conn, content):
    """从消息内容中识别 @数字员工（按名称最长匹配优先）"""
    agents = conn.execute(
        "SELECT id,name FROM agents WHERE status NOT IN ('已下线') ORDER BY LENGTH(name) DESC").fetchall()
    hits, seen = [], set()
    for a in agents:
        if f"@{a['name']}" in content and a["id"] not in seen:
            hits.append(a)
            seen.add(a["id"])
    return hits


@router.post("/{wid}/messages")
def post_message(wid: int, body: dict = Body(...), conn=Depends(db_conn),
                 person=Depends(get_current_person)):
    """发言；zone=='agent' 或内容 @数字员工 时触发数字员工执行"""
    ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
    if not ws:
        raise HTTPException(404, "工作区不存在")
    content = (body.get("content") or "").strip()
    zone = body.get("zone", "discussion")
    if not content:
        raise HTTPException(400, "content 必填")
    if zone not in ("discussion", "agent", "private"):
        raise HTTPException(400, "zone 仅支持 discussion/agent/private")

    msg_id = conn.execute(
        "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,created_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (wid, "human", person["id"], person["name"], zone, "text", content,
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

    # 触发数字员工：显式 @ 优先；agent 区无 @ 时派给工作区内全部数字员工成员
    targets = _find_mentioned_agents(conn, content)
    if zone == "agent" and not targets:
        targets = [dict(r) for r in conn.execute(
            "SELECT a.id, a.name FROM workspace_members wm JOIN agents a ON a.id=wm.member_id "
            "WHERE wm.workspace_id=? AND wm.member_type='agent' AND a.status NOT IN ('已下线')", (wid,))]
    dispatched = []
    for a in targets:
        task_id = engine.dispatch(conn, wid, a["id"], person["name"], content,
                                  creator_id=person["id"])
        if task_id:
            dispatched.append({"task_id": task_id, "agent_id": a["id"], "agent_name": a["name"]})
    if dispatched:
        audit(conn, person["name"], "派发任务", f"工作区#{wid}",
              f"派发 {len(dispatched)} 个任务：" + ",".join(str(t["task_id"]) for t in dispatched))
    return {"message": _msg_view(conn.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()),
            "dispatched": dispatched}
