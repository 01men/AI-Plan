# R7 投资人尽调修复销项报告（2026-07-29）

> 对应问题清单：`round7/investor-dd-findings.md`（34 项）。本报告逐条销项：修复位置、验证证据、遗留说明。
> 验证基线：`agent-platform` pytest **38/38**（既有 26 + R7 新增 12）、`multica-platform` **5/5**。

## 一、后端安全与工程（B1-B16）——全部修复

| # | 修复 | 证据 |
|---|---|---|
| B1 | 生产模式关闭免密登录/演示 OAuth/公开花名册；离职会话立即 401；`/api/health/ready` 生产就绪探针（未配真实 IM/模型 503 且不含密钥） | `app/config.py`、`routers/auth.py:91-103`、`routers/org.py:46-53`、`routers/imbind.py`；`tests/test_r7_production_auth.py` 5 项 |
| B2 | HTML 上传清洗补 `on*=` 事件属性、`javascript:`/`data:text/html`、`<iframe>`；html 产物 `/file` 强制 `Content-Disposition: attachment` 不同源直出 | `routers/knowledge.py:444-456,698-701`；R7 测试 `test_html_upload_sanitizer_blocks_xss_vectors` |
| B3 | 私聊写入落 `private_owner_id`，zone=private 查询仅本人可见；模型对话上下文召回同口径过滤（`_chat_history` 补漏） | `engine.py:448-455,582-587,725,754`、`routers/workspaces.py:130,193`；R7 测试私聊隔离 2 项 |
| B4 | staff 直建任务 403；status 服务端强制 `待处理`；priority 枚举校验；reviewer_id 校验存在且在职 | `routers/tasks.py:81-92,111`；R7 测试 `test_client_cannot_forge_status_priority_reviewer` |
| B5 | 无工作区任务催办跳过消息只记审计；单任务异常 try/except 不影响日报 | `engine.py:880-889`、引擎侧 `_audit`(185) |
| B6 | 审核改 `UPDATE ... WHERE id=? AND status='待审核'`，rowcount=0 → 409；绩效累计在原子更新成功后 | `routers/tasks.py:270-276,299-303`；R7 测试 `test_double_approve_rejected` |
| B7 | 幂等改 `runtime_events` 表按 (task_id,source,event_id) 去重，settings 键方案删除；响应结构不变，bridge 契约兼容 | `routers/tasks.py:169-180`；R7 测试 `test_idempotency_scoped_per_task`；bridge 5/5 |
| B8 | 三处 payload 匹配改 `"task_id": {id},` / `"task_id": {id}}` 双模式 | `engine.py:639`、`tasks.py:233-237`、`workspaces.py:263-265`；R7 测试 `test_task_id_like_no_prefix_collision` |
| B9 | OAuth state/登录码/轮询改 `DELETE/UPDATE ... RETURNING` 单语句原子消费（sqlite 3.50.4） | `security.py:26,58`、`imbind.py:307` |
| B10 | decrypt 异常记审计并按"未配置"回落模板，不再穿透 500 | `engine.py:206-213,222-229` |
| B11 | 死表 `request_idempotency` DDL 删除；execution_mode 映射抽 `_execution_fields()` 三处共用 | `database.py`、`engine.py:590` |
| B12/B13 | content 上限 20000（422）；全部校验先于落库；list limit 封顶 500 | `workspaces.py:133,163-186`；R7 测试 2 项 |
| B14 | 同 B4（staff 403） | 同上 |
| B15 | list_flows N+1：当前数据量小，列入 backlog 观察项，未改行为 | — |
| B16 | API.md 同步：msg_type 补 `runtime_event`；公开入口补 `/api/environment`、`/api/health/ready`；`reviewer_id` 示例修正；幂等口径三元组；审计承诺改实；新增"15. R7 尽调加固契约" | `API.md` |

## 二、前端与体验（F1-F11）——除 backlog 项外全部修复

| # | 修复 | 证据 |
|---|---|---|
| F1 | `?person=<id>` URL 免密 impersonate 整段删除，仅保留 `?im_login=` 换发会话分支 | `app.js:3139-3145`（grep `urlPerson` 零引用） |
| F2 | 后端逐接口强制鉴权兜底（见 B1/B4 等 R7 加固与既有 R5 权限守卫测试）；前端 localStorage 角色仅作展示层 | `tests/test_r5_hardening.py` + R7 测试 |
| F3 | 新增 `jsStr(s)=JSON.stringify`，内联事件字符串参数一律 `esc(jsStr(x))`（JS 逃逸+HTML 属性截断双防，18 处）；流程节点 code/gate_code 补 esc；URL path 拼接加 encodeURIComponent；另修 IM/供应商配置/switchZone 等 8 处同类 | `app.js:58-62,1156,2268-2277,2976-3077` 等；Node 恶意输入回归 5 组无逃逸 |
| F4 | 收敛手段：XSS 面修复（F3）+ 401 处理优化（F10）；HttpOnly Cookie 会话重构列 backlog | — |
| F5 | Tailwind JIT 与字体：删 `Noto Sans SC` 无效声明保留系统字体栈；JIT 预编译化列 backlog（console 留痕中仅存此 1 条 warning，如实记录） | `index.html:24`、`round7/login.png.console.json` |
| F6 | 新增 `withBusy(btn,fn)` 防重入封装，全部 15 个 submit*/send* 接入（按钮禁用+spinner+finally 恢复） | `app.js:63-71` |
| F7 | 激励审批改 openModal 模态框（openIncentiveReviewModal + submitIncentiveReview），window.prompt 零残留 | `app.js:2556-2584` |
| F8 | 四下载点合并为 `downloadBlob(url,filename)`（appendChild+3s 后 revoke，兼容 Firefox），downloadProtected 删除 | `app.js:2286-2320` |
| F9 | KPI 目标值 `KPI_TARGET_DEFAULTS` + `/api/environment` 的 `kpi_targets` 覆盖（缺字段逐字回落）；NAS 默认设备提为常量 | `app.js:40,693-698`；驾驶舱截图目标值渲染正常 |
| F10 | `api()`/`uploadApi()` 401 仅当失败请求的 token 与当前一致才 doLogout，并发误伤消除 | `app.js:180-200,210-224` |
| F11 | `app.js` 模块化拆分列 backlog | — |

浏览器实测（无头 Chrome + 新增 console 留痕）：登录页与董事长驾驶舱 `error_count: 0`，仅 Tailwind JIT 1 条已知 warning；驾驶舱 KPI 目标值（70/85/60/95/790000）经 `kpi_targets` 下发渲染正常。
证据：`round7/login.png(.console.json)`、`round7/dashboard.png(.console.json)`。

## 三、文档/测试/交付（D1-D8）——全部修复

| # | 修复 | 证据 |
|---|---|---|
| D1 | KPI 目标值定义 `KPI_TARGETS` 于后端并注明"行动方案口径"，经 `/api/environment` 下发；PRD 改述"方案口径静态展示值，随运营数据积累切换实测" | `routers/metrics.py:30-38`、`config.py:53-58`、`PRD.md:29` |
| D2 | PRD Multica 行改标"契约级测试 5/5 通过；真实 CLI 端到端联调待环境，见 B-2" | `PRD.md:33` |
| D3 | round5 报告 33/33→32/32、"13/13"→18/18 更正并加更正说明（不抹历史） | `acceptance/round5/final-delivery-acceptance.md:18,20,38` |
| D4 | 新增 `tests/test_r7_investor_audit.py` 12 项：报销三级分权全流程、密级矩阵、G1 阶段门、任务防伪、重复审核、私聊隔离×2、XSS 清洗、按任务幂等、LIKE 防碰撞、发言校验×2 | 12/12 通过 |
| D5 | README 补 poppler/pdftotext 前提；`启动平台.bat` 加 pdftotext 检测提示与 8000 端口占用防护 | `README.md`、`启动平台.bat:21-33` |
| D6 | `cdp_shot.js` 采集 console/页面异常，随截图落 `<png>.console.json` 并打印错误汇总 | `acceptance/cdp_shot.js`（`node --check` 通过） |
| D7 | PRD 七维→八项 KPI；删"Teams.md 通讯录"不实产物改组织树视图；测试数口径统一 | `PRD.md:23,29` |
| D8 | 启动脚本端口检测（见 D5）；`requirements.txt` 移除零引用 `httpx`；README 注明"运行时离线，首次部署装依赖需联网" | `requirements.txt`、`README.md` |

## 四、不在本轮的外部依赖（保持诚实披露）

- Multica 真实 CLI E2E（待真实 workspace/Agent UUID）；钉钉正式回调现场首扫；正式域名 HTTPS 反代——PRD B 区维持原披露。
- Tailwind 构建期预编译化、HttpOnly Cookie 会话重构、`app.js` 模块化拆分、list_flows 批量查询——列入 backlog。

## 五、验证记录

- `agent-platform`：`pytest tests/ -q` → **38 passed**（21 既有 + 5 生产认证 + 12 尽调回归；其中 5 项生产认证为 GPT 在制基线，Kimi 接力提交）
- `multica-platform`：`pytest tests/ -q` → **5 passed**（external 运行时契约兼容）
- 8 角色代入真实 API 回归（round5 脚本，8001 端口新代码实例）：**32/32 通过**
- 浏览器实测：登录页与董事长驾驶舱 console `error_count: 0`（仅 Tailwind JIT 已知 warning 1 条），截图与 console JSON 留档于 `round7/`
- 后端修复另经两轮内存库冒烟脚本实证（XSS 输出、staff 403、跨任务幂等、条件更新 rowcount、decrypt 回落、心跳 NULL 工作区跳过）
- 回归产生的演示数据已用核验前备份恢复 `data/platform.db`（密文配置与千条展示数据不受影响）
