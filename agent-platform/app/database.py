"""数据库连接与建表 DDL（仅使用标准库 sqlite3）"""
import sqlite3
from pathlib import Path

# 数据库文件固定放在项目根的 data/ 下
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "platform.db"


def get_db() -> sqlite3.Connection:
    """获取一个独立的数据库连接（row_factory=sqlite3.Row，支持外键）。

    并发修复说明：
    - check_same_thread=False：FastAPI 把同步依赖与端点分别调度到线程池的
      不同线程执行，默认 True 时连接跨线程使用会抛 sqlite3.ProgrammingError
      （并发 500 的根因）；每个请求本来就用独立连接，关闭该检查是安全的。
    - journal_mode=WAL：读写不互斥，多连接并发读不阻塞。
    - busy_timeout=5000：写冲突时等待至多 5 秒而非立即报 database is locked。
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


DDL = """
CREATE TABLE IF NOT EXISTS platforms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT,
    headcount INTEGER DEFAULT 0,
    color TEXT
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER NOT NULL REFERENCES platforms(id),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_id INTEGER NOT NULL REFERENCES departments(id),
    name TEXT NOT NULL,
    role_title TEXT,
    tier TEXT,          -- boss/coach/backbone/developer/staff
    direction TEXT,
    status TEXT DEFAULT '在职'
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_id INTEGER NOT NULL REFERENCES departments(id),
    name TEXT NOT NULL,
    code TEXT,
    category TEXT,      -- 业务/项目助理、智造运营/会议纪要、BOM/物料、质量/制程异常分析、研发测试/售后分析、综合事务
    description TEXT,
    status TEXT DEFAULT '规划中',  -- 规划中/开发中/试运行/试点中/已上线/已下线
    owner_id INTEGER REFERENCES people(id),
    wave INTEGER DEFAULT 4,        -- 波次 1-4
    skills TEXT DEFAULT '[]',      -- JSON 数组字符串
    tasks_done INTEGER DEFAULT 0,
    hours_saved REAL DEFAULT 0,
    accuracy REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_id INTEGER NOT NULL REFERENCES departments(id),
    agent_id INTEGER REFERENCES agents(id),
    name TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT '中',     -- 高/中/低
    batch TEXT,                     -- 首批/扩围
    status TEXT DEFAULT '待立项',   -- 待立项/已立项/开发中/试点中/已验收/已下线
    expected_benefit TEXT,
    actions TEXT DEFAULT '[]'       -- 场景动作 JSON 数组
);

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT DEFAULT '临时',       -- 项目/部门/临时
    scenario_id INTEGER REFERENCES scenarios(id),
    created_by INTEGER REFERENCES people(id),
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    member_type TEXT NOT NULL,      -- human/agent
    member_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    sender_type TEXT NOT NULL,      -- human/agent/system
    sender_id INTEGER,
    sender_name TEXT,
    zone TEXT DEFAULT 'discussion', -- discussion/agent/private
    msg_type TEXT DEFAULT 'text',   -- text/task_card/deliverable/approval/report
    content TEXT,
    payload TEXT,                   -- JSON 可空
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER REFERENCES workspaces(id),
    title TEXT NOT NULL,
    agent_id INTEGER REFERENCES agents(id),
    creator_id INTEGER REFERENCES people(id),
    reviewer_id INTEGER REFERENCES people(id),
    status TEXT DEFAULT '待处理',   -- 待处理/进行中/待审核/已通过/已驳回
    priority TEXT DEFAULT '中',
    requirement TEXT,
    deliverable TEXT,
    review_comment TEXT,
    deadline TEXT,
    created_at TEXT,
    done_at TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    scope TEXT DEFAULT '公开',      -- 公开/组织/个人
    category TEXT,
    owner_name TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_spaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    device TEXT,
    capacity TEXT,
    dept_name TEXT,
    domain TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id INTEGER NOT NULL REFERENCES knowledge_spaces(id),
    title TEXT NOT NULL,
    level TEXT,                     -- L1-L4
    tags TEXT,
    uploaded_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS metrics_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    agent_id INTEGER NOT NULL REFERENCES agents(id),
    tasks_done INTEGER DEFAULT 0,
    hours_saved REAL DEFAULT 0,
    token_cost REAL DEFAULT 0,
    accuracy REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase TEXT,
    month TEXT,
    name TEXT NOT NULL,
    owner TEXT,
    node_type TEXT,                 -- agent/hybrid/human
    status TEXT DEFAULT '未开始'    -- 未开始/进行中/已完成
);

CREATE TABLE IF NOT EXISTS incentives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,                      -- 火花奖/银齿轮奖/金扳手奖/种子基金
    nominee TEXT,
    reason TEXT,
    amount REAL,
    status TEXT DEFAULT '申报中',   -- 申报中/已评定/已发放
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS reimbursements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant TEXT,
    provider TEXT,
    tokens INTEGER,
    amount REAL,
    status TEXT DEFAULT '待平台长审批',  -- 待平台长审批/待数字化复核/待财务报销/已完成/已驳回
    step INTEGER DEFAULT 1,              -- 1-3
    comment TEXT,                        -- 各级审批意见逐行累加
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT,
    action TEXT,
    target TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """建表（幂等）"""
    conn.executescript(DDL)
    conn.commit()
