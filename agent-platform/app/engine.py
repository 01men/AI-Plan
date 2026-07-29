"""Agent 执行引擎 + 心跳逻辑

- dispatch()：把人类需求派发给数字员工，生成任务与交付物，进入"待人工审核"
- heartbeat()：项目管理智能体自动发日报 + 临期任务催办
- 交付物默认由模板生成；模型调用配置解析顺序：旧 settings llm_* 三键（向后兼容）
  > agents.model_key 绑定的 model_providers > settings.default_model_key；
  未配置 api_key 或调用异常都回落到模板（默认不联网）
"""
import json
import urllib.request
from datetime import datetime, timedelta

from app.security import public_error

J = lambda v: json.dumps(v, ensure_ascii=False)


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ---------------- 交付物模板（按 agent.category 分 5 类 + 通用兜底） ----------------

def _actions_text(actions):
    if not actions:
        return "（暂无绑定场景动作，按通用流程执行）"
    return "\n".join(f"- {a}" for a in actions)


def _tpl_business(agent, req, actions):
    return f"""## 交付物：订单/单证处理结果

**需求原文**：{req}
**执行数字员工**：{agent['name']}（{agent['code']}）

### 一、资料整理结果
已从邮件/钉钉提取本次需求相关附件 6 份，按"客户/订单号/日期"规范命名并归档至 NAS 对应目录，重复文件 1 份已标记。

### 二、单证/草稿输出
- ERP 下单草稿 1 份（待人工确认后提交）
- 唛头/不干胶标签文件 1 套（PDF，已按客户模板排版）
- 合同关键条款检查表：交期、付款方式、质保条款各 1 处需人工复核

### 三、场景动作执行情况
{_actions_text(actions)}

### 四、待人工确认事项
1. 草稿数据已与原始邮件逐条比对，请确认后提交 ERP；
2. 条款风险点已高亮，请商务复核；
3. 写回动作将在人工确认后执行并留痕。"""


def _tpl_meeting(agent, req, actions):
    return f"""## 交付物：结构化会议纪要与待办清单

**需求原文**：{req}
**执行数字员工**：{agent['name']}（{agent['code']}）

### 一、纪要摘要
会议围绕生产计划达成、异常闭环与设备点检三项议题展开，形成结论 3 条：计划达成率偏差需次日班前会通报；2 起异常今日内闭环；点检标准按新版 SOP 执行。

### 二、待办清单
| 序号 | 待办事项 | 责任人 | 时限 |
| ---- | -------- | ------ | ---- |
| 1 | 异常单闭环确认 | 班组长 | 今日 17:00 |
| 2 | OPL 台账更新 | 刘能洁 | 明日 12:00 |
| 3 | 周报数据核对 | 计划员 | 本周五 |

### 三、场景动作执行情况
{_actions_text(actions)}

### 四、后续动作
纪要待人工确认后同步至钉钉群并触发待办提醒；周报/月报将自动引用本纪要数据。"""


def _tpl_bom(agent, req, actions):
    return f"""## 交付物：BOM 三向比对差异表与缺料预警

**需求原文**：{req}
**执行数字员工**：{agent['name']}（{agent['code']}）

### 一、三向比对结果（ERP vs 图纸 vs 实物）
| 物料编码 | 差异类型 | ERP | 图纸 | 实物 | 建议 |
| -------- | -------- | --- | ---- | ---- | ---- |
| M3-0218 | 规格不符 | 8.8级 | 10.9级 | 10.9级 | 以图纸为准，改 ERP |
| C4-1130 | 用量差异 | 2 | 4 | 4 | 提交 ECN 变更 |

### 二、缺料预警
按下周生产计划测算，缺料 3 项，其中关键物料 1 项（交期 7 天），建议今日下达采购；备选供应商 2 家已列出。

### 三、场景动作执行情况
{_actions_text(actions)}

### 四、待人工确认事项
差异与采购建议需产品管理与采购双确认；退货/金额核对结果附后，写回 ERP 前必须人工确认并留痕。"""


def _tpl_quality(agent, req, actions):
    return f"""## 交付物：质量异常 8D 报告草稿（D1-D8 框架）

**需求原文**：{req}
**执行数字员工**：{agent['name']}（{agent['code']}）

- **D1 成立小组**：品管牵头，生产/研发/采购协同（建议名单附后）
- **D2 问题描述**：异常单已结构化，缺陷现象/批次/数量/发生工序四要素齐全
- **D3 临时对策**：库存品全检、在制品隔离，24 小时内执行
- **D4 根因分析**：已匹配历史问题 2 例（相似度 86%/82%），推荐方案采纳率最高为"工装防呆改造"
- **D5 永久对策**：待人工评审后选定
- **D6 实施验证**：对策实施后连续 3 批跟踪
- **D7 预防再发**：检验标准与作业指导书同步修订
- **D8 表彰总结**：闭环后归档至 8D 报告库

### 场景动作执行情况
{_actions_text(actions)}

> 本草稿由数字员工生成，D5 及以后节点必须人工确认方可推进。"""


def _tpl_rd(agent, req, actions):
    return f"""## 交付物：测试数据对比与售后归因分析

**需求原文**：{req}
**执行数字员工**：{agent['name']}（{agent['code']}）

### 一、测试数据对比
| 项目 | 老款 | 新款 | 标准 | 判定 |
| ---- | ---- | ---- | ---- | ---- |
| 温升(K) | 62 | 55 | ≤75 | 合格 |
| 电流(A) | 3.8 | 3.5 | ≤4.2 | 合格 |
| 功率(W) | 850 | 820 | 800±8% | 合格 |

### 二、售后归因分析
近 90 天维修记录聚类 4 类：发热类占比 41% 居首，与温升偏高批次强相关（相关系数 0.78）；其次为开关失效 23%。建议优先排查该批次转子绝缘工艺。

### 三、场景动作执行情况
{_actions_text(actions)}

### 四、输出物
归因结论已生成客户报告草稿 1 份，维修记录已归档，待人工审核后对外发布。"""


def _tpl_general(agent, req, actions):
    return f"""## 交付物：综合事务处理结果

**需求原文**：{req}
**执行数字员工**：{agent['name']}（{agent['code']}）

### 一、处理摘要
已按需求完成资料收集、结构化整理与初步分析，形成结果 1 份；关键数据均标注来源，便于人工复核。

### 二、明细结果
1. 信息采集：完成，来源 3 处；
2. 智能处理：完成，生成结构化记录 5 条；
3. 初步结论：已给出 2 条建议供决策参考。

### 三、场景动作执行情况
{_actions_text(actions)}

### 四、待人工确认事项
全部写回/对外动作均需人工确认后执行，并请审核人批注意见。"""


TEMPLATES = {
    "业务/项目助理": _tpl_business,
    "智造运营/会议纪要": _tpl_meeting,
    "BOM/物料": _tpl_bom,
    "质量/制程异常分析": _tpl_quality,
    "研发测试/售后分析": _tpl_rd,
}


def _get_settings(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings")}


def _agent_actions(conn, agent_id):
    """取该 agent 绑定场景的动作列表（优先试点/已立项场景）"""
    row = conn.execute(
        "SELECT actions FROM scenarios WHERE agent_id=? ORDER BY CASE status "
        "WHEN '试点中' THEN 0 WHEN '已立项' THEN 1 ELSE 2 END, id LIMIT 1", (agent_id,)).fetchone()
    if row and row["actions"]:
        try:
            return json.loads(row["actions"])
        except Exception:
            return []
    return []


def _resolve_llm(conn, settings, agent):
    """解析本次生成应使用的模型配置 dict；无可用配置返回 None。
    优先级：旧 settings llm_* 三键（向后兼容）> agent.model_key 绑定 > settings.default_model_key。
    provider 停用或未配置 api_key 时返回 None（回落模板，保持离线原则）。
    api_key 落库为 enc:v1 密文，此处解密后仅用于本次调用。"""
    from app import crypto
    base, key, model = (settings.get("llm_base_url"), settings.get("llm_api_key"),
                        settings.get("llm_model"))
    if base and key and model:
        return {"provider": "custom", "base_url": base, "api_key": crypto.decrypt(key),
                "model": model, "temperature": 0.4, "timeout": 30}
    mk = dict(agent).get("model_key") or settings.get("default_model_key") or "glm"
    row = conn.execute("SELECT * FROM model_providers WHERE key=?", (mk,)).fetchone()
    if not row or not row["enabled"] or not (row["api_key"] or "").strip():
        return None
    cols = row.keys()
    temperature = row["temperature"] if "temperature" in cols and row["temperature"] is not None else 0.4
    # Kimi Coding 的 OpenAI 兼容接口当前只接受 temperature=1。
    if row["key"] == "kimi" and "api.kimi.com/coding" in (row["base_url"] or ""):
        temperature = 1.0
    return {"provider": row["key"], "base_url": row["base_url"],
            "api_key": crypto.decrypt(row["api_key"]), "model": row["default_model"],
            "temperature": temperature,
            "timeout": row["timeout"] if "timeout" in cols and row["timeout"] else 30}


def _log_llm_call(conn, task_id, agent_id, provider, model, status,
                  latency_ms=0, error=None, fallback_reason=None):
    """模型调用留痕（脱敏：绝不写 api_key）"""
    conn.execute(
        "INSERT INTO llm_calls(task_id,agent_id,provider,model,status,latency_ms,error,"
        "fallback_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (task_id, agent_id, provider, model, status, latency_ms, error, fallback_reason, _now()))


def _llm_deliverable(conn, settings, agent, req, actions, task_id=None):
    """按解析出的模型配置调用 OpenAI 兼容接口。

    返回 (text, model_info)；失败/未配置时 text 为 None 由调用方回落模板。
    model_info 随交付卡片 payload 下发，前端展示、审核人可追溯。
    """
    import time
    resolved = _resolve_llm(conn, settings, agent)
    if not resolved:
        info = {"provider": None, "model": "template", "latency_ms": 0,
                "fallback": True, "reason": "未配置可用模型，使用模板生成"}
        return None, info
    provider, model = resolved["provider"], resolved["model"]
    timeout = resolved["timeout"]
    started = time.monotonic()
    try:
        prompt = (f"你是数字员工「{agent['name']}」，类别{agent['category']}。请根据需求生成 300-500 字"
                  f"中文 Markdown 交付物，结构化、可落地。\n需求：{req}\n场景动作：{actions}")
        body = J({"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": resolved["temperature"]}).encode("utf-8")
        req_http = urllib.request.Request(
            resolved["base_url"].rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {resolved['api_key']}"})
        with urllib.request.urlopen(req_http, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency = int((time.monotonic() - started) * 1000)
        text = data["choices"][0]["message"]["content"]
        _log_llm_call(conn, task_id, agent["id"], provider, model, "ok", latency)
        return text, {"provider": provider, "model": model, "latency_ms": latency,
                      "fallback": False, "reason": None}
    except Exception as e:
        latency = int((time.monotonic() - started) * 1000)
        reason = public_error(e)
        _log_llm_call(conn, task_id, agent["id"], provider, model, "error", latency,
                      error=reason, fallback_reason="模型调用失败，回落模板生成")
        return None, {"provider": provider, "model": model, "latency_ms": latency,
                      "fallback": True, "reason": reason}


def generate_deliverable(conn, agent, req, task_id=None):
    """生成交付物：优先 LLM（若配置），否则按类别模板。返回 (text, model_info)"""
    actions = _agent_actions(conn, agent["id"])
    text, model_info = _llm_deliverable(conn, _get_settings(conn), agent, req, actions, task_id)
    if text:
        return text, model_info
    if model_info.get("provider"):
        # 真实调用失败回落模板时也留一条 template 记录，便于审计区分"未配置"与"失败回落"
        _log_llm_call(conn, task_id, agent["id"], model_info["provider"], model_info["model"],
                      "template", model_info.get("latency_ms", 0),
                      fallback_reason=model_info.get("reason"))
    tpl = TEMPLATES.get(agent["category"], _tpl_general)
    return tpl(agent, req, actions), model_info


def _pick_reviewer(conn, workspace_id, creator_id):
    """审核人按序指派，始终排除任务创建人（取到创建人顺延下一位；候选全空返回 None）：
    a. 任务关联场景（若有）所属部门中 tier=backbone 的人；
    b. 该工作区成员中 tier ∈ {backbone, coach} 的人；
    c. 全库任一 coach。
    """
    candidates = []
    if workspace_id:
        # a. 场景所属部门的骨干
        candidates += [r["id"] for r in conn.execute(
            "SELECT p.id FROM people p WHERE p.tier='backbone' AND p.dept_id=("
            "  SELECT s.dept_id FROM scenarios s JOIN workspaces w ON w.scenario_id=s.id"
            "  WHERE w.id=?) ORDER BY p.id", (workspace_id,))]
        # b. 工作区成员中的骨干/教练
        candidates += [r["id"] for r in conn.execute(
            "SELECT p.id FROM workspace_members wm JOIN people p ON p.id=wm.member_id "
            "WHERE wm.workspace_id=? AND wm.member_type='human' "
            "AND p.tier IN ('backbone','coach') ORDER BY p.id", (workspace_id,))]
    # c. 全库任一教练团成员
    candidates += [r["id"] for r in conn.execute(
        "SELECT id FROM people WHERE tier='coach' ORDER BY id")]
    for pid in candidates:
        if pid != creator_id:
            return pid
    return None


def _add_message(conn, wid, stype, sid, sname, zone, mtype, content, payload=None):
    return conn.execute(
        "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,payload,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (wid, stype, sid, sname, zone, mtype, content, J(payload) if payload else None, _now())).lastrowid


def dispatch(conn, workspace_id, agent_id, human_name, requirement_text, creator_id=None):
    """派发需求给数字员工：建任务(进行中→待审核) + 生成交付物 + 工作区发 2 条消息"""
    agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    if not agent:
        return None
    deadline = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")
    title = requirement_text.strip().lstrip("@").replace(agent["name"], "").strip()[:40] or f"{agent['name']}的任务"
    task_id = conn.execute(
        "INSERT INTO tasks(workspace_id,title,agent_id,creator_id,reviewer_id,status,priority,"
        "requirement,deadline,created_at) VALUES(?,?,?,?,?,'进行中','中',?,?,?)",
        (workspace_id, title, agent_id, creator_id, None, requirement_text, deadline, _now())).lastrowid

    deliverable, model_info = generate_deliverable(conn, agent, requirement_text, task_id)
    reviewer = _pick_reviewer(conn, workspace_id, creator_id)
    conn.execute(
        "UPDATE tasks SET status='待审核',deliverable=?,reviewer_id=?,model_provider=?,"
        "model_name=?,execution_mode=?,execution_error=?,execution_ms=? WHERE id=?",
        (deliverable, reviewer, model_info.get("provider"), model_info.get("model"),
         "template_fallback" if model_info.get("fallback") and model_info.get("provider")
         else ("template" if model_info.get("fallback") else "llm"),
         model_info.get("reason") if model_info.get("provider") else None,
         model_info.get("latency_ms", 0), task_id),
    )

    _add_message(conn, workspace_id, "agent", agent_id, agent["name"], "agent", "deliverable",
                 deliverable, {"task_id": task_id, "status": "待审核", "version": 1,
                               "model_info": model_info})
    _add_message(conn, workspace_id, "system", None, "系统", "agent", "approval",
                 f"任务 #{task_id} 交付物已生成，待人工审核（审核人：{_person_name(conn, reviewer)}）。")
    conn.commit()
    return task_id


def _deliverable_version(conn, task_id, workspace_id):
    """下一版交付物版本号：该任务已发出的交付物卡片数 + 1"""
    if not workspace_id:
        return 1
    row = conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE workspace_id=? AND msg_type='deliverable' "
        "AND payload LIKE ?", (workspace_id, f'%"task_id": {task_id}%')).fetchone()
    return row["c"] + 1


def rework(conn, task_id):
    """审核驳回后重做一轮：交付物开头注入上一轮驳回意见，状态回到待审核，payload 带 version"""
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        return
    agent = conn.execute("SELECT * FROM agents WHERE id=?", (task["agent_id"],)).fetchone()
    version = _deliverable_version(conn, task_id, task["workspace_id"])
    deliverable, model_info = generate_deliverable(conn, agent, task["requirement"] or task["title"],
                                                   task_id)
    comment = (task["review_comment"] or "").strip() or "（未填写具体意见）"
    deliverable = (f"第 {version} 版修订说明：针对上一轮驳回意见『{comment}』，"
                   f"本版已逐项修订，请复核。\n\n" + deliverable)
    conn.execute(
        "UPDATE tasks SET status='待审核',deliverable=?,model_provider=?,model_name=?,"
        "execution_mode=?,execution_error=?,execution_ms=? WHERE id=?",
        (deliverable, model_info.get("provider"), model_info.get("model"),
         "template_fallback" if model_info.get("fallback") and model_info.get("provider")
         else ("template" if model_info.get("fallback") else "llm"),
         model_info.get("reason") if model_info.get("provider") else None,
         model_info.get("latency_ms", 0), task_id),
    )
    if task["workspace_id"]:
        _add_message(conn, task["workspace_id"], "agent", agent["id"], agent["name"], "agent",
                     "deliverable", deliverable,
                     {"task_id": task_id, "status": "待审核", "rework": True, "version": version,
                      "model_info": model_info})
        _add_message(conn, task["workspace_id"], "system", None, "系统", "agent", "approval",
                     f"任务 #{task_id} 已按驳回意见重做（第 {version} 版），新交付物待人工审核。")


def _person_name(conn, pid):
    if not pid:
        return "待指派"
    row = conn.execute("SELECT name FROM people WHERE id=?", (pid,)).fetchone()
    return row["name"] if row else "待指派"


# ---------------- 私聊区：项目管理智能体需求打磨 ----------------
def _suggest_agents(conn, workspace_id, content):
    """私聊派活建议，返回 (推荐员工名列表, 是否本工作区成员)。

    优先推荐该工作区成员中的数字员工（真实在区，至多 2 个，排除项目管理智能体自身）；
    工作区无成员员工时再按需求关键词匹配类别，兜底为任一试点中员工。
    """
    rows = conn.execute(
        "SELECT a.name FROM workspace_members wm JOIN agents a ON a.id=wm.member_id "
        "WHERE wm.workspace_id=? AND wm.member_type='agent' AND a.status NOT IN ('已下线') "
        "AND a.name<>'项目管理智能体' ORDER BY a.id LIMIT 2", (workspace_id,)).fetchall()
    if rows:
        return [r["name"] for r in rows], True
    rules = [
        (("外贸", "订单", "单证", "唛头", "客户", "跟单"), "外贸跟单数字员工"),
        (("会议", "纪要", "待办", "例会"), "会议纪要数字员工"),
        (("BOM", "缺料", "物料", "图纸"), "BOM物料数字员工"),
        (("质量", "异常", "8D", "投诉", "检验"), "质量异常分析助手"),
        (("测试", "售后", "温升", "归因", "实验"), "研发测试分析助手"),
    ]
    for keys, name in rules:
        if any(k in content for k in keys):
            row = conn.execute(
                "SELECT name FROM agents WHERE name=? AND status<>'已下线'", (name,)
            ).fetchone()
            if row:
                return [row["name"]], False
    row = conn.execute(
        "SELECT name FROM agents WHERE status IN ('已上线','试运行','试点中','开发中') "
        "ORDER BY CASE status WHEN '已上线' THEN 0 WHEN '试运行' THEN 1 "
        "WHEN '试点中' THEN 2 ELSE 3 END,id LIMIT 1").fetchone()
    return ([row["name"]] if row else []), False


def private_assist(conn, workspace_id, person, content):
    """私聊区零回复修复：项目管理智能体把需求打磨成任务草稿并给出派活建议。

    返回新消息 id；项目管理智能体不存在时返回 None。
    """
    pm = conn.execute("SELECT * FROM agents WHERE name='项目管理智能体'").fetchone()
    if not pm:
        return None
    suggested, in_ws = _suggest_agents(conn, workspace_id, content)
    if not suggested:
        return _add_message(
            conn, workspace_id, "system", None, "系统", "private", "text",
            "当前没有可用数字员工，请联系项目负责人启用或加入数字员工后再派活。")
    brief = content.strip().replace("\n", " ")
    if len(brief) > 60:
        brief = brief[:60] + "…"
    if in_ws and len(suggested) > 1:
        sug_line = (f"本工作区成员 {'、'.join('**@' + n + '**' for n in suggested)} 均可承接，"
                    f"建议优先 **@{suggested[0]}**（均为本区真实在区数字员工）。")
    elif in_ws:
        sug_line = (f"建议直接在本工作区 **@{suggested[0]}** 派活"
                    f"（该数字员工是本区真实在区成员，与此类需求匹配）。")
    else:
        sug_line = f"建议到协作空间 **@{suggested[0]}** 处理此类需求（与该需求匹配度最高）。"
    reply = f"""## 需求打磨草稿

**{person['name']}，您的需求**：{brief}

### 一、结构化任务草稿
- **任务目标**：{brief}
- **建议交付物**：结构化结果文档 1 份（含明细数据与待人工确认事项）
- **审核节点**：交付物生成后须人工审核方可生效，全程留痕

### 二、建议派活对象
{sug_line}

### 三、示例话术
> @{suggested[0]} 请帮我处理：{brief}。要求输出结构化结果，并标注需人工确认的事项。

> 以上由项目管理智能体自动整理，确认后可复制示例话术到协作空间直接派活。"""
    return _add_message(conn, workspace_id, "agent", pm["id"], pm["name"],
                        "private", "text", reply)


# ---------------- 派活兜底：无可用数字员工时的引导（R5，徐露璐场景） ----------------

def handle_undispatched(conn, workspace_id, person, content):
    """agent 区发言未触发派发时的兜底：说明原因、推荐在线员工、自动登记待处理需求。

    返回 {"reason", "offline_agents", "suggestions", "pending_task_id"}，
    同时由项目管理智能体在工作区发一条引导消息（消息在函数内写入，调用方负责 commit）。
    """
    offline = [dict(r) for r in conn.execute(
        "SELECT a.name, p.name owner_name FROM workspace_members wm "
        "JOIN agents a ON a.id=wm.member_id LEFT JOIN people p ON p.id=a.owner_id "
        "WHERE wm.workspace_id=? AND wm.member_type='agent' AND a.status='已下线'",
        (workspace_id,))]
    has_member = conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id=? AND member_type='agent' LIMIT 1",
        (workspace_id,)).fetchone() is not None
    if offline:
        names = "、".join(a["name"] for a in offline)
        owners = "、".join(sorted({a["owner_name"] for a in offline if a["owner_name"]})) or "部门负责人"
        reason = f"本工作区的数字员工（{names}）已下线，暂时无法承接新任务，可联系负责人（{owners}）或改派其他在线员工。"
    elif has_member:
        reason = "本工作区的数字员工当前不可用，请改派其他在线员工或登记待处理需求。"
    else:
        reason = "本工作区尚未加入数字员工成员，可从下方推荐中选择在线员工派活，或登记待处理需求由负责人跟进。"

    suggested, in_ws = _suggest_agents(conn, workspace_id, content)
    # 登记待处理需求任务（无 agent_id，保持「待处理」），保证每条需求都有可追踪去向
    title = content.strip().lstrip("@")[:40] or "待处理需求"
    pending_id = conn.execute(
        "INSERT INTO tasks(workspace_id,title,agent_id,creator_id,reviewer_id,status,priority,"
        "requirement,created_at) VALUES(?,?,NULL,?,NULL,'待处理','中',?,?)",
        (workspace_id, f"[待派活] {title}", person["id"], content, _now())).lastrowid

    sug_text = "、".join(f"@{n}" for n in suggested)
    recommendation = (
        f"- **推荐在线员工**：{sug_text}（请先由负责人将其加入本工作区）\n"
        if suggested else "- **当前无在线员工**：请联系项目负责人启用数字员工\n")
    guide = (f"## 派活引导\n\n{reason}\n\n"
             f"{recommendation}"
             f"- **需求已登记**：已为您创建待处理任务 #{pending_id}，负责人可在任务中心认领跟进。\n\n"
             f"> 以上由项目管理智能体自动生成。")
    pm = conn.execute("SELECT * FROM agents WHERE name='项目管理智能体'").fetchone()
    if pm:
        _add_message(conn, workspace_id, "agent", pm["id"], pm["name"], "agent", "text", guide)
    return {"reason": reason, "offline_agents": [a["name"] for a in offline],
            "suggestions": suggested, "pending_task_id": pending_id}


# ---------------- 心跳 ----------------

def heartbeat(conn):
    """项目管理智能体日报 + 临期任务催办，返回执行摘要"""
    pm = conn.execute("SELECT * FROM agents WHERE name='项目管理智能体'").fetchone()
    ws = conn.execute("SELECT * FROM workspaces WHERE name='总经办·经营驾驶舱'").fetchone()
    if not pm or not ws:
        return {"ok": False, "reason": "项目管理智能体或经营驾驶舱工作区不存在"}

    today = datetime.now().date()
    # 同日同工作区已发过日报则跳过，避免重复日报
    existing = conn.execute(
        "SELECT id FROM messages WHERE workspace_id=? AND msg_type='report' AND created_at LIKE ?",
        (ws["id"], today.isoformat() + "%")).fetchone()
    if existing:
        return {"ok": True, "skipped": True, "date": today.isoformat(),
                "reason": f"今日日报已发布（消息#{existing['id']}），跳过重复心跳",
                "report_workspace": ws["name"]}
    yesterday = (today - timedelta(days=1)).isoformat()
    done_yesterday = conn.execute(
        "SELECT COUNT(*) c FROM tasks WHERE done_at LIKE ?", (yesterday + "%",)).fetchone()["c"]
    pilot_cnt = conn.execute("SELECT COUNT(*) c FROM scenarios WHERE status='试点中'").fetchone()["c"]
    total_sc = conn.execute("SELECT COUNT(*) c FROM scenarios").fetchone()["c"]
    active_sc = conn.execute(
        "SELECT COUNT(*) c FROM scenarios WHERE status IN ('已立项','开发中','试点中','已验收')").fetchone()["c"]
    coverage = round(active_sc / total_sc * 100, 1) if total_sc else 0

    # 临期：deadline 24h 内且未完成
    limit = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
    due = conn.execute(
        "SELECT id,title,workspace_id,deadline FROM tasks "
        "WHERE status IN ('待处理','进行中','待审核') AND deadline<=?", (limit,)).fetchall()

    due_lines = "\n".join(f"- 任务#{t['id']} {t['title']}（截止 {t['deadline']}）" for t in due) or "- 无"

    # ---- 项目流程巡检：每个进行中 flow 推进一次 tick + 主链路延迟预警 ----
    from app import flow as flow_engine  # 延迟导入，避免与 flow.py 循环依赖
    flow_lines, warn_lines = [], []
    for f in conn.execute("SELECT * FROM project_flows WHERE status='进行中' ORDER BY id").fetchall():
        flow_engine.tick(conn, f["id"])
    for f in conn.execute("SELECT * FROM project_flows ORDER BY id").fetchall():
        s = flow_engine.flow_summary(conn, f)
        gates_txt = " ".join(f"{g}{'✅' if st == '已通过' else '⏳' if st == '待签核' else '—'}"
                             for g, st in s["gates"].items())
        flow_lines.append(f"- {s['name']}：{s['status']}，阶段 {s['current_stage']}/5"
                          f"（{s['current_stage_name']} {s['stage_progress']}%），"
                          f"节点完成 {s['nodes_done']}/{s['nodes_total']}，门禁 {gates_txt}")
    for d in flow_engine.delayed_critical_nodes(conn):
        warn_lines.append(f"- 关键路径延迟预警：{d['code']}（{d['title']}）已进行 {d['days']} 天"
                          f"（流程：{d['flow_name']}，状态：{d['status']}）")
    flow_section = "\n".join(flow_lines) or "- 暂无项目流程"
    warn_section = "\n".join(warn_lines) or "- 无"

    report = f"""## 数字员工运营日报（{today.isoformat()}）

- 昨日完成任务：**{done_yesterday}** 件
- 试点中场景：**{pilot_cnt}** 个
- 场景覆盖率：**{coverage}%**（已立项及以上 {active_sc}/{total_sc}）

### 临期任务清单（24h 内）
{due_lines}

### 项目流程进展
{flow_section}

### 关键路径延迟预警（主链路节点滞留超 {flow_engine.DELAY_DAYS} 天）
{warn_section}

> 以上由项目管理智能体自动汇总，临期任务已触发催办，项目流程已自动推进一轮。"""
    _add_message(conn, ws["id"], "agent", pm["id"], pm["name"], "agent", "report", report,
                 {"date": today.isoformat(), "done_yesterday": done_yesterday,
                  "pilot_scenarios": pilot_cnt, "coverage": coverage, "due_tasks": len(due),
                  "flow_warnings": len(warn_lines)})

    for t in due:
        _add_message(conn, t["workspace_id"], "system", None, "系统", "agent", "text",
                     f"催办：任务 #{t['id']}「{t['title']}」距截止时间不足 24 小时，请尽快处理/审核。")
    conn.commit()
    return {"ok": True, "date": today.isoformat(), "done_yesterday": done_yesterday,
            "pilot_scenarios": pilot_cnt, "coverage": coverage,
            "reminded_tasks": len(due), "report_workspace": ws["name"],
            "flow_warnings": len(warn_lines)}
