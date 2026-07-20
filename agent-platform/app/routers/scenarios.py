"""场景清单：查询/敏捷立项申报/立项"""
import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _view(row):
    d = dict(row)
    try:
        d["actions"] = json.loads(d.get("actions") or "[]")
    except Exception:
        d["actions"] = []
    return d


@router.get("")
def list_scenarios(platform_id: int = None, dept_id: int = None, status: str = None,
                   priority: str = None, conn=Depends(db_conn),
                   person=Depends(get_current_person)):
    sql = ("SELECT s.*, d.name dept_name, d.platform_id, p.name platform_name, a.name agent_name "
           "FROM scenarios s JOIN departments d ON d.id=s.dept_id "
           "JOIN platforms p ON p.id=d.platform_id LEFT JOIN agents a ON a.id=s.agent_id")
    cond, args = [], []
    if platform_id:
        cond.append("d.platform_id=?")
        args.append(platform_id)
    if dept_id:
        cond.append("s.dept_id=?")
        args.append(dept_id)
    if status:
        cond.append("s.status=?")
        args.append(status)
    if priority:
        cond.append("s.priority=?")
        args.append(priority)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY s.id"
    return [_view(r) for r in conn.execute(sql, args)]


@router.post("")
def create_scenario(body: dict = Body(...), conn=Depends(db_conn),
                    person=Depends(get_current_person)):
    """敏捷立项申报：创建即为"待立项" """
    name = (body.get("name") or "").strip()
    dept_id = body.get("dept_id")
    if not name or not dept_id:
        raise HTTPException(400, "name 与 dept_id 必填")
    if not conn.execute("SELECT id FROM departments WHERE id=?", (dept_id,)).fetchone():
        raise HTTPException(404, "部门不存在")
    sid = conn.execute(
        "INSERT INTO scenarios(dept_id,agent_id,name,description,priority,batch,status,"
        "expected_benefit,actions) VALUES(?,?,?,?,?,?,'待立项',?,?)",
        (dept_id, body.get("agent_id"), name, body.get("description", ""),
         body.get("priority", "中"), body.get("batch", "扩围"), body.get("expected_benefit", ""),
         json.dumps(body.get("actions", []), ensure_ascii=False))).lastrowid
    conn.commit()
    audit(conn, person["name"], "立项申报", name, f"申报人 {person['name']} 提交敏捷立项申报")
    return _view(conn.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone())


@router.post("/{sid}/initiate")
def initiate_scenario(sid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    """立项：状态→已立项，自动建项目工作区并拉入关联 agent 与申请人"""
    sc = conn.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone()
    if not sc:
        raise HTTPException(404, "场景不存在")
    if sc["status"] != "待立项":
        raise HTTPException(400, f"当前状态为「{sc['status']}」，仅待立项场景可立项")

    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("UPDATE scenarios SET status='已立项' WHERE id=?", (sid,))
    wid = conn.execute(
        "INSERT INTO workspaces(name,type,scenario_id,created_by,created_at) VALUES(?,?,?,?,?)",
        (f"项目·{sc['name']}", "项目", sid, person["id"], now)).lastrowid
    conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                 (wid, "human", person["id"]))
    agent_name = None
    if sc["agent_id"]:
        conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                     (wid, "agent", sc["agent_id"]))
        a = conn.execute("SELECT name FROM agents WHERE id=?", (sc["agent_id"],)).fetchone()
        agent_name = a["name"] if a else None
    # system 消息 + 立项说明（human 主导节点）
    conn.execute(
        "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,payload,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (wid, "system", None, "系统", "discussion", "text",
         f"场景「{sc['name']}」已立项，项目工作区自动创建。", None, now))
    note = (f"立项说明：{sc['name']}\n背景与目标：{sc['description'] or '见场景清单'}\n"
            f"预期效益：{sc['expected_benefit'] or '待评估'}\n"
            f"责任数字员工：{agent_name or '待指派'}\n请项目组按敏捷方式推进，交付物须人工审核后生效。")
    conn.execute(
        "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,payload,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (wid, "human", person["id"], person["name"], "discussion", "text", note, None, now))
    conn.commit()
    audit(conn, person["name"], "场景立项", sc["name"], f"立项并自动创建工作区 #{wid}")
    ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
    return {"scenario": _view(conn.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone()),
            "workspace": dict(ws)}
