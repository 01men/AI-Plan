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
    private_owner_id INTEGER REFERENCES people(id), -- 私聊仅该人员本人可见
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
    done_at TEXT,
    model_provider TEXT,
    model_name TEXT,
    execution_mode TEXT DEFAULT 'template',
    execution_error TEXT,
    execution_ms INTEGER DEFAULT 0
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
    review_comment TEXT,
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

-- 项目流程引擎（V3 泳道 N01-N40 + 阶段门 G1-G4）
CREATE TABLE IF NOT EXISTS project_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id),
    workspace_id INTEGER REFERENCES workspaces(id),
    name TEXT NOT NULL,
    current_stage INTEGER DEFAULT 1,   -- 1-5
    status TEXT DEFAULT '进行中',      -- 进行中/已结项/已暂停
    created_at TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS flow_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id INTEGER NOT NULL REFERENCES project_flows(id),
    code TEXT NOT NULL,                -- N01-N40
    stage INTEGER NOT NULL,            -- 1-5
    role_name TEXT,                    -- 泳道角色（业务部门/项目经理/数字化平台/...）
    title TEXT,
    outputs TEXT,                      -- 产出物（/ 分隔）
    exec_type TEXT,                    -- agent/hybrid/human
    is_critical INTEGER DEFAULT 0,     -- 1=主链路节点
    gate_code TEXT,                    -- 可空：G1-G4（门禁节点）
    status TEXT DEFAULT '未开始',      -- 已锁定/未开始/进行中/待确认/待签核/已完成
    started_at TEXT,
    done_at TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS gate_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id INTEGER NOT NULL REFERENCES project_flows(id),
    gate TEXT NOT NULL,                -- G1-G4
    stage INTEGER NOT NULL,            -- 门禁所在阶段（G1=1 G2=2 G3=4 G4=5）
    status TEXT DEFAULT '未开启',      -- 未开启/待签核/已通过
    signed_by TEXT,
    signed_at TEXT,
    comment TEXT
);

-- R4-1 模型供应商台账（OpenAI 兼容接口）
CREATE TABLE IF NOT EXISTS model_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,          -- glm/kimi/minimax/deepseek/qwen
    name TEXT NOT NULL,
    base_url TEXT,
    default_model TEXT,
    api_key TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    temperature REAL DEFAULT 0.4,
    timeout INTEGER DEFAULT 30,
    last_test_status TEXT DEFAULT '未测试',
    last_test_message TEXT DEFAULT '',
    last_tested_at TEXT
);

-- R4-2 MCP 服务台账（本迭代只做绑定与展示，不做真实调用）
CREATE TABLE IF NOT EXISTS mcp_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    endpoint TEXT,
    description TEXT,
    status TEXT DEFAULT '停用'         -- 启用/停用
);

-- R4-3 文档解析分块
CREATE TABLE IF NOT EXISTS doc_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    seq INTEGER,
    heading TEXT,
    content TEXT
);

-- R4-4 第三方 IM 授权配置与人员绑定
CREATE TABLE IF NOT EXISTS auth_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT UNIQUE NOT NULL,     -- dingtalk/feishu
    app_id TEXT DEFAULT '',
    app_secret TEXT DEFAULT '',
    redirect_uri TEXT DEFAULT '',
    enabled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    provider TEXT NOT NULL,
    external_id TEXT,
    external_name TEXT,
    bound_at TEXT,
    UNIQUE(person_id, provider)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_user_binding_external
ON user_bindings(provider, external_id) WHERE external_id<>'';

CREATE TABLE IF NOT EXISTS oauth_login_codes (
    code TEXT PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id),
    provider TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

-- R5 模型调用留痕：供应商/模型/耗时/成败/回退原因，供审核人追溯交付物来源
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    agent_id INTEGER,
    provider TEXT,                     -- 供应商 key（glm/kimi/...），模板生成时为 NULL
    model TEXT,
    status TEXT NOT NULL,              -- ok / error / template
    latency_ms INTEGER DEFAULT 0,
    error TEXT,                        -- 失败原因（脱敏，不含密钥）
    fallback_reason TEXT,              -- 回落模板原因
    user_id INTEGER REFERENCES people(id),
    workspace_id INTEGER REFERENCES workspaces(id),
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    created_at TEXT
);

-- R7 API 幂等账本：防止弱网/重复点击造成重复消息、任务和模型费用
CREATE TABLE IF NOT EXISTS request_idempotency (
    scope TEXT NOT NULL,
    request_id TEXT NOT NULL,
    person_id INTEGER NOT NULL REFERENCES people(id),
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(scope, request_id, person_id)
);

-- R7 外部运行时事件：事件 ID 必须在任务维度幂等，不能跨任务互相吞事件
CREATE TABLE IF NOT EXISTS runtime_events (
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    source TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(task_id, source, event_id)
);

-- R6 默认制造业务展示数据：每次启动幂等补齐 DEMO-0001..DEMO-1000
CREATE TABLE IF NOT EXISTS business_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_no TEXT UNIQUE NOT NULL,
    business_type TEXT NOT NULL,        -- 销售订单/生产报工/质量检验/库存流水/售后工单
    business_date TEXT NOT NULL,
    department TEXT,
    customer TEXT,
    product_code TEXT,
    product_name TEXT,
    quantity INTEGER DEFAULT 0,
    amount REAL DEFAULT 0,
    status TEXT,
    metric_name TEXT,
    metric_value REAL DEFAULT 0,
    detail TEXT DEFAULT '{}',           -- 各业务类型扩展字段 JSON
    source TEXT DEFAULT '系统演示'
);

CREATE INDEX IF NOT EXISTS ix_business_records_type_date
ON business_records(business_type, business_date);

CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_member
ON workspace_members(workspace_id, member_type, member_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_metrics_daily_agent_date
ON metrics_daily(date, agent_id);
"""

# 老库增量迁移：逐条尝试，已存在则忽略（sqlite 不支持 IF NOT EXISTS 加列）
MIGRATIONS = [
    "ALTER TABLE agents ADD COLUMN model_key TEXT",             # R4-1 空=跟随全局默认
    "ALTER TABLE agents ADD COLUMN mcp_ids TEXT DEFAULT '[]'",  # R4-2 MCP 绑定 JSON 数组
    "ALTER TABLE documents ADD COLUMN file_path TEXT",          # R4-3 转换产物路径
    "ALTER TABLE documents ADD COLUMN converted_format TEXT",   # R4-3 md/html/sqlite
    "ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN summary TEXT",
    "ALTER TABLE model_providers ADD COLUMN temperature REAL DEFAULT 0.4",  # R5 按供应商可调
    "ALTER TABLE model_providers ADD COLUMN timeout INTEGER DEFAULT 30",    # R5 调用超时(秒)
    "ALTER TABLE model_providers ADD COLUMN last_test_status TEXT DEFAULT '未测试'",
    "ALTER TABLE model_providers ADD COLUMN last_test_message TEXT DEFAULT ''",
    "ALTER TABLE model_providers ADD COLUMN last_tested_at TEXT",
    "ALTER TABLE tasks ADD COLUMN model_provider TEXT",
    "ALTER TABLE tasks ADD COLUMN model_name TEXT",
    "ALTER TABLE tasks ADD COLUMN execution_mode TEXT DEFAULT 'template'",
    "ALTER TABLE tasks ADD COLUMN execution_error TEXT",
    "ALTER TABLE tasks ADD COLUMN execution_ms INTEGER DEFAULT 0",
    "ALTER TABLE incentives ADD COLUMN review_comment TEXT",
    "ALTER TABLE messages ADD COLUMN private_owner_id INTEGER REFERENCES people(id)",
    "ALTER TABLE llm_calls ADD COLUMN user_id INTEGER REFERENCES people(id)",
    "ALTER TABLE llm_calls ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id)",
    "ALTER TABLE llm_calls ADD COLUMN prompt_tokens INTEGER DEFAULT 0",
    "ALTER TABLE llm_calls ADD COLUMN completion_tokens INTEGER DEFAULT 0",
    "ALTER TABLE llm_calls ADD COLUMN total_tokens INTEGER DEFAULT 0",
]


def init_db(conn: sqlite3.Connection) -> None:
    """建表 + 老库列迁移（均幂等）"""
    conn.executescript(DDL)
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError as exc:
            # 只忽略 SQLite 明确报告的重复列；磁盘、锁、SQL 拼写等真实迁移错误必须阻断启动。
            if "duplicate column name" not in str(exc).lower():
                raise
    conn.commit()
