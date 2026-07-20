"""KPI 看板指标"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from app.routers.auth import db_conn, get_current_person

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# 首年投入与效益（来自行动方案，单位：元）
INVESTMENT_YEAR1 = 342895.6
INVESTMENT_BREAKDOWN = {
    "算力资源": 137895.6,
    "NAS知识库底座": 105000.0,
    "创新激励奖金池": 100000.0,
}
# 各科目明细（方案口径，单位：元）
INVESTMENT_BREAKDOWN_DETAIL = {
    "算力资源": {"阿里云节省计划": 23850.0, "智谱团队套餐": 84045.6, "个性化灵活采购": 30000.0},
    "NAS知识库底座": {"采购": 95000.0, "运维预留": 10000.0},
    "创新激励奖金池": {},
}
BENEFIT_DIRECT = 540000
BENEFIT_TOTAL = 790000
ROI_YEAR1_PCT = 57.5
ROI_YEAR2_PCT = 117.8


@router.get("/dashboard")
def dashboard(conn=Depends(db_conn), person=Depends(get_current_person)):
    total_sc = conn.execute("SELECT COUNT(*) c FROM scenarios").fetchone()["c"]
    # 覆盖率（方案口径）：已验收场景 / 场景总数
    accepted_sc = conn.execute("SELECT COUNT(*) c FROM scenarios WHERE status='已验收'").fetchone()["c"]
    coverage = round(accepted_sc / total_sc * 100, 1) if total_sc else 0
    # 试点覆盖率：试点中+已验收 / 场景总数（原口径数值）
    trial_sc = conn.execute(
        "SELECT COUNT(*) c FROM scenarios WHERE status IN ('试点中','已验收')").fetchone()["c"]
    trial_coverage = round(trial_sc / total_sc * 100, 1) if total_sc else 0

    approved = conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='已通过'").fetchone()["c"]
    rejected = conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='已驳回'").fetchone()["c"]
    acceptance_rate = round(approved / (approved + rejected) * 100, 1) if approved + rejected else 0

    total_agents = conn.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"]
    since7 = (datetime.now().date() - timedelta(days=6)).isoformat()
    active_agents = conn.execute(
        "SELECT COUNT(DISTINCT agent_id) c FROM metrics_daily WHERE date>=? AND tasks_done>0",
        (since7,)).fetchone()["c"]
    active_rate = round(active_agents / total_agents * 100, 1) if total_agents else 0

    hours_saved = conn.execute("SELECT ROUND(COALESCE(SUM(hours_saved),0),1) s FROM agents").fetchone()["s"]
    acc = conn.execute("SELECT ROUND(AVG(accuracy),1) a FROM agents WHERE accuracy>0").fetchone()["a"] or 0

    # Skill 复用次数：被数字员工引用的 Skill 总数（去重）
    reuse = set()
    for r in conn.execute("SELECT skills FROM agents"):
        try:
            reuse.update(json.loads(r["skills"] or "[]"))
        except Exception:
            pass

    # 四波次分布
    waves = []
    for w in (1, 2, 3, 4):
        rows = conn.execute("SELECT status, COUNT(*) c FROM agents WHERE wave=? GROUP BY status", (w,))
        by_status = {r["status"]: r["c"] for r in rows}
        waves.append({"wave": w, "total": sum(by_status.values()), "by_status": by_status})

    leaderboard = [dict(r) for r in conn.execute(
        "SELECT id,name,code,status,tasks_done,hours_saved,accuracy FROM agents "
        "ORDER BY tasks_done DESC, hours_saved DESC LIMIT 8")]

    # 近 14 天趋势（缺的日期补 0）
    today = datetime.now().date()
    day_map = {(today - timedelta(days=13 - i)).isoformat(): {"tasks_done": 0, "hours_saved": 0.0}
               for i in range(14)}
    for r in conn.execute(
            "SELECT date, SUM(tasks_done) t, ROUND(SUM(hours_saved),1) h FROM metrics_daily "
            "WHERE date>=? GROUP BY date", ((today - timedelta(days=13)).isoformat(),)):
        if r["date"] in day_map:
            day_map[r["date"]] = {"tasks_done": r["t"], "hours_saved": r["h"]}
    trend = [{"date": d, **v} for d, v in sorted(day_map.items())]

    feed = [dict(r) for r in conn.execute(
        "SELECT m.id, m.workspace_id, w.name workspace_name, m.sender_type, m.sender_name,"
        " m.zone, m.msg_type, m.content, m.created_at FROM messages m "
        "JOIN workspaces w ON w.id=m.workspace_id "
        "WHERE m.sender_type IN ('system','agent') ORDER BY m.id DESC LIMIT 12")]

    return {
        "kpi": {
            "coverage": {"value": coverage, "note": "已验收场景/场景总数"},
            "trial_coverage": {"value": trial_coverage, "note": "试点中+已验收/场景总数"},
            "acceptance_rate": {"value": acceptance_rate, "note": "审核通过数/已审核数"},
            "active_rate": {"value": active_rate, "note": "近7日有产出数字员工/已上线+试运行"},
            "hours_saved": {"value": hours_saved, "note": "累计审核通过折算工时"},
            "accuracy": {"value": acc, "note": "近30日平均准确率"},
            "annual_benefit": {"value": BENEFIT_TOTAL, "note": "已验收场景预期年化收益合计"},
            "reuse_count": {"value": len(reuse), "note": "被数字员工引用的 Skill 总数（去重）"},
        },
        "investment": {"year1": INVESTMENT_YEAR1, "breakdown": INVESTMENT_BREAKDOWN,
                       "breakdown_detail": INVESTMENT_BREAKDOWN_DETAIL},
        "benefit": {"direct": BENEFIT_DIRECT, "total": BENEFIT_TOTAL,
                    "roi_year1_pct": ROI_YEAR1_PCT, "roi_year2_pct": ROI_YEAR2_PCT},
        "waves": waves,
        "leaderboard": leaderboard,
        "trend": trend,
        "feed": feed,
    }


@router.get("/agents")
def agent_metrics(conn=Depends(db_conn), person=Depends(get_current_person)):
    return [dict(r) for r in conn.execute(
        "SELECT a.id, a.name, a.code, a.status, a.wave, d.name dept_name, a.tasks_done,"
        " a.hours_saved, a.accuracy FROM agents a JOIN departments d ON d.id=a.dept_id "
        "ORDER BY a.tasks_done DESC")]
