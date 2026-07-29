"""服务端最小权限策略。

前端隐藏只是体验优化，所有敏感资源必须在这里做服务端授权。
"""
from fastapi import HTTPException

GLOBAL_TIERS = ("boss", "coach")


def _person_dept_id(conn, person) -> int | None:
    if isinstance(person, dict) and person.get("dept_id"):
        return person["dept_id"]
    try:
        return person["dept_id"]
    except Exception:
        row = conn.execute("SELECT dept_id FROM people WHERE id=?", (person["id"],)).fetchone()
        return row["dept_id"] if row else None


def is_workspace_member(conn, wid: int, person_id: int) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id=? "
        "AND member_type='human' AND member_id=?",
        (wid, person_id),
    ).fetchone())


def can_access_workspace(conn, wid: int, person) -> bool:
    if person["tier"] in GLOBAL_TIERS:
        return True
    if is_workspace_member(conn, wid, person["id"]):
        return True
    if person["tier"] == "backbone":
        dept_id = _person_dept_id(conn, person)
        return bool(conn.execute(
            "SELECT 1 FROM workspaces w JOIN scenarios s ON s.id=w.scenario_id "
            "WHERE w.id=? AND s.dept_id=?",
            (wid, dept_id),
        ).fetchone())
    return False


def require_workspace(conn, wid: int, person):
    row = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
    if not row:
        raise HTTPException(404, "工作区不存在")
    if not can_access_workspace(conn, wid, person):
        # 不向越权用户泄露资源是否真实存在。
        raise HTTPException(404, "工作区不存在或无权访问")
    return row


def workspace_scope_sql(person, alias: str = "w") -> tuple[str, list]:
    if person["tier"] in GLOBAL_TIERS:
        return "", []
    if person["tier"] == "backbone":
        return (
            f"({alias}.id IN (SELECT workspace_id FROM workspace_members "
            "WHERE member_type='human' AND member_id=?) OR "
            f"{alias}.scenario_id IN (SELECT id FROM scenarios WHERE dept_id=?))",
            [person["id"], person["dept_id"]],
        )
    return (
        f"{alias}.id IN (SELECT workspace_id FROM workspace_members "
        "WHERE member_type='human' AND member_id=?)",
        [person["id"]],
    )


def can_access_task(conn, task, person) -> bool:
    if person["tier"] in GLOBAL_TIERS:
        return True
    if task["creator_id"] == person["id"] or task["reviewer_id"] == person["id"]:
        return True
    return bool(task["workspace_id"] and
                can_access_workspace(conn, task["workspace_id"], person))


def require_task(conn, tid: int, person):
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        raise HTTPException(404, "任务不存在")
    if not can_access_task(conn, row, person):
        raise HTTPException(404, "任务不存在或无权访问")
    return row


def require_flow(conn, fid: int, person):
    row = conn.execute("SELECT * FROM project_flows WHERE id=?", (fid,)).fetchone()
    if not row:
        raise HTTPException(404, "流程不存在")
    if row["workspace_id"] and not can_access_workspace(conn, row["workspace_id"], person):
        raise HTTPException(404, "项目流程不存在或无权访问")
    return row


def can_access_document(person, level: str, space_dept: str) -> bool:
    level = (level or "L1").upper()
    if level in ("L1", "L2"):
        return True
    if person["tier"] in GLOBAL_TIERS:
        return True
    same_dept = (person.get("dept_name") or "") == (space_dept or "")
    if level == "L3":
        return same_dept
    return same_dept and person["tier"] == "backbone"


def require_document(conn, did: int, person):
    row = conn.execute(
        "SELECT d.*,s.name space_name,s.dept_name space_dept FROM documents d "
        "JOIN knowledge_spaces s ON s.id=d.space_id WHERE d.id=?",
        (did,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    if not can_access_document(person, row["level"], row["space_dept"]):
        raise HTTPException(403, f"您无权访问该 {row['level'] or 'L1'} 文档")
    return row
