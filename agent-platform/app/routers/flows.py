"""项目流程：查询（列表/详情）+ 人类动作（节点确认/阶段门签核）+ 手动 tick（演示用）"""
from fastapi import APIRouter, Body, Depends, HTTPException

from app import flow as flow_engine
from app.access import can_access_workspace, require_flow
from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/flows", tags=["flows"])


def _get_flow_or_404(conn, fid):
    f = flow_engine.get_flow(conn, fid)
    if not f:
        raise HTTPException(404, "流程不存在")
    return f


@router.get("")
def list_flows(status: str = None, conn=Depends(db_conn), person=Depends(get_current_person)):
    """流程列表：flow + 阶段进度百分比 + 当前阶段 + 门禁状态汇总 + 延迟主链路节点数"""
    sql = "SELECT * FROM project_flows"
    args = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY id"
    return [flow_engine.flow_summary(conn, f) for f in conn.execute(sql, args)
            if not f["workspace_id"] or can_access_workspace(conn, f["workspace_id"], person)]


@router.get("/{fid}")
def flow_detail(fid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    """流程完整详情：flow 信息 + 40 节点（全部字段）+ 4 门禁记录 + 主链路序列"""
    require_flow(conn, fid, person)
    f = _get_flow_or_404(conn, fid)
    return flow_engine.flow_detail(conn, f)


@router.post("/{fid}/tick")
def tick_flow(fid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    """手动触发一次自动推进（演示/调试用；heartbeat 也会自动调用）"""
    require_flow(conn, fid, person)
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管或教练团可手动推进项目流程")
    _get_flow_or_404(conn, fid)
    result = flow_engine.tick(conn, fid)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "推进失败"))
    codes = "、".join(p["code"] for p in result["processed"]) or "无（等待人工动作）"
    audit(conn, person["name"], "手动推进流程", f"flow#{fid}", f"tick 处理节点：{codes}")
    return result


@router.post("/{fid}/nodes/{code}/confirm")
def confirm_node(fid: int, code: str, body: dict = Body(default={}),
                 conn=Depends(db_conn), person=Depends(get_current_person)):
    """🤝节点确认生效 / 👤节点标记完成。权限：tier ∈ {boss, coach, backbone}"""
    if person["tier"] not in flow_engine.CONFIRM_TIERS:
        raise HTTPException(403, "仅 boss/coach/backbone 可确认流程节点")
    require_flow(conn, fid, person)
    f = _get_flow_or_404(conn, fid)
    node, err = flow_engine.confirm_node(conn, f, code.upper(), person,
                                         (body.get("comment") or "").strip())
    if err:
        raise HTTPException(err[0], err[1])
    audit(conn, person["name"], "流程节点确认", f"flow#{fid} {node['code']}",
          f"{node['title']} 确认生效")
    return {"ok": True, "node": dict(node)}


@router.post("/{fid}/gates/{gate}/sign")
def sign_gate(fid: int, gate: str, body: dict = Body(default={}),
              conn=Depends(db_conn), person=Depends(get_current_person)):
    """阶段门签核。权限：G1/G2/G4 仅 boss；G3 允许 boss/coach/backbone"""
    gate = gate.upper()
    if gate not in flow_engine.GATE_SIGN_TIERS:
        raise HTTPException(404, "阶段门不存在（应为 G1-G4）")
    if person["tier"] not in flow_engine.GATE_SIGN_TIERS[gate]:
        need = "/".join(sorted(flow_engine.GATE_SIGN_TIERS[gate]))
        raise HTTPException(403, f"{gate} 签核权限不足（要求 tier ∈ {{{need}}}）")
    require_flow(conn, fid, person)
    f = _get_flow_or_404(conn, fid)
    rec, err = flow_engine.sign_gate(conn, f, gate, person, (body.get("comment") or "").strip())
    if err:
        raise HTTPException(err[0], err[1])
    audit(conn, person["name"], "阶段门签核", f"flow#{fid} {gate}",
          f"签核通过" + (f"：{rec['comment']}" if rec["comment"] else ""))
    return {"ok": True, "gate": dict(rec)}
