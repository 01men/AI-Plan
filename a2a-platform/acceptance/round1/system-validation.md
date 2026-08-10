# A2A v3.1 阶段 0/1 系统验证记录

执行基线：`AI-Native协作系统重构方案-A2A底座-v3.1-执行版`。验证范围为首期“经营 PMO / 会议纪要—行动项闭环”，严格保持 L1/L2、T0/T1 与只读/建议模式；没有开放 ERP、PLM、MES、邮件或质量系统写回。

## 结果

| 类别 | 验证项 | 结果 |
|---|---|---|
| 功能 | 资源登记、Agent Card 发现、沙箱验证、审批启用 | 通过 |
| 功能 | 六段式契约、短期签名授权、Outbox 派发 | 通过 |
| 功能 | 远端 `started`/`deliverable` 回调、审核、驳回重做 | 通过 |
| 功能 | 暂停/解绑、在途任务阻断、人工接管 | 通过 |
| 可靠性 | 重复契约幂等、重复事件幂等、乱序事件拒绝 | 通过 |
| 可靠性 | 远端连接失败三次重试、死信、降级 | 通过 |
| 安全 | L3/T2 拒绝、篡改任务令牌拒绝、回调令牌与 Run 绑定 | 通过 |
| 环境 | 控制面 `/health`、资源 API、管理页 HTTP 启动检查 | 通过 |
| 数据 | 榕器干净启动后业务展示数据接口 | 通过：1000 条、5 类、抽样 `DEMO-0185` |

## 实测命令与输出

```text
a2a-platform: .venv/bin/python -m pytest -q
5 passed in 2.01s

agent-platform: .venv/bin/python -m pytest -q
40 passed, 2 warnings in 1.34s

multica-platform: ../agent-platform/.venv/bin/python -m pytest -q
5 passed in 0.20s

agent-platform HTTP 数据接口：business_total=1000; categories=5; sample=DEMO-0185
a2a-platform HTTP 启动检查：health=ok; resources_status=200; page_status=200
```

## 真正外部联调的边界

本轮 A2A 验证启动了真实 HTTP 监听的 Agent Card / `POST /a2a/tasks` 服务，并通过网络协议完成发现和派发；它不是对某个已部署生产 Agent 的声明。当前工作区没有经授权的远端 Agent/Runner 地址、mTLS/OAuth 凭据、真实会议纪要或企业业务数据访问授权，因此以下项目**不能伪称已完成真实生产验证**：

1. 原生 A2A、C 类隔离 CLI Runner、本地推理引擎三种外部服务的真实绑定与 60 秒心跳；
2. 企业真实会议纪要到行动项的业务采纳验证，以及人工处理基线、节省工时、一次通过率等指标；
3. ERP/PLM/MES/邮件/质量系统写回（按方案本来就不属于首期范围）。

取得上述受控测试服务与脱敏业务数据后，可直接按 `README.md` 的协议登记资源，并以本报告的自动化测试作为验收回归基线。
