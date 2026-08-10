# A2A 控制面 API

所有写接口可设置 `X-A2A-Token`；审计身份来自 `X-Actor`。生产必须设置管理令牌。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/resources` | 登记 Agent/知识库/Skill/MCP 资源 |
| POST | `/api/resources/{id}/discover` | 读取标准 Agent Card |
| POST | `/api/resources/{id}/sandbox-validate` | 无副作用可达/认证/执行/容量检查 |
| POST | `/api/resources/{id}/enable` | 以审批票据启用 |
| POST | `/api/resources/{id}/pause` / `unbind` | 暂停/安全解绑 |
| POST | `/api/approvals`、`/{id}/decision` | 创建、决定审批票据 |
| POST | `/api/contracts` | 事务创建不可变六段式任务契约与 Outbox |
| POST | `/api/worker/tick` | 手动触发派发（生产由后台 Worker 调用） |
| POST | `/api/runs/{id}/events` | 远端回调（携带该任务的 `Authorization: Bearer <短期授权>`；事件 ID 幂等、序号单调递增） |
| POST | `/api/contracts/{id}/review` | 审核采纳或驳回重做 |
| POST | `/api/contracts/{id}/input` / `takeover` | 补料恢复 / 人工接手 |

### `POST /api/contracts`

```json
{"idempotency_key":"pmo-minutes-20260807-001","subject":"经营例会行动项","resource_id":"<已启用 Agent ID>","role":"经营 PMO 助理","skills":["pmo.readonly"],"tools":[{"name":"minutes_parser","tier":"T0"}],"data_scope":[{"ref":"meeting:2026-08-07","level":"L2"}],"write_policy":"forbid","runtime":{"timeout_seconds":300,"fallback":"human_takeover"},"input_payload":{"minutes":"…"}}
```

### `POST /api/runs/{id}/events`

```json
{"event_id":"remote-001:2","sequence":2,"event_type":"deliverable","artifact":"行动项建议…","provenance":{"source":"meeting:2026-08-07"}}
```

事件重复提交返回 `idempotent: true`；小于当前序号的事件被拒绝，不能覆写新状态。
