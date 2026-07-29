# Agent 人机协作平台 · 后端 API 文档

- Base URL：`http://127.0.0.1:8000`
- 启动：`python -m uvicorn app.main:app --port 8000`（首次启动自动建库 `data/platform.db` 并播种）
- 全部接口返回 JSON；错误格式统一为 `{"detail": "错误信息"}`（HTTP 状态码 400/401/404 等）
- 认证：除 `POST /api/login` 外，所有接口都需要请求头 `Authorization: Bearer <token>`
- 写操作（POST/PATCH/审核/审批）均会写入 `audits` 审计表（`POST /api/login` 除外：登录是高频流水，不记审计）
- 中文乱码提示：curl 直接 `-d` 内联中文在 Windows Git Bash 下会损坏编码，请用 `--data-binary @file.json`
  并加 `Content-Type: application/json; charset=utf-8`（前端 fetch/axios 无此问题）

## 数据字典（枚举值）

| 字段 | 取值 |
| ---- | ---- |
| people.tier | `boss` / `coach` / `backbone` / `developer` / `staff` |
| agents.status | `规划中` / `开发中` / `试运行` / `试点中` / `已上线` / `已下线` |
| agents.category | `业务/项目助理` / `智造运营/会议纪要` / `BOM/物料` / `质量/制程异常分析` / `研发测试/售后分析` / `综合事务` / `通用` |
| agents.wave | 1（8月战略+营销核心）/ 2（9月营销深化+智造）/ 3（10月研发+质量）/ 4（其余） |
| scenarios.priority | `高` / `中` / `低` |
| scenarios.status | `待立项` / `已立项` / `开发中` / `试点中` / `已验收` / `已下线` |
| workspaces.type | `项目` / `部门` / `临时` |
| messages.zone | `discussion`（讨论区）/ `agent`（Agent执行区）/ `private`（私聊区） |
| messages.msg_type | `text` / `task_card` / `deliverable` / `approval` / `report` |
| tasks.status | `待处理` / `进行中` / `待审核` / `已通过` / `已驳回` |
| skills.scope | `公开` / `组织` / `个人` |
| documents.level | `L1` / `L2` / `L3` / `L4` |
| milestones.node_type | `agent` / `hybrid` / `human` |
| incentives.type | `火花奖` / `银齿轮奖` / `金扳手奖` / `种子基金` |
| reimbursements.status | `待平台长审批` / `待数字化复核` / `待财务报销` / `已完成` / `已驳回`（step 1-3 三级流转） |

---

## 1. 认证

### POST /api/login
登录（唯一免 token 接口）。

请求：
```json
{"person_id": 20}
```
响应 200：
```json
{
  "token": "aa8a03223b72422fb7c7163234768073",
  "person": {
    "id": 20, "dept_id": 11, "name": "胡鑫", "role_title": "AI应用开发者",
    "tier": "developer", "direction": "外贸销售/跟单/单证/包装资料", "status": "在职",
    "dept_name": "国际销售部", "platform_name": "产品营销平台", "platform_id": 2
  }
}
```
错误：404 `{"detail":"人员不存在"}`

### GET /api/me
返回当前登录人（结构同 login 的 `person`）。无/错 token → 401 `{"detail":"Token 无效或已过期"}`。

---

## 2. 组织

### GET /api/org/tree
5 平台嵌套部门，部门含 `people[]` 与 `agents[]`。

响应 200（节选）：
```json
[
  {
    "id": 1, "name": "战略平台", "code": "PLT-STR", "headcount": 43, "color": "#4C6FFF",
    "departments": [
      {
        "id": 1, "platform_id": 1, "name": "董事办",
        "people": [{"id": 1, "dept_id": 1, "name": "董事长", "role_title": "董事长", "tier": "boss", "direction": "经营决策", "status": "在职"}],
        "agents": [{"id": 1, "dept_id": 1, "name": "财务经营数字员工", "code": "DE-DSB-01", "category": "综合事务", "status": "开发中", "wave": 1, "tasks_done": 0, "hours_saved": 0.0, "accuracy": 0.0}]
      }
    ]
  }
]
```

### GET /api/people
查询参数（可选）：`tier`、`dept_id`。
响应：`[{id, dept_id, name, role_title, tier, direction, status, dept_name}, ...]`

### GET /api/people/{id}
响应：人员详情 + `dept_name/platform_name/platform_id` + `agents[]`（名下数字员工 `{id,name,code,status,category}`）。404 人员不存在。

---

## 3. 数字员工

### GET /api/agents
查询参数（可选）：`platform_id`、`status`、`wave`、`category`（可组合）。
响应：`[{id, dept_id, name, code, category, description, status, owner_id, wave, skills[], tasks_done, hours_saved, accuracy, dept_name, platform_id, platform_name, owner_name}, ...]`（`skills` 已解析为数组）

### GET /api/agents/{id}
响应：基本信息同上，另含三个扩展字段：
```json
{
  "id": 22, "name": "外贸跟单数字员工", "code": "DE-INT-02", "status": "试点中", "wave": 1,
  "owner_name": "谢荣浩", "skills": ["外贸单证生成", "合同要点检查", "待办分派"],
  "scenarios": [{"id": 1, "name": "外贸订单跟单自动化", "status": "试点中", "priority": "高", "batch": "首批", "expected_benefit": "12.24万/年"}],
  "metrics_14d": [{"date": "2026-07-06", "tasks_done": 3, "hours_saved": 1.9, "token_cost": 4.23, "accuracy": 96.5}],
  "recent_tasks": [{"id": 6, "workspace_id": 2, "title": "请整理本周订单资料并生成唛头", "status": "已通过", "priority": "中", "created_at": "...", "done_at": "..."}]
}
```

### PATCH /api/agents/{id}
可更新字段：`status / description / owner_id / wave / accuracy / category / name / skills`（skills 传数组）。

权限与校验（第一轮验收新增）：
- 仅 `boss` / `coach` 或该数字员工的 **owner 本人** 可修改，否则 403 `{"detail":"仅高管/教练团或该数字员工的负责人本人可修改"}`；
- `status` 仅允许 `规划中/开发中/试运行/已上线/已下线`，其他值 422
  `{"detail":"status 仅允许：规划中/开发中/试运行/已上线/已下线，收到「飞」"}`。

请求：
```json
{"status": "试运行"}
```
响应：更新后的 agent 完整对象。400 没有可更新字段；404 不存在。

---

## 4. 场景

### GET /api/scenarios
查询参数（可选）：`platform_id`、`dept_id`、`status`、`priority`。
响应：`[{id, dept_id, agent_id, name, description, priority, batch, status, expected_benefit, actions[], dept_name, platform_id, platform_name, agent_name}, ...]`（`actions` 已解析为数组）

### POST /api/scenarios
敏捷立项申报，创建即 `待立项`。
请求：
```json
{"dept_id": 13, "name": "供应商报价单智能归档", "description": "采购报价单自动识别、归档并生成比价表", "priority": "中", "expected_benefit": "预估3万/年", "actions": ["报价单识别归档", "比价表生成"]}
```
（`agent_id`、`batch` 可选，batch 默认 `扩围`）
响应：创建的场景对象。400 缺 name/dept_id；404 部门不存在。

### POST /api/scenarios/{id}/initiate
立项：状态 `待立项`→`已立项`，自动创建项目工作区（拉入申请人与关联 agent），并在工作区写入一条 system 消息与一条立项说明。
响应 200：
```json
{
  "scenario": {"id": 82, "name": "供应商报价单智能归档", "status": "已立项", "...": "..."},
  "workspace": {"id": 7, "name": "项目·供应商报价单智能归档", "type": "项目", "scenario_id": 82, "created_by": 20, "created_at": "..."}
}
```
错误：400 仅待立项场景可立项；404 场景不存在。

---

## 5. 工作区与消息（三区交互）

### GET /api/workspaces
查询参数（可选）：`type`。
响应：`[{id, name, type, scenario_id, created_by, created_at, creator_name, scenario_name, member_count}, ...]`

### POST /api/workspaces
请求：
```json
{"name": "外贸旺季攻坚群", "type": "临时", "scenario_id": null, "humans": [21, 39], "agents": [22]}
```
`type` 默认 `临时`；`humans`/`agents` 为可选初始成员 id 数组；创建人自动入群并生成一条 system 消息。
响应：`{"id": 8, "name": "外贸旺季攻坚群"}`

### GET /api/workspaces/{id}
响应：工作区信息 + `members[]`：
```json
{"id": 2, "name": "试点项目·外贸订单跟单自动化", "type": "项目",
 "members": [{"id": 3, "workspace_id": 2, "member_type": "human", "member_id": 20, "name": "胡鑫"},
             {"id": 6, "workspace_id": 2, "member_type": "agent", "member_id": 22, "name": "外贸跟单数字员工"}]}
```

### GET /api/workspaces/{id}/messages
查询参数（可选）：`zone`（三区过滤）、`limit`（默认 200）。按时间升序。
响应：
```json
[
  {"id": 27, "workspace_id": 2, "sender_type": "human", "sender_id": 20, "sender_name": "胡鑫",
   "zone": "agent", "msg_type": "text", "content": "@外贸跟单数字员工 请整理本周订单资料并生成唛头",
   "payload": null, "created_at": "2026-07-19T17:12:03"},
  {"id": 28, "workspace_id": 2, "sender_type": "agent", "sender_id": 22, "sender_name": "外贸跟单数字员工",
   "zone": "agent", "msg_type": "deliverable", "content": "## 交付物：订单/单证处理结果\n...",
   "payload": {"task_id": 6, "status": "待审核", "version": 1}, "created_at": "2026-07-19T17:12:04"},
  {"id": 29, "workspace_id": 2, "sender_type": "system", "sender_id": null, "sender_name": "系统",
   "zone": "agent", "msg_type": "approval", "content": "任务 #6 交付物已生成，待人工审核（审核人：胡鑫）。",
   "payload": null, "created_at": "2026-07-19T17:12:04"}
]
```
`payload` 已解析为对象（无则 null）；`deliverable` 消息的 `payload.task_id` 用于调审核接口，
`payload.version` 为交付物版本号（首次派发=1，每次驳回重做 +1，重做时另有 `rework: true`）。

### POST /api/workspaces/{id}/messages
发言。若 `zone=="agent"` 或内容含 `@某数字员工名` → 自动派发任务，数字员工产出交付物（见上例 28/29 两条消息）；agent 区无 @ 时派给工作区内全部数字员工成员。
请求：
```json
{"content": "@外贸跟单数字员工 请整理本周订单资料并生成唛头", "zone": "agent"}
```
响应 200：
```json
{
  "message": {"id": 27, "sender_type": "human", "sender_name": "胡鑫", "zone": "agent", "msg_type": "text", "content": "@外贸跟单数字员工 请整理本周订单资料并生成唛头", "...": "..."},
  "dispatched": [{"task_id": 6, "agent_id": 22, "agent_name": "外贸跟单数字员工"}]
}
```
未触发派发时 `dispatched` 为 `[]`。400 content 必填 / zone 非法；404 工作区不存在。

私聊区（第一轮验收新增）：`zone=="private"` 时不派活，由「项目管理智能体」生成一条需求打磨回复
（把需求复述成结构化任务草稿 + 建议 @ 哪个数字员工 + 示例话术），响应多一个 `reply` 字段
（`sender_type=agent`、`msg_type=text`、`zone=private`）。
建议派活对象的选择（第二轮验收变更）：优先推荐本工作区成员中的数字员工（真实在区，至多 2 个，
不含项目管理智能体自身）；本区无成员员工时才按需求关键词匹配全库员工类别兜底。
```json
{
  "message": {"id": 40, "zone": "private", "...": "..."},
  "dispatched": [],
  "reply": {"id": 41, "sender_type": "agent", "sender_name": "项目管理智能体", "zone": "private",
            "msg_type": "text", "content": "## 需求打磨草稿\n..."}
}
```

---

## 6. 任务（人在环路）

### GET /api/tasks
查询参数（可选）：`status`、`agent_id`、`reviewer_id`、`workspace_id`。按 id 倒序。
响应：`[{id, workspace_id, title, agent_id, creator_id, reviewer_id, status, priority, requirement, deliverable, review_comment, deadline, created_at, done_at, agent_name, creator_name, reviewer_name}, ...]`

### GET /api/tasks/{id}
按 ID 返回单项任务，字段与列表项一致；任务不存在返回 404。该端点用于外部 Agent 运行时按稳定 ID 拉取任务上下文。

### POST /api/tasks
请求：
```json
{"title": "整理8月展会客户名单", "workspace_id": 2, "agent_id": 22, "priority": "高", "requirement": "...", "deadline": "2026-07-25T18:00:00", "reviewer_id": 3}
```
仅需 `title`；创建人取当前登录人。行为（第一轮验收修复）：
- **带 `agent_id`**：复用引擎执行逻辑，立即产出交付物并转 `待审核`（同步完成），
  若带 `workspace_id` 同时在工作区发 deliverable + approval 消息（payload 含 `version: 1`）；`agent_id` 不存在 → 404；
- **不带 `agent_id`**：允许创建（保持 `待处理`，不会自动执行），响应附带提示字段：
  `"hint": "未指派数字员工，任务不会自动执行，建议到协作空间 @数字员工 派活"`。

响应：任务对象（无 agent_id 时多一个 `hint` 字段）。

### POST /api/tasks/{id}/external-events

外部 Agent 执行控制面回传任务事件。仅 `boss/coach` 身份可调用；同一 `source + event_id` 幂等，重复请求返回 `idempotent: true`。

请求：

```json
{
  "event_id": "multica:JJ-18:deliverable:sha256",
  "event_type": "deliverable",
  "source": "multica",
  "content": "## 外部 Agent 交付物\n...",
  "metadata": {"external_issue_id": "...", "external_status": "done"}
}
```

- `event_type`：`started/progress/blocked/deliverable/cancelled`；
- `started/progress/blocked`：任务保持或进入 `进行中`，有工作区时写入 runtime_event 系统消息；
- `deliverable`：`content` 必填，任务只进入 `待审核`，写入带 `runtime=external` 的交付卡片，**绝不自动通过**；
- `cancelled`：任务进入 `已驳回`，保留原因等待人工处置；
- 已经人工 `已通过` 的任务拒绝后续外部事件（409）。

响应：`{"ok":true,"idempotent":false,"task":{...}}`。事件会写审计；`event_id/source/content/metadata` 格式错误返回 400。

### POST /api/tasks/{id}/review
人工审核（仅 `待审核` 状态可审，审核人记为当前登录人）。

权限（第一轮验收新增）：
- 仅 `tier ∈ {boss, coach, backbone}` 可审核，否则 403 `{"detail":"当前身份无权审核任务，仅高管/教练团/骨干可审核"}`；
- 不能审核自己发起的任务（reviewer ≠ creator），否则 403 `{"detail":"不能审核自己发起的任务"}`。

审核人自动指派（第二轮验收变更）：派活或带 `agent_id` 直建任务时自动写入 `reviewer_id`，
按序取人且**始终排除任务创建人**（取到创建人顺延下一位）：
1. 任务关联场景（若有）所属部门中 `tier=backbone` 的人；
2. 该工作区成员中 `tier ∈ {backbone, coach}` 的人；
3. 全库任一 `coach`。

候选全空时 `reviewer_id` 为 `null`（待指派；审核通过/驳回时会改写为实际审核人）。

请求：
```json
{"action": "approve", "comment": "资料齐全，通过"}
```
- `approve`：状态→`已通过`，写 `done_at`；agent 累计 `tasks_done+1`、`hours_saved` 按优先级 +3/2/1 小时（高/中/低），写入当日 `metrics_daily`，工作区发 system 通知。
- `reject`：状态→`已驳回` 并记录批注，随后数字员工自动重做一轮：新交付物开头注入
  `第 N 版修订说明：针对上一轮驳回意见『<comment>』……`，状态回到 `待审核`，
  工作区再发 deliverable（payload 含 `rework: true, version: N`）+ approval 两条消息。
  若最新交付卡片带 `runtime=external`，则保持 `已驳回` 并写 runtime_event，等待外部运行时读取任务状态后重做，避免本地模板覆盖真实 Agent 结果。

响应：更新后的任务对象。400 action 非法 / 状态非待审核；403 权限不足或自审；404 任务不存在。

---

## 7. Skill 资产库

### GET /api/skills
查询参数（可选）：`scope`。
响应：`[{id, name, scope, category, owner_name, description}, ...]`（播种 20 条）

### POST /api/skills
请求：`{"name": "信用证审单", "scope": "组织", "category": "外贸", "description": "..."}`
（`owner_name` 缺省取当前人）。响应：创建的 skill 对象。

---

## 8. 知识库

### GET /api/knowledge/spaces
响应：`[{id, name, device, capacity, dept_name, domain, doc_count}, ...]`（6 套群晖 DS925+ 空间）

### GET /api/knowledge/documents
查询参数（可选）：`space_id`、`level`。
响应：`[{id, space_id, title, level, tags, uploaded_by, created_at, space_name}, ...]`

### POST /api/knowledge/documents
请求：`{"space_id": 4, "title": "测试用例库", "level": "L3", "tags": "测试,用例"}`
（`uploaded_by` 取当前人）。响应：创建的文档对象。400 缺参数；404 空间不存在。

---

## 9. KPI 看板

### GET /api/metrics/dashboard
响应 200（示例，第一轮验收后结构）：
```json
{
  "kpi": {
    "coverage":        {"value": 0.0,   "note": "已验收场景/场景总数"},
    "trial_coverage":  {"value": 6.2,   "note": "试点中+已验收/场景总数"},
    "acceptance_rate": {"value": 100.0, "note": "审核通过数/已审核数"},
    "active_rate":     {"value": 7.7,   "note": "近7日有产出数字员工/已上线+试运行"},
    "hours_saved":     {"value": 187.4, "note": "累计审核通过折算工时"},
    "accuracy":        {"value": 96.2,  "note": "近30日平均准确率"},
    "annual_benefit":  {"value": 790000,"note": "已验收场景预期年化收益合计"},
    "reuse_count":     {"value": 13,    "note": "被数字员工引用的 Skill 总数（去重）"}
  },
  "investment": {"year1": 342895.6,
                 "breakdown": {"算力资源": 137895.6, "NAS知识库底座": 105000.0, "创新激励奖金池": 100000.0},
                 "breakdown_detail": {
                   "算力资源": {"阿里云节省计划": 23850.0, "智谱团队套餐": 84045.6, "个性化灵活采购": 30000.0},
                   "NAS知识库底座": {"采购": 95000.0, "运维预留": 10000.0},
                   "创新激励奖金池": {}}},
  "benefit": {"direct": 540000, "total": 790000, "roi_year1_pct": 57.5, "roi_year2_pct": 117.8},
  "waves": [{"wave": 1, "total": 21, "by_status": {"开发中": 19, "试点中": 1, "已上线": 1}}],
  "leaderboard": [{"id": 22, "name": "外贸跟单数字员工", "code": "DE-INT-02", "status": "试点中",
                   "tasks_done": 48, "hours_saved": 26.1, "accuracy": 95.5}],
  "trend": [{"date": "2026-07-06", "tasks_done": 11, "hours_saved": 8.3}],
  "feed": [{"id": 33, "workspace_id": 1, "workspace_name": "总经办·经营驾驶舱", "sender_type": "agent",
            "sender_name": "项目管理智能体", "zone": "agent", "msg_type": "report",
            "content": "## 数字员工运营日报（2026-07-19）...", "created_at": "..."}],
  "latest_report": {"id": 33, "workspace_id": 1, "workspace_name": "总经办·经营驾驶舱",
                    "sender_name": "项目管理智能体",
                    "content": "## 数字员工运营日报（2026-07-20）...", "created_at": "2026-07-20T02:02:28"}
}
```
说明（第一轮验收变更）：
- **`kpi` 每项改为 `{value, note}` 结构**（`note` 为口径说明小字，前端渲染用 `.value` 取数）；
- `kpi.coverage` 改为方案口径 = 已验收场景/场景总数（当前 0）；原口径数值移入新增字段
  `kpi.trial_coverage` = （试点中+已验收）/场景总数（当前 6.2）；
- `investment.breakdown` 改为方案三科目（算力资源 137,895.6 / NAS知识库底座 105,000 / 创新激励奖金池 100,000，合计 342,895.6 元），
  新增 `investment.breakdown_detail` 给出各科目明细；
- `benefit` 新增 `roi_year1_pct=57.5`、`roi_year2_pct=117.8`；
- `trend` 固定近 14 天（无数据日期补 0）；`feed` 为最近 12 条 system/agent 消息；
- **`latest_report`（第二轮验收新增）**：全库最新一条 `msg_type=report` 的日报消息对象
  （含 `id/workspace_id/workspace_name/sender_name/content/created_at`），无日报时为 `null`；
  前端可将其固定在动态流顶部展示，不受 `feed` 12 条截断影响；
- 指标为实时计算：审核通过后 `acceptance_rate` 等立即变化，页面与 API 不同时刻读数不一致属时序现象。

### GET /api/metrics/agents
响应：`[{id, name, code, status, wave, dept_name, tasks_done, hours_saved, accuracy}, ...]`（按 tasks_done 倒序，全量 65 个）

---

## 10. 治理

### GET /api/governance/incentives
查询参数（可选）：`status`。响应：`[{id, type, nominee, reason, amount, status, created_at}, ...]`

### POST /api/governance/incentives
请求：`{"type": "火花奖", "nominee": "陈思思", "reason": "...", "amount": 800}`（status 固定 `申报中`，申报写 audits）。
类型校验（第二轮验收新增）：`type` 仅允许 `火花奖/银齿轮奖/金扳手奖/种子基金`（缺省 `火花奖`；
未收录奖项或带空格等变体一律拦截），否则 422 `{"detail":"奖项类型仅允许：火花奖/银齿轮奖/金扳手奖/种子基金"}`。
金额档位校验（第一轮验收新增）：`火花奖 500-2000 / 银齿轮奖 5000-10000 / 金扳手奖 30000-50000`（元），
超出档位 422 `{"detail":"火花奖申报金额须在 500-2000 元之间，当前 3000 元超出档位"}`（`种子基金` 不限档）。

### GET /api/governance/reimbursements
查询参数（可选）：`status`。响应：`[{id, applicant, provider, tokens, amount, status, step, comment, created_at}, ...]`
（`comment` 为各级审批意见逐行累加，新列，可空）

### POST /api/governance/reimbursements
请求：`{"provider": "智谱GLM", "tokens": 1200000, "amount": 360}`（`applicant` 缺省取当前人；初始 `待平台长审批` step=1）。

### POST /api/governance/reimbursements/{id}/approve
三级流转审批：step1 平台长→step2 数字化复核→step3 财务→`已完成`；任意级 `reject` 即 `已驳回` 终结。每步记审计，
审批意见累加进 `comment` 列（格式：`[第N级·状态名] 审批人：意见`）。

分权规则（第一轮验收新增，违反返回 403 中文提示）：
- 第 1 级（平台长审批）：`tier ∈ {coach, backbone, boss}`；
- 第 2 级（数字化复核）：仅 `coach`（数字化平台长）；
- 第 3 级（财务报销）：仅 **财务部** 的 `backbone` 或 `boss`；
- 同一人不能审批同一单的连续两级（以 audits 中本单已有通过记录为准）。

请求：`{"action": "approve", "comment": "同意"}` 或 `{"action": "reject", "comment": "..."}`
响应 200：
```json
{"id": 1, "applicant": "胡鑫", "provider": "智谱GLM", "tokens": 1200000, "amount": 360.0,
 "status": "待数字化复核", "step": 2, "comment": "[第1级·待平台长审批] 戴栓：同意", "created_at": "..."}
```
错误：400 已终结 / action 非法；403 越级/越权/同人连批；404 不存在。

### GET /api/governance/audits
审计查询（按 id 倒序）：`[{id, actor, action, target, detail, created_at}, ...]`

查询参数（第二轮验收新增，均可选）：
- `action`：按动作名精确筛选，如 `?action=激励评定`；
- `limit`：返回条数，默认 100，上限 500（超出按 500 计）。

注：登录不记审计（高频流水），audits 中不会出现 `登录` 动作的新记录。

### GET /api/governance/redlines
六大红线（内置常量）：
```json
[{"id": 1, "text": "AI 不得直连生产数据库"}, {"id": 2, "text": "AI 不得直接修改正式业务数据"},
 {"id": 3, "text": "AI 不得绕过人工自动提交审批"}, {"id": 4, "text": "未经评审不得向公网部署"},
 {"id": 5, "text": "写回动作必须人工确认并留痕"}, {"id": 6, "text": "敏感数据必须脱敏"}]
```

---

## 11. 路线图与心跳

### GET /api/roadmap
响应：
```json
{
  "phases": [{"name": "筑基期", "period": "2026.8-2026.9", "description": "搭底座：NAS 知识库部署..."}],
  "milestones": [{"id": 1, "phase": "筑基期", "month": "2026-08", "name": "NAS知识库部署",
                  "owner": "付玉虎", "node_type": "hybrid", "status": "进行中"}],
  "waves": [{"wave": 1, "description": "第一波（2026.8）：战略平台 + 营销核心（营销商务部/国际销售部），含首批试点", "agent_count": 21}]
}
```
（milestones 全量 15 条；phases 3 个；waves 4 个）

### POST /api/heartbeat/run
立即执行一次心跳：项目管理智能体在「总经办·经营驾驶舱」发日报（msg_type=`report`），并对 24h 内临期未完成任务发催办消息。
同日同工作区已发过日报则跳过（去重），响应带 `skipped: true`。
响应 200：
```json
{"ok": true, "date": "2026-07-19", "done_yesterday": 0, "pilot_scenarios": 5,
 "coverage": 6.2, "reminded_tasks": 5, "report_workspace": "总经办·经营驾驶舱"}
```
当日重复触发：
```json
{"ok": true, "skipped": true, "date": "2026-07-19",
 "reason": "今日日报已发布（消息#33），跳过重复心跳", "report_workspace": "总经办·经营驾驶舱"}
```
心跳同时会对每个进行中流程自动执行一次 tick 巡检，日报中含「项目流程进展」与「关键路径延迟预警」两节。

---

## 12. 项目流程（N01-N40 泳道 + G1-G4 阶段门）

承载《AI数智化行动方案 V3》：5 阶段 × 8 角色 × 40 节点；🤖agent 24 / 🤝hybrid 9 / 👤human 7；
12 个主链路节点构成关键路径（N01→N02→N07→G1→N09→G2→N17→N18→N25→G3→N33→G4）；
阶段门 G1=N08 / G2=N16 / G3=N28 / G4=N40，**未过门禁不得进入下一阶段**（阶段三无门禁，主链路全完成后自动解锁阶段四）。
场景立项（`POST /api/scenarios/{id}/initiate`）时自动实例化，响应带 `flow_id`；种子数据含 2 个演示流程
（flow#1 外贸→阶段三、flow#2 会议纪要→G1 待签核）。

| 字段 | 取值 |
| ---- | ---- |
| project_flows.status | `进行中` / `已结项` / `已暂停` |
| project_flows.current_stage | 1-5（项目启动/方案与设计/开发与测试/试点与验证/结项与移交） |
| flow_nodes.exec_type | `agent`（自动完成）/ `hybrid`（AI 初稿待人确认）/ `human`（人工完成） |
| flow_nodes.status | `已锁定` / `未开始` / `进行中` / `待确认` / `待签核` / `已完成` |
| gate_records.status | `未开启` / `待签核` / `已通过` |

### GET /api/flows
流程列表（可按 `?status=进行中` 过滤）。每行含阶段进度、门禁汇总、延迟主链路节点数。

响应 200（节选）：
```json
[
  {"id": 1, "scenario_id": 1, "workspace_id": 2, "name": "外贸订单跟单自动化",
   "status": "进行中", "current_stage": 3, "current_stage_name": "开发与测试",
   "created_at": "2026-07-09T09:00:00", "closed_at": null,
   "stage_progress": 13, "overall_progress": 40, "nodes_done": 16, "nodes_total": 40,
   "gates": {"G1": "已通过", "G2": "已通过", "G3": "未开启", "G4": "未开启"},
   "delayed_critical": 1, "delayed_nodes": ["N17"]}
]
```

### GET /api/flows/{id}
流程完整详情：在列表字段基础上增加 `nodes`（40 节点全部字段：code/stage/role_name/title/outputs/
exec_type/is_critical/gate_code/status/started_at/done_at/note）、`gate_records`（4 条，含 signed_by/
signed_at/comment）、`critical_chain`（主链路 12 节点序列）、`stage_names`。

### POST /api/flows/{id}/tick
手动触发一次自动推进（演示/调试用，需登录，写审计；heartbeat 每轮也会自动调用）。
规则：按节点顺序处理「未开始」节点，每次最多 2 个——🤖直接置已完成并发产出消息；
🤝置「待确认」并发"AI 已生成初稿，请 XX 确认生效"；👤（非门禁）置「进行中」并发 @角色 提醒；
门禁节点不自动处理。

响应 200：
```json
{"ok": true, "flow_id": 3, "processed": [{"code": "N03", "exec_type": "agent"}, {"code": "N04", "exec_type": "agent"}]}
```

### POST /api/flows/{id}/nodes/{code}/confirm
🤝节点确认生效 / 👤节点标记完成。权限：`tier ∈ {boss, coach, backbone}`（其余 403）。
前置状态：hybrid 须为「待确认」，human 须为「进行中」；门禁节点请走签核接口（400）。
确认后置「已完成」（note 记录确认人与 comment）；若为主链路节点且同阶段主链路全部完成，
门禁节点自动置「待签核」、gate_record 置「待签核」。

请求体（可空）：`{"comment": "预算与ROI无误"}`
响应 200：`{"ok": true, "node": {...}}`
错误：403 权限不足；400 状态不符（如「已完成，无需重复确认」）；404 节点不存在。

### POST /api/flows/{id}/gates/{gate}/sign
阶段门签核（gate ∈ G1-G4）。权限：**G1/G2/G4 仅 boss；G3 允许 boss/coach/backbone**（其余 403）。
前置：gate_record 须为「待签核」（未开启→400）。签核后：gate_record「已通过」（signed_by/signed_at/comment）、
门禁节点「已完成」、下一阶段节点「已锁定→未开始」、flow.current_stage+1；
**G4 通过后 flow.status=「已结项」并写 closed_at，关联 scenario.status 置「已验收」**。
全程写 audits + 工作区消息。

请求体（可空）：`{"comment": "同意立项，A级"}`
响应 200：
```json
{"ok": true, "gate": {"id": 1, "flow_id": 2, "gate": "G1", "stage": 1, "status": "已通过",
 "signed_by": "董事长", "signed_at": "2026-07-29T16:00:00", "comment": "同意立项，A级"}}
```
错误：403 签核权限不足（报文注明要求 tier）；400 未开启/重复签核；404 阶段门不存在。

---

## 13. R4 新增能力

### 13.1 模型供应商配置（R4-1）

引擎生成交付物时的模型解析优先级：旧 `settings.llm_*` 三键（向后兼容）> `agents.model_key`
绑定的供应商 > `settings.default_model_key`（默认 glm）。供应商停用或未配置 api_key 时静默回落模板。

#### GET /api/models
供应商列表（api_key 脱敏）：
```json
[{"id": 1, "key": "glm", "name": "智谱GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
  "default_model": "glm-4-flash", "api_key": "未配置", "enabled": true, "is_default": true}]
```

#### PUT /api/models/default
设置全局默认模型（boss/coach）。请求：`{"key": "kimi"}`。
响应：`{"ok": true, "default_model_key": "kimi", "providers": [...]}`。404 供应商不存在。

#### PUT /api/models/{key}
配置单个供应商（boss/coach），可改 `api_key / default_model / enabled`。
请求：`{"api_key": "你的Key", "enabled": true}`。响应：更新后对象（api_key 脱敏为 已配置/未配置）。

#### agents 补充
`POST /api/agents` 与 `PATCH /api/agents/{id}` 均支持 `model_key`（空=跟随全局默认）；
`GET /api/agents/{id}` 返回中新增 `model_key / mcp_ids / mcp`（见 13.2）。

### 13.2 Skill 维护 / Agent 新建 / MCP（R4-2）

#### PATCH /api/skills/{id}
改 `name/scope/category/owner_name/description`（boss/coach）。404 Skill 不存在。

#### DELETE /api/skills/{id}
删除（boss/coach）。响应：`{"ok": true, "deleted": 21}`。

#### POST /api/agents
新建数字员工（boss/coach/developer）。`name/dept_id` 必填，`code` 自动生成
（优先沿用部门前缀 `DE-{部门码}-{序号}`，兜底 `DE-C{id}`）：
```json
{"name": "单证审核数字员工", "dept_id": 11, "category": "业务/项目助理",
 "description": "...", "skills": ["信用证审单"], "model_key": "glm", "mcp_ids": [1, 3]}
```
响应：创建的 agent 对象（含展开后的 `mcp` 数组）。404 部门/MCP/模型不存在。

#### PATCH /api/agents/{id}（扩展）
新增可更新字段：`dept_id / model_key / mcp_ids`（mcp_ids 传 id 数组，落库 JSON）。
`GET /api/agents/{id}` 返回新增：`model_key`、`mcp_ids`（数组）、`mcp`（MCP 对象数组）。

#### GET /api/mcp
MCP 服务台账：`[{id, name, endpoint, description, status}, ...]`（status：启用/停用）。

#### POST /api/mcp
新增（boss/coach）：`{"name": "ERP只读接口", "endpoint": "mcp://erp.internal/read", "description": "...", "status": "停用"}`。

#### PATCH /api/mcp/{id}
改 `name/endpoint/description/status`（boss/coach；status 枚举校验）。

### 13.3 知识库上传与自动解析（R4-3）

#### POST /api/knowledge/spaces/{sid}/upload
multipart 文件上传（backbone/coach/boss/developer）。表单字段：`file`（必填）、`level`（默认 L1）、`tags`。
转换规则：

| 扩展名 | 转换产物 | converted_format |
| ------ | -------- | ---------------- |
| .txt/.md | 直存 .md | md |
| .docx | zipfile 解 word/document.xml 提取文本存 .md | md |
| .pdf | 系统 pdftotext 提取存 .md（失败给中文 422） | md |
| .csv/.json | 解析入 SQLite（`data/knowledge/doc_{id}.db` 的 data_rows 表）+ 生成 .md 摘要（列名+前 5 行） | sqlite |
| .html/.htm | 去 script/style 后存 .html | html |
| 其他 | 422 中文错误 | - |

产物存 `data/uploads/space_{sid}/`；同时写入 `doc_chunks`（md 类按标题/空行约 500 字/块，
html 类按纯文本段落，表格类每 50 行一块），`documents.summary`=首个 chunk 前 200 字。
响应：文档对象（含 `file_path / converted_format / chunk_count / summary`）。

#### GET /api/knowledge/documents/{id}
文档详情 + `chunks[]`（`{id,seq,heading,content}`，按 seq 升序）+ `summary`。

#### GET /api/knowledge/documents/{id}/file
下载/预览转换产物（md→text/markdown，html→text/html）。404 无解析产物。

### 13.4 钉钉/飞书绑定授权（R4-4）

#### GET /api/auth/providers
授权配置列表（app_secret 脱敏为 已配置/未配置，附 `configured` 是否可用真实授权）。

#### PUT /api/auth/providers/{provider}
配置 `app_id/app_secret/redirect_uri/enabled`（仅 boss/coach；secret 返回脱敏、不落审计明文）。

#### GET /api/auth/oauth/{provider}/url
生成授权 URL。已配置凭证→平台标准授权地址（钉钉 `login.dingtalk.com/oauth2/auth`，
飞书 `open.feishu.cn/open-apis/authen/v1/authorize`，state=当前人 id）；
未配置→demo 模式：
```json
{"provider": "dingtalk", "demo": true,
 "url": "/api/auth/oauth/dingtalk/callback?demo=1&person_id=20",
 "tip": "未配置钉钉应用凭证，当前为演示模式（配置后自动切换真实授权）"}
```

#### GET /api/auth/oauth/{provider}/callback?code=&demo=&person_id=
授权回调（浏览器直达，免 token）。demo 模式直接模拟外部身份（`钉钉用户_姓名`）完成绑定；
真实模式用 code 走 urllib 换 token 换用户信息，任何异常返回中文错误 JSON
`{"ok": false, "detail": "钉钉授权回调失败：..."}`。成功：
`{"ok": true, "demo": true, "msg": "...", "binding": {id, person_id, provider, external_id, external_name, bound_at}}`。
重复绑定按 `UNIQUE(person_id,provider)` 覆盖。

#### GET /api/auth/bindings
当前人的绑定列表。

#### POST /api/auth/bindings/{provider}
主动绑定入口（demo 用，直接模拟绑定）。

#### DELETE /api/auth/bindings/{provider}
解绑。404 未绑定。

### 13.5 执行链路（R4-6）

#### GET /api/workspaces/{id}/chain
聚合"过去→现在→未来"执行链（前端链路条用）：
```json
{
  "past": [{"type": "task_event", "task_id": 6, "time": "2026-07-19T17:12:04",
            "title": "审核通过：你会干吗", "status": "已通过", "agent_name": "外贸跟单数字员工", "version": 2}],
  "present": [{"id": 6, "title": "...", "status": "待审核", "agent_name": "...", "priority": "中",
               "deadline": "...", "version": 1}],
  "future": [{"code": "N18", "title": "平台支撑·带教答疑·代码审查", "role_name": "数字化平台",
              "exec_type": "hybrid", "stage": 3, "status": "进行中"}],
  "flow_id": 1
}
```
- `past`：该工作区任务按时间升序的事件流（已创建/已交付/已通过/已驳回）；
- `present`：当前进行中/待审核任务（无则为 `[]`）；
- `future`：关联 project_flow 的未完成节点按阶段顺序取接下来 6 个（无 flow 则 `[]` 且 `flow_id` 为 null）。

---

## 14. 其他

### GET /
前端入口：`app/static/index.html` 存在则返回该页面，否则返回兜底 JSON
`{"msg": "Agent 人机协作平台后端运行中；前端 index.html 尚未部署到 app/static"}`。

### GET /static/*
静态文件目录（前端构建产物放 `app/static/`）。

## 附：演示脚本（前端联调常用路径）
1. `POST /api/login {"person_id": 20}`（胡鑫·国际销售部开发者）拿 token；
2. `GET /api/org/tree` 渲染组织与 65 个数字员工；
3. `GET /api/workspaces` → 进入「试点项目·外贸订单跟单自动化」（id=2）；
4. `GET /api/workspaces/2/messages?zone=agent` 看交付物卡片（payload.task_id）；
5. `POST /api/workspaces/2/messages` 发 `@外贸跟单数字员工 ...`（zone=agent）实时触发派发；
6. `POST /api/tasks/{task_id}/review` 审核通过/驳回；
7. `GET /api/metrics/dashboard` 看 KPI 变化；`POST /api/heartbeat/run` 触发日报。
8. 项目流程：`GET /api/flows` 看两个演示流程 → `GET /api/flows/1` 看 40 节点泳道 →
   `POST /api/flows/2/gates/G1/sign`（boss 登录）演示阶段门签核解锁阶段二。
9. R4 联调：`GET /api/models` 配模型 Key（`PUT /api/models/glm`）→ `POST /api/agents` 新建数字员工绑技能/MCP →
   `POST /api/knowledge/spaces/1/upload` 上传文档自动解析 → `GET /api/auth/oauth/dingtalk/url` 演示模式绑定 →
   `GET /api/workspaces/2/chain` 看"过去→现在→未来"执行链。
