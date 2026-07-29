# 第五轮终轮交付验收报告（R5 终极优化回归）

- 日期：2026-07-29
- 环境：`http://127.0.0.1:8000`，本地 SQLite，当前 main（Kimi × GPT 合并态）
- 范围：round4 报告 P0×3 / P1×5 整改项逐条销项 + 8 角色全旅程代入回归 + 离线可用性验证
- 依据：`acceptance/charter.md` 章程、`acceptance/round4/real-config-acceptance.md` 放行门槛
- 结论：**通过，达到交付验收线，建议明日向客户演示**

## 一、round4 放行门槛逐条销项

| # | round4 门槛 | 本轮结果 | 证据 |
|---|---|---|---|
| 1 | 非成员工作区的列表/消息/任务/知识文件无法读写 | ✅ 已修复 | 统一权限守卫 `app/access.py`：boss/coach 全局，其余按成员关系（backbone 兼顾本部门场景）；越权一律 403/404。徐露璐仅见 1 个工作区（原 9 个），越权读消息/任务被拦截 |
| 2 | 每位 staff 至少一条可执行路径，员工不可用时有明确兜底 | ✅ 已修复 | 派活兜底 `engine.handle_undispatched`：下线员工明示原因+负责人、推荐在线员工、自动登记「待处理」需求任务；徐露璐发言后拿到任务 #待派活 并可追踪 |
| 3 | 两个模型通过「测试连接」和真实出件，错误可见、回退可追溯 | ✅ 已修复 | 新增 `POST /api/models/{key}/test`；`llm_calls` 留痕（供应商/模型/耗时/成败/回退原因）；交付卡片 `model_info` 溯源。实测 qwen 真实出件 490 字非模板交付物，留痕 `ok/17157ms` |
| 4 | 凭证不明文存储 | ✅ 已修复 | `app/crypto.py` AES-256-GCM，主密钥取 `PLATFORM_MASTER_KEY` 或本地 `data/master.key`；库内全部为 `enc:v1:` 密文（kimi/qwen/dingtalk 已迁移），返回与审计持续脱敏 |
| 5 | 钉钉真人扫码链路 + 内网不依赖公共 CDN | ✅ 平台侧就绪 | OAuth state 一次性防重放（`app/security.py`）、免登录授权入口、服务端二维码（`GET /api/auth/oauth/qr`）；Tailwind/ECharts/QRCode 全部本地化 `app/static/vendor/`，页面零外部引用。真人扫码需客户现场手机确认，demo 绑定兜底可演示 |
| 6 | 8 角色回归达章程合格线 | ✅ 通过 | 自动化回归 33/33 通过（见下），无阻塞、无严重 |

## 二、8 角色代入回归（自动化，33/33 通过）

- 脚本：`acceptance/round5/regression.py`（真实 API 全旅程）
- 结果明细：`acceptance/round5/regression-results.json`

| 角色 | 关键旅程 | 结果 |
|---|---|---|
| 董事长 | 投入 34.29 万/ROI 57.5% 口径、KPI 八项、阶段门签核 | 5/5 |
| 师圆圆(coach) | 申报→立项→自动建区→派活→审核计绩效→激励档位校验 | 4/4 |
| 戴栓(backbone) | 组织树 5 平台 28 部门、覆盖率双口径 | 2/2 |
| 胡鑫(developer) | 三区发言、私聊打磨、@派活兜底提示、无权审核 403 | 4/4 |
| 徐露璐(staff·最低门槛样本) | 只见本人工作区、越权拦截、兜底登记可追踪、无权审核 403 | 5/5 |
| 杨思严(财务) | 投入三科目口径、报销三级分权全流程、审计筛选 | 5/5 |
| 李丹(HR) | 五层梯队、激励档位下限、人级考核数据（`GET /api/metrics/people`） | 3/3 |
| 范丁鑫(IT) | 六大红线、知识密级、422 中文化、越权拦截 | 4/4 |

## 三、自动化测试

- `agent-platform`：13/13 通过（既有外部运行时契约 3 + R5 权限/兜底/加密/回落留痕 10）
- `multica-platform`：5/5 通过（桥接契约无回归）

## 四、离线可用性（内网交付硬性要求）

- `app/static/index.html` 与 `app.js` 已无任何外部 CDN 引用；Tailwind/ECharts/QRCode 本地 vendor；
- 无头 Chrome 实测：驾驶舱图表、徐露璐 scoped 侧边栏（仅协作空间/任务中心/知识库）、三区交互全部正常渲染。
- 截图：`round5/dashboard_boss.png`、`round5/ws_xululu.png`

## 五、真实模型复验

- qwen（round4 配置的真实 Key）经平台生成：任务交付物 490 字，非模板占位；`llm_calls` 记录 `qwen/qwen3.7-flash ok 17157ms`；交付卡片带 `model_info`。
- 温度/超时/base_url 可按供应商配置（Kimi Coding 类需 temperature=1 的场景已可适配），配置弹窗内置「测试连接」。

## 六、遗留说明（不阻塞交付）

- 钉钉真人扫码五步闭环需客户现场用手机确认；平台侧授权页、二维码、回调、绑定落库已就绪，演示环境用 demo 绑定兜底。
- 演示库为保留真实模型/钉钉配置未重置；如需纯净初始数据，删 `data/platform.db` 重启自动播种（加密配置会丢失需重配）。
