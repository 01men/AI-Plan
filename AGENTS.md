# 项目说明与协作约定

## 项目内容

- `AI数智化企业应用推广行动方案 V2.html` — 金华聚杰电器行动方案文档（需求来源）
- `agent-platform/` — 榕器·Agent人机协作平台（FastAPI + SQLite + 原生 SPA），详见其 README.md

## Git 同步约定（重要）

- 远程仓库：**https://github.com/01men/AI-Plan.git**，分支 `main`
- **每次代码更新完成后都必须提交并推送**：`git add -A && git commit -m "<中文简述>" && git push`
- 提交信息用中文，说明改动要点
- `.gitignore` 已排除：数据库文件（`agent-platform/data/*.db*`）、`__pycache__`、服务日志、验收截图 PNG（验收报告 md 需入库）
- 数据库为运行时产物，删库重启自动播种，不入库

## 验收迭代约定

- 验收团队章程：`agent-platform/acceptance/charter.md`
- 每轮验收报告存 `agent-platform/acceptance/round<N>/`，验收与修复完成后随代码一并推送
