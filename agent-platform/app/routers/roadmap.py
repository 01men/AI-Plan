"""路线图：三阶段 + 里程碑 + 四波次排期"""
from fastapi import APIRouter, Depends

from app.routers.auth import db_conn, get_current_person

router = APIRouter(prefix="/api", tags=["roadmap"])

PHASES = [
    {"name": "筑基期", "period": "2026.8-2026.9",
     "description": "搭底座：NAS 知识库部署、五大保障机制发布、教练团组建培训、首批 5 场景立项与 MVP 开发，"
                    "覆盖率自动统计上线并完成第一轮达标扩围。"},
    {"name": "推广期", "period": "2026.10-2026.11",
     "description": "扩场景：第二、三轮扩围，标杆项目打造与固化，周报月报自动归档，月度成果分享，"
                    "数字员工覆盖研发与质量平台。"},
    {"name": "深化期", "period": "2026.12",
     "description": "固成果：年终复盘与考核、激励兑现、2027 年度规划，形成可复制的 AI 原生运营模式。"},
]

WAVE_DESC = {
    1: "第一波（2026.8）：战略平台 + 营销核心（营销商务部/国际销售部），含首批试点",
    2: "第二波（2026.9）：营销深化 + 智造平台（生产/采购/生管/品管等）",
    3: "第三波（2026.10）：研发平台 + 质量平台",
    4: "第四波（2026.11 起）：其余部门补全，全面覆盖",
}


@router.get("/roadmap")
def roadmap(conn=Depends(db_conn), person=Depends(get_current_person)):
    milestones = [dict(r) for r in conn.execute("SELECT * FROM milestones ORDER BY id")]
    waves = []
    for w in (1, 2, 3, 4):
        cnt = conn.execute("SELECT COUNT(*) c FROM agents WHERE wave=?", (w,)).fetchone()["c"]
        waves.append({"wave": w, "description": WAVE_DESC[w], "agent_count": cnt})
    return {"phases": PHASES, "milestones": milestones, "waves": waves}
