# R7 投资人尽调问题清单（2026-07-29）

> 视角：投资人携 AI 企业资源服务团队对全仓做尽调式"挑毛病"。三个审查小组（后端安全与工程 / 前端与体验 / 文档测试与交付）独立取证，每条附文件:行号。行号为审查时点（2026-07-29）数据。
> 修复与销项见同目录 `investor-audit-fixes.md`（修复完成后产出）。

## 一、后端安全与工程组（agent-platform/app）

### P1 高危

| # | 问题 | 证据 |
|---|---|---|
| B1 | 认证 fail-open：`PLATFORM_MODE` 缺省 demo，任意 person_id 免密换 12h token；`/api/login/people` 公开全员花名册 | `app/routers/auth.py:92-97`、`app/routers/org.py:46-53` |
| B2 | 存储型 XSS：知识库 `.html` 上传仅剔 `<script>`，`onclick`/`javascript:`/`<svg onload>` 保留；`/documents/{id}/file` 以 text/html 同源直出且无 CSP | `app/routers/knowledge.py:444-448,686-694`、`app/main.py:42-51` |
| B3 | 私聊区无隐私：`private_owner_id` 从不写入，zone=private 查询不过滤，工作区成员可读他人"私聊" | `app/database.py:108`、`app/engine.py:693,723`、`app/routers/workspaces.py:117-130` |
| B4 | 任务状态可伪造：POST /api/tasks 采信 `status/reviewer_id/priority` 零校验，可直造"已通过"污染 KPI | `app/routers/tasks.py:99-104`、`app/routers/metrics.py:42-44` |
| B5 | 心跳崩溃边界：无工作区任务催办时 `_add_message(conn, None, ...)` 撞 NOT NULL，整个 heartbeat 回滚 500 | `app/engine.py:848-850`、`app/database.py:100` |
| B6 | 审核 TOCTOU：先查后改无原子条件，并发双通过致绩效重复累计 | `app/routers/tasks.py:252-273` |

### P2 一般

| # | 问题 | 证据 |
|---|---|---|
| B7 | 外部事件幂等跨任务误吞：去重键不含 task_id；专用 `runtime_events` 表成死表 | `app/routers/tasks.py:162-168`、`app/database.py:353-361` |
| B8 | `payload LIKE %"task_id": {id}%` 前缀碰撞：task#6 误匹配 task#60 | `app/routers/tasks.py:225`、`app/engine.py:607`、`app/routers/workspaces.py:259` |
| B9 | OAuth state/code 消费 SELECT→DELETE 非原子，并发可双花 | `app/security.py:22-66`、`app/routers/imbind.py:305-315` |
| B10 | 主密钥丢失时 `crypto.decrypt()` 在 try 外，InvalidTag 穿透 500 | `app/engine.py:199,211` |
| B11 | 死代码 `request_idempotency` 表；POST /api/tasks 与 engine.dispatch 大段重复 | `app/database.py:344-351`、`app/routers/tasks.py:99-135`、`app/engine.py:568-598` |
| B12 | 发言无长度上限、list limit 无上限 | `app/routers/workspaces.py:118,155-158` |
| B13 | post_message 先落库后校验 target_agent_id，422 但消息已发出 | `app/routers/workspaces.py:167-196` |
| B14 | POST /api/tasks 无 tier 限制，staff 可直接烧 LLM 算力（对比工作区创建已拒 staff） | `app/routers/tasks.py:74-75`、`app/routers/workspaces.py:71-72` |
| B15 | list_flows N+1（每 flow 三次子查询） | `app/flow.py:308-328`、`app/routers/flows.py:27-28` |

### API.md 契约不一致

| # | 问题 | 证据 |
|---|---|---|
| B16 | `msg_type` 枚举缺 `runtime_event`；`/api/environment`、`/api/health/ready` 公开未入文档；POST /api/tasks 示例的 `reviewer_id` 会被自动指派静默覆盖；"写操作均记审计"承诺过满（普通发言不记） | `API.md:6,9,25,258,270`、`app/routers/auth.py:100-103`、`app/main.py:79-133`、`app/routers/tasks.py:117-118`、`app/routers/workspaces.py:227-232` |

## 二、前端与体验组（app/static）

### P0 阻断

| # | 问题 | 证据 |
|---|---|---|
| F1 | `?person=<id>` URL 参数免密 impersonate 任意人含 boss | `app.js:3056-3064` |
| F2 | 前端角色体系全读 localStorage 可篡改解锁管理按钮（须后端逐接口强制鉴权兜底） | `app.js:43,74,78,88,2759` |

### P1 高危

| # | 问题 | 证据 |
|---|---|---|
| F3 | 内联事件 XSS：`esc()` 字符串拼进 onclick JS 上下文，单引号逃逸（agent 名、Excel 工作表名用户可控）；流程节点 code 完全未转义 | `app.js:1092,2188,2190,2897,2947,2951,2955,2977,2996` |
| F4 | token 存 localStorage + 大量 innerHTML，XSS 命中即盗号（HttpOnly 改造列 backlog） | `app.js:403` |
| F5 | Tailwind 为浏览器运行时 JIT 版（官方自警勿上生产）首开卡顿；`Noto Sans SC` 声明了但从未加载字体文件 | `vendor/tailwind.js:64`、`index.html:24` |

### P2 一般

| # | 问题 | 证据 |
|---|---|---|
| F6 | 提交按钮普遍无防重复点击（sendWsMessage/submitTask/submitScenario/submitSkill/submitIncentive/submitReimb） | `app.js:1136,1741,1831,1969,2529,2594` |
| F7 | 激励审批用 window.prompt，与全站模态框不一致 | `app.js:2500` |
| F8 | 三个下载函数逐行重复，downloadAuditCsv revoke 时机在 Firefox 会失败 | `app.js:2203-2255,2643-2655` |
| F9 | KPI 目标值、NAS 型号等硬编码前端 | `app.js:655-662,2070` |
| F10 | 401 一律 doLogout()，并发请求被误伤 | `app.js:172-175` |
| F11 | 单文件 3067 行约 70 个全局函数，维护到临界点（拆分列 backlog） | `app.js` 全文 |

## 三、文档/测试/交付组

### P0 阻断

| # | 问题 | 证据 |
|---|---|---|
| D1 | ROI 57.5%/效益 79 万/投入 34.29 万全是硬编码常量而非计算结果，PRD 却列为已实现能力 | `app/routers/metrics.py:13-28`、`PRD.md:29` |
| D2 | Multica 桥接 5 个测试全 mock，真实 E2E 从未执行，PRD 标"已完成"有误导 | `multica-platform/tests/test_bridge.py:11-40,133-138`、`multica-platform/KIMI_SYNC.md:10`、`PRD.md:33` |

### P1 高危

| # | 问题 | 证据 |
|---|---|---|
| D3 | round5 报告"33/33"与证据文件 32/32 矛盾；"13/13"与实际 18 项构成不符 | `acceptance/round5/final-delivery-acceptance.md:18,20,38`、`regression-results.json` |
| D4 | 报销三级审批（唯一资金流）、密级守卫、阶段门签核零 pytest 覆盖 | `tests/` 对 reimburse 零命中；regression 阶段门项实为"无待签核门，跳过" |
| D5 | PDF 解析依赖系统命令 pdftotext，不在 requirements/README/启动自检 | `app/routers/knowledge.py:154-170`、`README.md:17`、`启动平台.bat:11` |
| D6 | "浏览器 JS error 0" 无留档证据不可复现 | round5/round6 仅截图；`cdp_shot.js` 不采 console |

### P2 一般

| # | 问题 | 证据 |
|---|---|---|
| D7 | PRD"七维 KPI"与实际八项不符；"Teams.md 通讯录"无真实产物；测试数口径不一 | `PRD.md:23,29,58`、`README.md:54` |
| D8 | 启动脚本无端口占用检测；`httpx` 未被使用；离线口径（仅前端 CDN）与"首次需联网"矛盾未注明 | `启动平台.bat:26`、`requirements.txt`、`app/` 零 httpx 引用 |

## 四、已核实无误项（平衡参考）

- SQL 注入面逐一核查：动态 SQL 仅拼枚举列名，值均参数绑定；秘钥无硬编码；审计 CSV 防公式注入；前端 mdLite 先 esc 后渲染。
- pytest 实测：agent-platform 26/26、multica-platform 5/5 真实通过。
- 权限守卫、AES-256-GCM 凭证加密、OAuth state 一次性、激励闭环、Excel 解析、1000 条数据幂等自愈均有具体断言的测试。
- 钉钉"真实扫码未完成"在 PRD/R5 报告如实披露，未夸大。
