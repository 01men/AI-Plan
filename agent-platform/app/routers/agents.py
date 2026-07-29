"""数字员工档案：列表/详情/状态维护/新建（R4-2 角色自定义 + MCP 绑定）"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person
from app.routers.mcp import expand_mcp, parse_mcp_ids
from app.seed import DEPT_CODE

router = APIRouter(prefix="/api/agents", tags=["agents"])

# 数字员工状态枚举（PATCH 仅允许这些值）
AGENT_STATUS_ALLOWED = ("规划中", "开发中", "试运行", "试点中", "已上线", "已下线")


def _view(row, conn=None):
    d = dict(row)
    for k in ("skills", "mcp_ids"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    if conn is not None:
        d["mcp"] = expand_mcp(conn, d["mcp_ids"])
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
    if person["tier"] == "staff":
        cond.append(
            "a.id IN (SELECT am.member_id FROM workspace_members am "
            "JOIN workspace_members hm ON hm.workspace_id=am.workspace_id "
            "WHERE am.member_type='agent' AND hm.member_type='human' AND hm.member_id=?)"
        )
        args.append(person["id"])
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
    if person["tier"] == "staff" and not conn.execute(
            "SELECT 1 FROM workspace_members am JOIN workspace_members hm "
            "ON hm.workspace_id=am.workspace_id WHERE am.member_type='agent' "
            "AND am.member_id=? AND hm.member_type='human' AND hm.member_id=?",
            (aid, person["id"])).fetchone():
        raise HTTPException(404, "数字员工不存在或不在您的工作区")
    d = _view(row, conn)
    # 绑定场景
    d["scenarios"] = [dict(r) for r in conn.execute(
        "SELECT id,name,status,priority,batch,expected_benefit FROM scenarios WHERE agent_id=?", (aid,))]
    # 近 14 天指标
    since = (datetime.now().date() - timedelta(days=13)).isoformat()
    d["metrics_14d"] = [dict(r) for r in conn.execute(
        "SELECT date,tasks_done,hours_saved,token_cost,accuracy FROM metrics_daily "
        "WHERE agent_id=? AND date>=? ORDER BY date", (aid, since))]
    # 最近 10 条任务
    recent_sql = (
        "SELECT id,workspace_id,title,status,priority,created_at,done_at FROM tasks "
        "WHERE agent_id=?"
    )
    recent_args = [aid]
    if person["tier"] not in ("boss", "coach"):
        recent_sql += (
            " AND (creator_id=? OR reviewer_id=? OR workspace_id IN ("
            "SELECT workspace_id FROM workspace_members "
            "WHERE member_type='human' AND member_id=?))"
        )
        recent_args.extend([person["id"], person["id"], person["id"]])
    recent_sql += " ORDER BY id DESC LIMIT 10"
    d["recent_tasks"] = [dict(r) for r in conn.execute(recent_sql, recent_args)]
    # R5：最近 5 次模型调用留痕（供应商/模型/耗时/成败/回退原因，供追溯）
    d["llm_calls"] = []
    if person["tier"] in ("boss", "coach") or row["owner_id"] == person["id"]:
        d["llm_calls"] = [dict(r) for r in conn.execute(
            "SELECT task_id,provider,model,status,latency_ms,error,fallback_reason,created_at "
            "FROM llm_calls WHERE agent_id=? ORDER BY id DESC LIMIT 5", (aid,))]
    return d


def _gen_code(conn, dept_name):
    """自动生成工号：优先沿用部门前缀 DE-{部门码}-{序号}，兜底 DE-C{自增 id}"""
    prefix = DEPT_CODE.get(dept_name)
    if prefix:
        idx = conn.execute(
            "SELECT COUNT(*) c FROM agents WHERE code LIKE ?", (f"DE-{prefix}-%",)).fetchone()["c"] + 1
        return f"DE-{prefix}-{idx:02d}"
    nid = (conn.execute("SELECT MAX(id) m FROM agents").fetchone()["m"] or 0) + 1
    return f"DE-C{nid:03d}"


@router.post("")
def create_agent(body: dict = Body(...), conn=Depends(db_conn),
                 person=Depends(get_current_person)):
    """新建数字员工：name/dept_id 必填，code 自动生成，可绑 skills/model_key/mcp_ids"""
    if person["tier"] not in ("boss", "coach", "developer"):
        raise HTTPException(403, "仅高管/教练团/开发者可新建数字员工")
    name = (body.get("name") or "").strip()
    dept_id = body.get("dept_id")
    if not name or not dept_id:
        raise HTTPException(400, "name 与 dept_id 必填")
    dept = conn.execute("SELECT * FROM departments WHERE id=?", (dept_id,)).fetchone()
    if not dept:
        raise HTTPException(404, "部门不存在")
    if person["tier"] == "developer" and dept_id != person["dept_id"]:
        raise HTTPException(403, "开发者只能在本人部门新建数字员工")
    owner_id = body.get("owner_id")
    if person["tier"] == "developer":
        owner_id = person["id"]
    elif owner_id and not conn.execute(
            "SELECT id FROM people WHERE id=? AND status='在职'", (owner_id,)).fetchone():
        raise HTTPException(404, "数字员工负责人不存在或已停用")
    skills = body.get("skills") or []
    if not isinstance(skills, list):
        raise HTTPException(422, "skills 需为数组")
    mcp_ids = parse_mcp_ids(body.get("mcp_ids"))
    for mid in mcp_ids:
        if not conn.execute("SELECT id FROM mcp_servers WHERE id=?", (mid,)).fetchone():
            raise HTTPException(404, f"MCP 服务不存在：{mid}")
    model_key = (body.get("model_key") or "").strip() or None
    if model_key and not conn.execute(
            "SELECT id FROM model_providers WHERE key=?", (model_key,)).fetchone():
        raise HTTPException(404, f"模型供应商不存在：{model_key}")
    try:
        wave = int(body.get("wave", 4))
    except (TypeError, ValueError):
        raise HTTPException(422, "wave 必须是 1-4 的整数")
    if wave not in (1, 2, 3, 4):
        raise HTTPException(422, "wave 必须是 1-4 的整数")
    aid = conn.execute(
        "INSERT INTO agents(dept_id,name,code,category,description,status,owner_id,wave,skills,"
        "tasks_done,hours_saved,accuracy,model_key,mcp_ids) VALUES(?,?,?,?,?,'规划中',?,?,?,0,0,0,?,?)",
        (dept_id, name, _gen_code(conn, dept["name"]), body.get("category", "通用"),
         body.get("description", ""), owner_id, wave,
         json.dumps(skills, ensure_ascii=False), model_key,
         json.dumps(mcp_ids, ensure_ascii=False))).lastrowid
    conn.commit()
    audit(conn, person["name"], "新建数字员工", name,
          f"部门：{dept['name']}，绑定 MCP {len(mcp_ids)} 个")
    return _view(conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone(), conn)


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
    if "dept_id" in body and not conn.execute(
            "SELECT id FROM departments WHERE id=?", (body["dept_id"],)).fetchone():
        raise HTTPException(404, "部门不存在")
    if "model_key" in body and body["model_key"] and not conn.execute(
            "SELECT id FROM model_providers WHERE key=?", (body["model_key"],)).fetchone():
        raise HTTPException(404, f"模型供应商不存在：{body['model_key']}")
    if "owner_id" in body and body["owner_id"] and not conn.execute(
            "SELECT id FROM people WHERE id=? AND status='在职'", (body["owner_id"],)).fetchone():
        raise HTTPException(404, "数字员工负责人不存在或已停用")
    if "wave" in body:
        try:
            body["wave"] = int(body["wave"])
        except (TypeError, ValueError):
            raise HTTPException(422, "wave 必须是 1-4 的整数")
        if body["wave"] not in (1, 2, 3, 4):
            raise HTTPException(422, "wave 必须是 1-4 的整数")
    if "accuracy" in body:
        try:
            body["accuracy"] = float(body["accuracy"])
        except (TypeError, ValueError):
            raise HTTPException(422, "accuracy 必须是 0-100 的数字")
        if not 0 <= body["accuracy"] <= 100:
            raise HTTPException(422, "accuracy 必须在 0-100 之间")
    allowed = {"status", "description", "owner_id", "wave", "accuracy", "category", "name",
               "dept_id", "model_key"}
    sets, args = [], []
    for k, v in body.items():
        if k in allowed:
            sets.append(f"{k}=?")
            args.append(v)
        elif k == "skills":  # skills 允许传数组，落库为 JSON 字符串
            if not isinstance(v, list):
                raise HTTPException(422, "skills 需为数组")
            sets.append("skills=?")
            args.append(json.dumps(v, ensure_ascii=False))
        elif k == "mcp_ids":  # mcp_ids 同样传数组落 JSON
            parsed_ids = parse_mcp_ids(v)
            for mid in parsed_ids:
                if not conn.execute("SELECT id FROM mcp_servers WHERE id=?", (mid,)).fetchone():
                    raise HTTPException(404, f"MCP 服务不存在：{mid}")
            sets.append("mcp_ids=?")
            args.append(json.dumps(parsed_ids, ensure_ascii=False))
    if not sets:
        raise HTTPException(400, "没有可更新的字段")
    args.append(aid)
    conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE id=?", args)
    conn.commit()
    audit(conn, person["name"], "更新数字员工", row["name"], f"更新字段：{','.join(body.keys())}")
    return _view(conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone(), conn)
