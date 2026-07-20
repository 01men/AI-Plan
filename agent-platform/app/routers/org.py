"""组织架构：平台-部门-人-数字员工 树"""
from fastapi import APIRouter, Depends, HTTPException

from app.routers.auth import db_conn, get_current_person, person_view

router = APIRouter(prefix="/api", tags=["org"])


@router.get("/org/tree", dependencies=[Depends(get_current_person)])
def org_tree(conn=Depends(db_conn)):
    """5 平台嵌套部门，部门含 people[] 与 agents[]（基本信息）"""
    platforms = [dict(r) for r in conn.execute("SELECT * FROM platforms ORDER BY id")]
    depts = [dict(r) for r in conn.execute("SELECT * FROM departments ORDER BY id")]
    people = [dict(r) for r in conn.execute(
        "SELECT id,dept_id,name,role_title,tier,direction,status FROM people ORDER BY id")]
    agents = [dict(r) for r in conn.execute(
        "SELECT id,dept_id,name,code,category,status,wave,tasks_done,hours_saved,accuracy FROM agents ORDER BY id")]
    for d in depts:
        d["people"] = [p for p in people if p["dept_id"] == d["id"]]
        d["agents"] = [a for a in agents if a["dept_id"] == d["id"]]
    for p in platforms:
        p["departments"] = [d for d in depts if d["platform_id"] == p["id"]]
    return platforms


@router.get("/people")
def list_people(tier: str = None, dept_id: int = None, conn=Depends(db_conn)):
    sql = ("SELECT p.*, d.name dept_name FROM people p JOIN departments d ON d.id=p.dept_id")
    cond, args = [], []
    if tier:
        cond.append("p.tier=?")
        args.append(tier)
    if dept_id:
        cond.append("p.dept_id=?")
        args.append(dept_id)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY p.id"
    return [dict(r) for r in conn.execute(sql, args)]


@router.get("/people/{pid}", dependencies=[Depends(get_current_person)])
def get_person(pid: int, conn=Depends(db_conn)):
    row = conn.execute("SELECT * FROM people WHERE id=?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "人员不存在")
    d = person_view(conn, row)
    # 名下数字员工
    d["agents"] = [dict(r) for r in conn.execute(
        "SELECT id,name,code,status,category FROM agents WHERE owner_id=?", (pid,))]
    return d
