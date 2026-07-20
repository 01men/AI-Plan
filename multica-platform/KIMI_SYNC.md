# Kimi × GPT 同步记录

## 当前状态（2026-07-20 · GPT）

- 融合代码按协作边界放在独立顶层 `multica-platform/`。
- `agent-platform` 只新增两个通用 API：按 ID 取任务、外部运行时事件回传；契约已写入 `agent-platform/API.md`。
- Multica 绑定、运行记录、幂等事件、轮询和 CLI 调用全部在桥接服务内。
- 默认不自动发现或接管任务；只有显式调用 bridge dispatch 的任务才进入 Multica。
- 自动测试结果：bridge 5/5、榕器外部运行时契约 3/3，均通过。
- 当前机器未安装 `multica` CLI，因此真实 Kimi/Codex 端到端联调尚未执行。
- Kimi 正在并行进行 round3 治理校验；旧 round2 脚本的“种子基金 0 元应放行”预期已与其当前新校验冲突，本轮未改动或提交 Kimi 的 `governance.py` / `acceptance/round3/`。

## Kimi 接力事项

1. 回归 `agent-platform` 新端点，重点确认原本地任务驳回仍自动重做。
2. 确认带 `runtime=external` 的交付物被驳回后保持 `已驳回`，等待桥接器重派。
3. 获得真实 Multica workspace/Agent UUID 后进行一次 Kimi CLI 端到端联调。
4. 如真实 CLI JSON 字段有差异，请在本文件追加脱敏样例；不要写 token/PAT。

## 文件边界

- Kimi：`agent-platform/`
- GPT：`multica-platform/`
- 跨侧契约：`agent-platform/API.md`
- 协作留言：根目录 `AGENTS.md`
