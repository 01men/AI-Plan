# 全新部署验收三项复测记录（2026-07-29，R7+）

> 背景：验收反馈 ①数字员工无法模型对话 ②知识库无法解析 Excel ③缺默认 1000 条业务数据。
> 本机实证三项功能正常后，判定为"全新部署开箱缺口"（模型 Key 不入 Git），遂做干净环境实测 + 演示降级 + 引导完善。

## 一、干净环境实测（`D:\项目\榕器创\fresh-deploy-test\`，空库启动 8765 端口）

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 空库启动自动播种 | PASS | `business_records` 恰好 1000 条，售后工单/库存流水/生产报工/质量检验/销售订单各 200 |
| 2 | xlsx 双工作表上传 | PASS | `converted_format=sqlite+csv`，`sheet_订单表`/`sheet_回款表` 两数据集，预览与 CSV 下载（带 BOM）均正常 |
| 3 | xls（BIFF 旧格式）上传 | PASS | xlrd 分支解析正常，数值类型保留 |
| 4 | 无 Key 聊天（修复前） | 优雅降级 | HTTP 200，`model_info.ok=false, reason=未配置可用模型`，文案指引明确 |
| 5 | 业务数据 API | PASS | `GET /api/knowledge/business-data` → `total:1000`，五类汇总齐全 |
| 6 | 登录页浏览器 | PASS | console `error_count:0`（仅 Tailwind JIT 已知 warning） |

干净环境未发现 Excel/种子数据的真实 bug，未做代码改动。

## 二、本轮修复（针对"开箱即可演示"）

1. **demo 演示回复降级**（`app/engine.py:468-525`）：demo 模式无模型 Key 时，`chat_with_agent` 生成带实质内容的演示回复——数字员工 persona + 项目上下文 + 知识库/业务数据召回 + 下一步建议，开头明确标注**【演示回复·未配置模型算力】**，`model_info.demo_reply=true`，`llm_calls` 留痕 `demo_reply`；production 模式保持硬错误，绝不冒充真实模型。
2. **配置引导**：聊天 toast/气泡/交付卡片在未配置模型时追加"请在 数字员工→模型 中配置 Key 并测试连接"（`app.js:1090,1128,1221`）；`启动平台.bat:33-41` 启动前检测 Key 配置状态并打印提示（不阻断）。
3. **README 新增"八、全新部署验收清单"**：安装→启动→（可选）配 Key→三项验收动作与预期结果，注明无 Key 时 demo 演示回复非故障。

## 三、终态验证

- 干净环境同步新代码复测：无 Key 聊天返回 `demo_reply:true`，回复含演示标注+persona+业务数据召回；`business_records=1000`；`llm_calls` 留痕 demo_reply。
- `agent-platform` pytest **40/40**（含新增 `test_r7_fresh_deploy.py` 2 项：demo 降级契约 / production 硬错误）；`multica-platform` **5/5**。
- 本机有 Key 环境：qwen 真实模型对话不受影响（此前已实证 `ok:true`）。
