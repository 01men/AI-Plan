"""知识库：NAS 空间与文档"""
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/spaces")
def list_spaces(conn=Depends(db_conn), person=Depends(get_current_person)):
    out = []
    for r in conn.execute("SELECT * FROM knowledge_spaces ORDER BY id"):
        d = dict(r)
        d["doc_count"] = conn.execute(
            "SELECT COUNT(*) c FROM documents WHERE space_id=?", (r["id"],)).fetchone()["c"]
        out.append(d)
    return out


@router.get("/documents")
def list_documents(space_id: int = None, level: str = None, conn=Depends(db_conn),
                   person=Depends(get_current_person)):
    sql = "SELECT d.*, s.name space_name FROM documents d JOIN knowledge_spaces s ON s.id=d.space_id"
    cond, args = [], []
    if space_id:
        cond.append("d.space_id=?")
        args.append(space_id)
    if level:
        cond.append("d.level=?")
        args.append(level)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY d.id"
    return [dict(r) for r in conn.execute(sql, args)]


@router.post("/documents")
def create_document(body: dict = Body(...), conn=Depends(db_conn),
                    person=Depends(get_current_person)):
    title = (body.get("title") or "").strip()
    space_id = body.get("space_id")
    if not title or not space_id:
        raise HTTPException(400, "title 与 space_id 必填")
    if not conn.execute("SELECT id FROM knowledge_spaces WHERE id=?", (space_id,)).fetchone():
        raise HTTPException(404, "知识空间不存在")
    did = conn.execute(
        "INSERT INTO documents(space_id,title,level,tags,uploaded_by,created_at) VALUES(?,?,?,?,?,?)",
        (space_id, title, body.get("level", "L1"), body.get("tags", ""), person["name"],
         datetime.now().isoformat(timespec="seconds"))).lastrowid
    conn.commit()
    audit(conn, person["name"], "上传文档", title, f"空间 #{space_id}")
    return dict(conn.execute("SELECT * FROM documents WHERE id=?", (did,)).fetchone())
