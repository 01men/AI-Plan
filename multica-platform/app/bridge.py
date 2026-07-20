from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime

from app.config import Config
from app.database import db_session
from app.multica_cli import (
    PRIORITY,
    MulticaCLI,
    MulticaError,
    deliverable,
    issue_identity,
    issue_status,
    latest_run_id,
)
from app.rongqi_client import RongqiAPIError, RongqiClient


class BridgeError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


class Bridge:
    def __init__(self, config: Config, rongqi: RongqiClient | None = None,
                 multica: MulticaCLI | None = None):
        self.config = config
        self.rongqi = rongqi or RongqiClient(
            config.rongqi_api_url, config.rongqi_api_token, config.rongqi_person_id)
        self.multica = multica or MulticaCLI(
            config.multica_cli, config.multica_profile, config.multica_timeout_seconds)

    def list_bindings(self) -> list[dict]:
        with db_session(self.config.bridge_db_path) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM bindings ORDER BY local_agent_id")]

    def upsert_binding(self, local_agent_id: int, data: dict) -> dict:
        external_id = str(data.get("external_agent_id") or "").strip()
        external_name = str(data.get("external_agent_name") or "").strip()
        if not (external_id or external_name):
            raise BridgeError("external_agent_id / external_agent_name 至少填写一个")
        now = _now()
        with db_session(self.config.bridge_db_path) as conn:
            conn.execute(
                "INSERT INTO bindings(local_agent_id,external_agent_id,external_agent_name,"
                "external_workspace_id,external_project_id,enabled,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(local_agent_id) DO UPDATE SET "
                "external_agent_id=excluded.external_agent_id,"
                "external_agent_name=excluded.external_agent_name,"
                "external_workspace_id=excluded.external_workspace_id,"
                "external_project_id=excluded.external_project_id,"
                "enabled=excluded.enabled,updated_at=excluded.updated_at",
                (local_agent_id, external_id or None, external_name or None,
                 str(data.get("external_workspace_id") or "").strip() or None,
                 str(data.get("external_project_id") or "").strip() or None,
                 1 if data.get("enabled", True) else 0, now, now))
            conn.commit()
            return dict(conn.execute(
                "SELECT * FROM bindings WHERE local_agent_id=?", (local_agent_id,)).fetchone())

    def _binding(self, conn, agent_id: int):
        return conn.execute(
            "SELECT * FROM bindings WHERE local_agent_id=? AND enabled=1", (agent_id,)).fetchone()

    def _workspace_id(self, binding) -> str:
        value = binding["external_workspace_id"] or self.config.multica_workspace_id
        if not value:
            raise BridgeError("绑定和环境变量均未配置 Multica workspace_id")
        return value

    def _send_event(self, task_id: int, event_key: str, event_type: str,
                    content: str = "", metadata: dict | None = None) -> dict:
        payload = {"event_id": event_key, "event_type": event_type, "content": content,
                   "metadata": metadata or {}}
        with db_session(self.config.bridge_db_path) as conn:
            existing = conn.execute("SELECT * FROM events WHERE event_key=?", (event_key,)).fetchone()
            if existing and existing["status"] == "processed":
                return {"ok": True, "idempotent": True}
            now = _now()
            conn.execute(
                "INSERT INTO events(event_key,local_task_id,direction,event_type,payload,status,"
                "created_at) VALUES(?,?,'outbound',?,?,'pending',?) "
                "ON CONFLICT(event_key) DO UPDATE SET status='pending',error=NULL,payload=excluded.payload",
                (event_key, task_id, event_type, json.dumps(payload, ensure_ascii=False), now))
            conn.commit()
        try:
            result = self.rongqi.post_external_event(
                task_id, event_id=event_key, event_type=event_type, content=content,
                metadata=metadata or {}, source="multica")
            with db_session(self.config.bridge_db_path) as conn:
                conn.execute("UPDATE events SET status='processed',processed_at=?,error=NULL "
                             "WHERE event_key=?", (_now(), event_key))
                conn.commit()
            return result
        except RongqiAPIError as exc:
            with db_session(self.config.bridge_db_path) as conn:
                conn.execute("UPDATE events SET status='failed',error=? WHERE event_key=?",
                             (str(exc), event_key))
                conn.commit()
            raise BridgeError(str(exc)) from exc

    def dispatch(self, task_id: int) -> dict:
        with db_session(self.config.bridge_db_path) as conn:
            existing = conn.execute("SELECT * FROM runs WHERE local_task_id=?", (task_id,)).fetchone()
            if existing and existing["external_issue_id"]:
                return {"ok": True, "idempotent": True, "run": dict(existing)}
        task = self.rongqi.get_task(task_id)
        if not task.get("agent_id"):
            raise BridgeError("本地任务尚未指派数字员工")
        with db_session(self.config.bridge_db_path) as conn:
            binding = self._binding(conn, int(task["agent_id"]))
            if not binding:
                raise BridgeError("该数字员工尚未绑定 Multica Agent")
            binding = dict(binding)
        workspace_id = self._workspace_id(binding)
        description = (
            f"[榕器平台任务 #{task_id}]\n\n{task.get('requirement') or task['title']}\n\n"
            "协作约束：请报告进度、阻塞与最终交付物。完成后必须回到榕器平台人工审核；"
            "未经审核不得写回业务系统或对外发布。")
        try:
            result = self.multica.create_issue(
                title=f"[榕器#{task_id}] {task['title']}", description=description,
                priority=PRIORITY.get(task.get("priority"), "medium"), workspace_id=workspace_id,
                assignee_id=binding.get("external_agent_id") or "",
                assignee_name=binding.get("external_agent_name") or "",
                project_id=binding.get("external_project_id") or "",
                due_date=task.get("deadline") or "")
            issue_id, issue_key = issue_identity(result)
        except MulticaError as exc:
            raise BridgeError(str(exc)) from exc
        now = _now()
        with db_session(self.config.bridge_db_path) as conn:
            conn.execute(
                "INSERT INTO runs(local_task_id,local_agent_id,external_issue_id,external_issue_key,"
                "external_status,state,created_at,updated_at) VALUES(?,?,?,?,?,'queued',?,?) "
                "ON CONFLICT(local_task_id) DO UPDATE SET "
                "external_issue_id=excluded.external_issue_id,external_issue_key=excluded.external_issue_key,"
                "external_status=excluded.external_status,state='queued',error=NULL,"
                "updated_at=excluded.updated_at",
                (task_id, task["agent_id"], issue_id, issue_key, "todo", now, now))
            conn.commit()
        self._send_event(
            task_id, f"dispatch:{issue_id}", "started",
            f"任务 #{task_id} 已进入 Multica 执行队列（{issue_key or issue_id}）。",
            {"external_issue_id": issue_id, "external_issue_key": issue_key,
             "external_status": "todo"})
        with db_session(self.config.bridge_db_path) as conn:
            run = dict(conn.execute("SELECT * FROM runs WHERE local_task_id=?", (task_id,)).fetchone())
        return {"ok": True, "idempotent": False, "run": run}

    def _update_run(self, task_id: int, **values):
        allowed = {"external_status", "state", "last_deliverable_hash", "error"}
        fields = [(key, value) for key, value in values.items() if key in allowed]
        if not fields:
            return
        with db_session(self.config.bridge_db_path) as conn:
            sql = "UPDATE runs SET " + ",".join(f"{key}=?" for key, _ in fields) + ",updated_at=? WHERE local_task_id=?"
            conn.execute(sql, [value for _, value in fields] + [_now(), task_id])
            conn.commit()

    def _sync_one(self, run: dict) -> dict:
        task_id = int(run["local_task_id"])
        task = self.rongqi.get_task(task_id)
        with db_session(self.config.bridge_db_path) as conn:
            binding_row = self._binding(conn, int(run["local_agent_id"]))
            if not binding_row:
                raise BridgeError("运行记录对应的数字员工绑定已停用")
            binding = dict(binding_row)
        workspace_id = self._workspace_id(binding)
        issue_id = run["external_issue_id"]

        # 榕器平台拥有最终审核权；审批结果反向同步到 Multica。
        if task["status"] == "已通过" and run["state"] != "approved":
            self.multica.add_comment(
                issue_id, f"榕器平台人工审核通过。批注：{task.get('review_comment') or '无'}",
                workspace_id)
            self.multica.set_status(issue_id, "done", workspace_id)
            self._update_run(task_id, external_status="done", state="approved", error=None)
            return {"task_id": task_id, "state": "approved"}
        if task["status"] == "已驳回" and run["state"] == "waiting_human_review":
            comment = task.get("review_comment") or "未填写具体意见"
            self.multica.add_comment(issue_id, f"榕器平台人工审核驳回，请重做：{comment}",
                                     workspace_id)
            self.multica.set_status(issue_id, "todo", workspace_id)
            marker = _digest(comment)
            self._send_event(
                task_id, f"rework:{issue_id}:{marker}", "started",
                f"任务 #{task_id} 的驳回意见已发送至 Multica，等待 Agent 重做。",
                {"external_issue_id": issue_id, "external_status": "todo", "rework": True})
            self._update_run(task_id, external_status="todo", state="queued", error=None)
            return {"task_id": task_id, "state": "queued", "rework": True}

        detail = self.multica.get_issue(issue_id, workspace_id)
        status = issue_status(detail)
        state = "running"
        if status in ("backlog", "todo", "in_progress"):
            if status != run.get("external_status"):
                self._send_event(
                    task_id, f"status:{issue_id}:{status}", "progress",
                    f"Multica 任务 {run.get('external_issue_key') or issue_id} 状态更新为 {status}。",
                    {"external_issue_id": issue_id, "external_status": status})
        elif status == "blocked":
            state = "blocked"
            self._send_event(
                task_id, f"status:{issue_id}:blocked", "blocked",
                f"Multica 报告任务 #{task_id} 受阻，请人工查看外部 Issue。",
                {"external_issue_id": issue_id, "external_status": status})
        elif status in ("in_review", "done"):
            run_id = latest_run_id(self.multica.issue_runs(issue_id, workspace_id))
            output = deliverable(self.multica.run_messages(run_id, workspace_id)) if run_id else ""
            if output:
                output_hash = _digest(output)
                state = "waiting_human_review"
                if output_hash != (run.get("last_deliverable_hash") or ""):
                    self._send_event(
                        task_id, f"deliverable:{issue_id}:{output_hash}", "deliverable", output,
                        {"external_issue_id": issue_id, "external_issue_key": run.get("external_issue_key"),
                         "external_status": status, "external_run_id": run_id})
                    self._update_run(task_id, last_deliverable_hash=output_hash)
            else:
                state = "waiting_output"
        elif status == "cancelled":
            state = "cancelled"
            self._send_event(
                task_id, f"status:{issue_id}:cancelled", "cancelled",
                f"Multica 已取消任务 #{task_id}。",
                {"external_issue_id": issue_id, "external_status": status})
        else:
            state = "unknown"
        self._update_run(task_id, external_status=status, state=state, error=None)
        return {"task_id": task_id, "external_status": status, "state": state}

    def sync(self, task_id: int | None = None, limit: int = 50) -> list[dict]:
        with db_session(self.config.bridge_db_path) as conn:
            sql = "SELECT * FROM runs WHERE external_issue_id IS NOT NULL AND state!='approved'"
            args = []
            if task_id:
                sql += " AND local_task_id=?"
                args.append(task_id)
            sql += " ORDER BY id LIMIT ?"
            args.append(max(1, min(limit, 200)))
            runs = [dict(row) for row in conn.execute(sql, args)]
        results = []
        for run in runs:
            try:
                results.append(self._sync_one(run))
            except (BridgeError, MulticaError, RongqiAPIError) as exc:
                self._update_run(run["local_task_id"], state="sync_failed", error=str(exc))
                results.append({"task_id": run["local_task_id"], "state": "sync_failed",
                                "error": str(exc)})
        return results

    def list_runs(self, limit: int = 100) -> list[dict]:
        with db_session(self.config.bridge_db_path) as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),))]

    def list_events(self, limit: int = 100) -> list[dict]:
        with db_session(self.config.bridge_db_path) as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),))]

