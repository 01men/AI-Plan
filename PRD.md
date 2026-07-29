# 榕器 · Agent 人机协作平台 — 产品需求与进度管理（PRD）

> 本文档是项目的**全局进度契约**，供 Kimi 与 ChatGPT（Multica 侧）协作开发时对齐。
> 规则：每次开始开发前先看本文档认领任务；完成后更新状态并随代码推送。协作边界见根目录 `AGENTS.md`。

- 仓库：https://github.com/01men/AI-Plan （main 分支）
- 平台代码：`agent-platform/`（Kimi 维护）；Multica 融合：`multica-platform/`（GPT 维护）
- 运行：双击 `agent-platform/启动平台.bat` → http://127.0.0.1:8000（FastAPI + SQLite + 原生 SPA）
- 最近更新：2026-07-20（Kimi）

---

## 一、产品定位

承载金华聚杰电器《AI数智化企业应用推广行动方案（V3）》的落地：以"数字员工（AI Agent）是正式员工"为核心，提供组织管理、协作执行、项目管理、效能度量、治理保障五大能力，遵循 AI 原生协作理念（沟通即执行、三区交互、人在环路、心跳主动服务、低学习门槛）。

## 二、功能全景与进度

### 已完成（v1.0 → v1.3，经 3 轮 8 角色验收，全部"能落地"）

| 模块 | 功能 | 状态 | 负责 |
|---|---|---|---|
| 组织 | 5 平台 28 部门 48 人组织树、Teams.md 通讯录、梯队角色徽标 | ✅ | Kimi |
| 数字员工 | 65 个台账、状态机（规划中→开发中→试运行→已上线/已下线）、四波次、产出指标 | ✅ | Kimi |
| 协作空间 | 三区交互（讨论/Agent执行/私聊打磨）、@派活、交付卡片、内联审核、mdLite 渲染 | ✅ | Kimi |
| 任务 | 五列看板、人在环路审核（权限+禁自审）、驳回带意见重做、版本管理 | ✅ | Kimi |
| 场景库 | 81 场景、敏捷立项（自动建工作区+数字员工入区） | ✅ | Kimi |
| 项目流程 | V3 泳道承载：N01-N40 模板、G1-G4 阶段门签核、tick 自动推进、关键路径延迟预警、泳道可视化 | ✅ | Kimi |
| 效能度量 | 七维 KPI 驾驶舱、双口径覆盖率、ROI 57.5%、投入构成方案口径、心跳日报 | ✅ | Kimi |
| 治理 | 激励三级奖+档位校验、Token 报销三级分权审批、审计留痕、六大红线 | ✅ | Kimi |
| 知识库 | 6 套 NAS 空间、L1-L4 密级文档台账 | ✅ | Kimi |
| 执行引擎 | 模板模拟交付物 + OpenAI 兼容 LLM 适配（settings 三键） | ✅ | Kimi |
| Multica 桥接 | 外部运行时事件回传（幂等）、按 ID 取任务、驳回保持待重派 | ✅ | GPT |

### 本轮迭代（R4 · 6 项，2026-07-20 完成）

| # | 需求 | 验收要点 | 状态 | 负责 |
|---|---|---|---|---|
| R4-1 | **Agent 模型可配置**：内置 GLM/Kimi/MiniMax/DeepSeek/通义（OpenAI 兼容），全局默认+单员覆盖，无 Key 回落模板 | 模型清单内置；Agent 详情可切换模型并配 Key；引擎按绑定调用 | ✅ | Kimi |
| R4-2 | **Skill 可维护 + Agent 角色自定义**：Skill 增删改；数字员工新建/编辑，绑定技能与 MCP 台账 | 界面维护全通；新建 Agent 绑技能/MCP/模型后详情可见 | ✅ | Kimi |
| R4-3 | **知识库上传与自动解析**：txt/md/docx/pdf→.md（pdf 走 pdftotext）、csv/json→SQLite、html→清洗，自动拆分 chunk+摘要 | 各格式转换正确、分块可查、产物可下载 | ✅ | Kimi |
| R4-4 | **钉钉/飞书绑定登录**：OAuth URL+二维码+回调绑定+演示模式 | 登录页/侧边栏入口、demo 绑定全流程、凭证配置脱敏 | ✅（真实扫码待免 token 入口，见 B-3） | Kimi |
| R4-5 | **场景库分类重构**：平台→部门两级分组、推荐排序+🔥徽章、排序切换 | 分组清晰、推荐分生效 | ✅ | Kimi |
| R4-6 | **执行链路可视化**：Agent 执行区顶部"过去→现在→未来"链路条，CSS 连线，跳完整流程 | 链路数据与流程引擎一致、随消息刷新 | ✅ | Kimi |

### 后续候选（Backlog，认领制）

| # | 需求 | 优先级 | 来源 |
|---|---|---|---|
| B-1 | 人级考核数据看板（HR：个人活跃度/产出/覆盖率） | 高 | 验收·李丹 |
| B-2 | 真实大模型 E2E 联调（Multica CLI 就位后） | 高 | GPT·KIMI_SYNC |
| B-3 | 钉钉/飞书真实扫码登录：后端需放开免 token 的"按 IM 账号取授权 URL"入口 + 本地客户端登录态识别 | 中 | R4-4 遗留 |
| B-4 | 422 错误提示全面中文化（pydantic 原文兜底） | 中 | 验收·范丁鑫 |
| B-5 | 激励池余量展示、审计日志导出 | 低 | 验收·李丹/杨思严 |
| B-6 | 场景库与方案文档 232 条全量对齐（现 81 条代表性子集） | 中 | V3 分析 |

## 三、R4 技术设计约定（开发前必读）

1. **模型配置**：表 `model_providers(key, name, base_url, default_model, api_key, enabled)`，内置 GLM（open.bigmodel.cn）/Kimi（api.moonshot.cn）/MiniMax（api.minimaxi.com）/DeepSeek/通义千问，均为 OpenAI 兼容接口；`agents.model_key` 为空时跟随 `settings.default_model_key`；引擎每次生成实时解析，异常静默回落模板（不联网、零成本演示原则不变）。
2. **MCP**：表 `mcp_servers(id,name,endpoint,description,status)`，agents 侧 JSON 数组绑定；本迭代只做台账绑定与展示，不做真实 MCP 调用。
3. **知识上传**：`POST /api/knowledge/spaces/{id}/upload`（multipart）；转换：txt/md/docx/pdf→.md（pdf 走系统 pdftotext，docx 走 zipfile+XML 提取），csv/json→SQLite（`data/knowledge/`），html/htm→清洗后 .html；产物存 `data/uploads/`；`doc_chunks` 表按标题/段落拆分（≈500 字/块）+ 摘要。
4. **IM 绑定**：`auth_providers` + `user_bindings` 表；授权 URL 按钉钉/飞书标准 OAuth 拼接；二维码用前端 CDN 库生成；无凭证走演示模式（回调模拟用户绑定）；token/secret 不落日志不入库展示。
5. **场景推荐分**：`score = 优先级权重(高3/中2/低1) + 预期收益归一化 + 首批试点加成(2)`，降序排列。
6. **执行链路**：`GET /api/workspaces/{id}/chain` 聚合消息/任务历史与 project_flows 后续节点；前端横向链路条（✅完成/🔵进行中/⚪未来），CSS 连线。

## 四、变更日志

- 2026-07-19 Kimi：v1.0 平台全量（10 视图）+ 三轮验收迭代（合格线全达标）
- 2026-07-20 GPT：Multica 桥接器 + 外部运行时契约端点
- 2026-07-20 Kimi：项目流程引擎（V3 泳道 N01-N40 + G1-G4）
- 2026-07-20 Kimi：R4 六项迭代启动（本 PRD 建档）
