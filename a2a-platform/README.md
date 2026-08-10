# 榕器 A2A 协作控制面（v3.1）

本目录替代原 `multica-platform` 桥接器作为 A2A 基座。榕器仍是项目、审批、权限与业务状态的唯一真相源；本服务只负责资源绑定、最小授权、可靠派发、远端运行账本、产物审核和人工接管。

`multica-platform/` 保留为历史兼容实现，不再扩展。需要接入 Codex/Kimi CLI 时，应部署一个**独立、隔离的远端 Runner Agent**，将其以 Native A2A 或受控 HTTP Agent 形式登记到本控制面；禁止将 CLI 放入本服务或榕器 Web/API 进程。

## 启动

```bash
cd a2a-platform
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8200
```

访问 `http://127.0.0.1:8200` 打开管理员的资源绑定与运行台。首期 SQLite 仅支持单实例 Worker；扩为多进程/多机前必须迁移 PostgreSQL 与独立消息队列。

## 必需环境变量

| 变量 | 说明 |
|---|---|
| `A2A_DB_PATH` | SQLite 账本路径，默认 `data/control.db` |
| `A2A_ADMIN_TOKEN` | 管理接口保护令牌；生产必须设置 |
| `A2A_SIGNING_KEY` | 单任务授权签名密钥；生产必须使用密钥服务注入 |
| `A2A_DEFAULT_TIMEOUT_SECONDS` | 远端任务默认超时 |

## 原生 A2A 最小契约

远端 Agent 需提供：

- `GET /.well-known/agent-card.json`，至少返回 `name`、`version` 与 `capabilities` 或 `skills`；
- `POST /a2a/tasks`，接收 `{contract, authorization}` 并返回唯一 `run_id`；
- 控制面通过 `POST /api/runs/{run_id}/events` 接收严格递增序号的运行事件。

支持事件：`started`、`progress`、`input_required`、`deliverable`、`failed`、`cancelled`。`deliverable` 只进入 `Review`；人工审核通过后才是 `Completed`，不等价于业务写回。

## 安全边界

- 首期只接受 L1/L2 数据与 T0/T1 工具；`forbid` 或 `suggest` 写策略，`suggest` 也必须有已审批票据。
- 授权令牌为签名、短期、单任务范围，不含平台全量凭据。
- 远端资源须经历登记 → 发现 → 无副作用沙箱验证 → 审批 → 启用；解绑会撤销新派发，且在途任务必须先转人工或取消。
- Outbox 使用事务、租约、幂等键、指数退避和死信记录；超时/失败三次后转 `Degraded`，不会盲目创建第二个远端动作。

## 验证

```bash
pytest -q
```

测试启动真实 HTTP 协议形状的 Agent Card / A2A 服务，覆盖绑定、审批、最小授权、派发、重复事件、乱序拒绝、审核重做、离线降级、人工接管与解绑保护。
