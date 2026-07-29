/* 榕器 · Agent 人机协作平台 — 前端 SPA（原生 JS，无构建） */
'use strict';

/* ==================== 常量字典 ==================== */
const TIER_META = {
  boss:      { label: '董事长',   badge: 'badge-gold',                cardRing: 'hover:border-yellow-300' },
  coach:     { label: '教练团',   badge: 'bg-teal',                   cardRing: 'hover:border-teal' },
  backbone:  { label: '业务骨干', badge: 'bg-secondary',              cardRing: 'hover:border-secondary' },
  developer: { label: '开发者',   badge: 'bg-accent',                 cardRing: 'hover:border-accent' },
  staff:     { label: '使用人',   badge: 'bg-gray-400',               cardRing: 'hover:border-gray-300' },
};
const TIER_ORDER = ['boss', 'coach', 'backbone', 'developer', 'staff'];
const AGENT_STATUS_META = {
  '规划中': 'bg-gray-400', '开发中': 'bg-secondary', '试运行': 'bg-accent',
  '试点中': 'bg-teal', '已上线': 'bg-success', '已下线': 'bg-danger',
};
const AGENT_STATUS_LIST = ['规划中', '开发中', '试运行', '试点中', '已上线', '已下线'];
const AGENT_CATEGORY_LIST = ['业务/项目助理', '智造运营/会议纪要', 'BOM/物料', '质量/制程异常分析', '研发测试/售后分析', '综合事务', '通用'];
const PRIORITY_META = { '高': 'bg-danger', '中': 'bg-accent', '低': 'bg-gray-400' };
const LEVEL_META = { L1: 'bg-success', L2: 'bg-secondary', L3: 'bg-accent', L4: 'bg-danger' };
const INCENTIVE_META = { '火花奖': 'bg-accent', '银齿轮奖': 'bg-gray-400', '金扳手奖': 'badge-gold', '种子基金': 'bg-teal' };
/* 激励奖项金额档位（申报表单金额框旁预提示，随奖项类型联动） */
const INCENTIVE_TIER_HINT = {
  '火花奖': '档位参考：500 – 2,000 元（小额即时激励）',
  '银齿轮奖': '档位参考：5,000 – 10,000 元',
  '金扳手奖': '档位参考：30,000 – 50,000 元',
  '种子基金': '档位参考：1 – 100,000 元（年度激励池上限）',
};
const SCENARIO_STATUS_META = { '待立项': 'bg-gray-400', '已立项': 'bg-secondary', '开发中': 'bg-accent', '试点中': 'bg-teal', '已验收': 'bg-success', '已下线': 'bg-danger' };
const ZONE_META = {
  discussion: { name: '讨论区',       desc: '和同事讨论，AI 不打扰', ph: '和同事聊聊想法……（AI 不会在这里插话）' },
  agent:      { name: 'Agent 协作区', desc: '可连续对话深化项目，也可切换为正式派活并进入审核闭环', ph: '直接提问或继续追问，数字员工会结合项目、知识库和业务数据回答' },
  private:    { name: '私聊打磨区',   desc: '先和 AI 助手一对一理清需求（它只回建议不干活），想清楚了再去执行区派活', ph: '把想法说给 AI 助手听，它帮你理成任务草稿（不会派活）' },
};
const TASK_COLUMNS = ['待处理', '进行中', '待审核', '已通过', '已驳回'];
const TASK_STATUS_META = { '待处理': 'bg-gray-400', '进行中': 'bg-secondary', '待审核': 'bg-accent', '已通过': 'bg-success', '已驳回': 'bg-danger' };
const REIMB_STEPS = ['平台长审批', '数字化复核', '财务报销'];
const NODE_TYPE_META = { agent: '智能体主导', hybrid: '人机协同', human: '人类主导' };
/* NAS 设备默认型号（知识库空间未登记设备时展示，可按实际部署修改） */
const NAS_DEFAULT_DEVICE = '群晖DS925+';

/* ==================== 全局状态 ==================== */
const state = {
  token: localStorage.getItem('rq_token') || '',
  person: JSON.parse(localStorage.getItem('rq_person') || 'null'),
};
let charts = [];                    // ECharts 实例注册表，切换视图时统一 dispose
const wsState = { id: null, zone: 'discussion', members: [], interactionMode: 'chat' };  // 协作空间选中态
const govState = { tab: 'incentives' };                            // 治理中心 Tab
const knState = { spaceId: null };                                 // 知识库展开的空间
const cache = { agents: null, agentMap: {}, platforms: null };     // 简单缓存
let taskCache = [];                                                // 任务中心数据（审核弹窗用）

/* ==================== 工具函数 ==================== */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
/* 内联事件（onclick 等）中的字符串参数：JSON.stringify 自带引号与转义，模板里不要再包单引号；
   外面再套 esc() 是为 HTML 属性上下文兜底（属性值中的 " 会被 HTML 解析器截断） */
function jsStr(s) { return JSON.stringify(String(s ?? '')); }
/* 防重复提交：await 期间禁用按钮，finally 恢复（弹窗关闭后节点已移除，恢复无害） */
async function withBusy(btn, fn) {
  if (!btn || btn.disabled) return;
  const oldHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try { await fn(); }
  finally { btn.disabled = false; btn.innerHTML = oldHtml; }
}
function pad2(n) { return String(n).padStart(2, '0'); }
function fmtTime(s) {
  if (!s) return '-';
  const d = new Date(s);
  if (isNaN(d)) return String(s);
  return pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
}
function fmtNum(n) {
  const v = Number(n);
  if (isNaN(v)) return String(n == null ? '-' : n);
  return v.toLocaleString('en-US', { maximumFractionDigits: 1 });
}
function fmtWan(v) {
  const n = Number(v) || 0;
  return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
}
function canReview() {
  return state.person && ['boss', 'coach', 'backbone'].indexOf(state.person.tier) >= 0;
}
/* R4 权限层级：boss/coach = 管理配置（模型/Skill/MCP/IM 凭证）；developer 及以上 = 新建数字员工/上传文档 */
function canAdmin() {
  return state.person && ['boss', 'coach'].indexOf(state.person.tier) >= 0;
}
function canCreateAgent() {
  return state.person && ['boss', 'coach', 'backbone', 'developer'].indexOf(state.person.tier) >= 0;
}
function canUploadDoc() {
  return state.person && ['boss', 'coach', 'backbone', 'developer'].indexOf(state.person.tier) >= 0;
}
/* 是否可修改某个数字员工档案（与后端一致：boss/coach 或其负责人本人） */
function canEditAgent(a) {
  return state.person && (canAdmin() || (a && a.owner_id === state.person.id));
}
function tierBadge(tier) {
  const m = TIER_META[tier] || { label: tier || '未知', badge: 'bg-gray-400' };
  return '<span class="badge ' + m.badge + '">' + esc(m.label) + '</span>';
}
function statusBadge(s, map) {
  const cls = (map && map[s]) || 'bg-gray-400';
  return '<span class="badge ' + cls + '">' + esc(s || '-') + '</span>';
}
function priorityBadge(p) { return statusBadge(p, PRIORITY_META); }

/* Markdown 轻量渲染：转义后处理标题/加粗/列表，容器 pre-wrap 保留换行 */
function mdLite(text) {
  if (!text) return '<div class="md-body text-gray-400">（无内容）</div>';
  let h = esc(text);
  h = h.replace(/^######[ \t]?(.*)\n?/gm, '<div class="md-h3">$1</div>')
       .replace(/^###[ \t]?(.*)\n?/gm, '<div class="md-h3">$1</div>')
       .replace(/^##[ \t]?(.*)\n?/gm, '<div class="md-h2">$1</div>')
       .replace(/^#[ \t]?(.*)\n?/gm, '<div class="md-h1">$1</div>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/^[-*][ \t]+(.*)\n?/gm, '<div class="md-li">· $1</div>');
  return '<div class="md-body">' + h + '</div>';
}

/* ==================== Toast / 弹窗 / 抽屉 ==================== */
function toast(msg, type) {
  const root = document.getElementById('toast-root');
  const t = document.createElement('div');
  t.className = 'toast toast-' + (type || 'success');
  t.textContent = msg;
  root.appendChild(t);
  setTimeout(function () { t.classList.add('show'); }, 10);
  setTimeout(function () { t.classList.remove('show'); setTimeout(function () { t.remove(); }, 300); }, 3800);
}
function openModal(html) {
  document.getElementById('modal-root').innerHTML =
    '<div class="modal-mask" onclick="if(event.target===this)closeModal()"><div class="modal-card">' + html + '</div></div>';
}
function closeModal() {
  document.getElementById('modal-root').innerHTML = '';
  if (typeof oauthPollTimer !== 'undefined' && oauthPollTimer) {
    clearInterval(oauthPollTimer);
    oauthPollTimer = null;
  }
}
function openDrawer(html) {
  document.getElementById('drawer-root').innerHTML =
    '<div class="drawer-mask" onclick="closeDrawer()"></div><div class="drawer-panel">' + html + '</div>';
}
function closeDrawer() {
  document.getElementById('drawer-root').innerHTML = '';
  disposeCharts();
}

/* ==================== 空状态 / 骨架 / 错误 ==================== */
function emptyHtml(text) {
  return '<div class="empty-state">' +
    '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.6a1 1 0 00-.9.55l-.8 1.6a1 1 0 01-.9.55H9.7a1 1 0 01-.9-.55l-.8-1.6a1 1 0 00-.9-.55H4"/></svg>' +
    '<div class="text-sm">' + esc(text || '暂无数据') + '</div></div>';
}
function skeletonHtml(rows) {
  let s = '<div class="space-y-4">';
  for (let i = 0; i < (rows || 4); i++) s += '<div class="skeleton h-24"></div>';
  return s + '</div>';
}
function loadingHtml(text) {
  return '<div class="flex items-center justify-center py-16 text-gray-400"><span class="spinner spinner-dark mr-2"></span>' + esc(text || '加载中…') + '</div>';
}
function errorHtml(msg) {
  return '<div class="data-card text-center py-12"><div class="text-danger font-bold mb-2">加载失败</div><div class="text-gray-500 text-sm">' + esc(msg) + '</div></div>';
}

/* ==================== API 封装 ==================== */
async function api(path, options) {
  const headers = { 'Content-Type': 'application/json; charset=utf-8' };
  const reqToken = state.token;   // 本次请求携带的 token（响应到达时会话可能已变更）
  if (reqToken) headers['Authorization'] = 'Bearer ' + reqToken;
  let res;
  try {
    res = await fetch(path, Object.assign({}, options || {}, { headers: headers }));
  } catch (e) {
    throw new Error('网络异常，请确认后端服务已启动');
  }
  if (res.status === 401) {
    /* 并发请求时第一个 401 已清会话后，后续旧 token 的 401 不得再清掉新会话：
       仅当本次请求所用 token 仍是当前存储的 token 才执行退出 */
    if (reqToken && reqToken === localStorage.getItem('rq_token')) doLogout();
    throw new Error('登录已过期，请重新选择身份登录');
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* 空响应 */ }
  if (!res.ok) throw new Error((data && data.detail) || ('请求失败（HTTP ' + res.status + '）'));
  return data;
}
function postApi(path, body) {
  return api(path, { method: 'POST', body: JSON.stringify(body || {}) });
}
function putApi(path, body) {
  return api(path, { method: 'PUT', body: JSON.stringify(body || {}) });
}
function patchApi(path, body) {
  return api(path, { method: 'PATCH', body: JSON.stringify(body || {}) });
}
function delApi(path) {
  return api(path, { method: 'DELETE' });
}
/* multipart 上传专用：不能带 JSON Content-Type，交给浏览器生成 boundary */
async function uploadApi(path, formData) {
  const headers = {};
  const reqToken = state.token;
  if (reqToken) headers['Authorization'] = 'Bearer ' + reqToken;
  let res;
  try {
    res = await fetch(path, { method: 'POST', headers: headers, body: formData });
  } catch (e) {
    throw new Error('网络异常，请确认后端服务已启动');
  }
  if (res.status === 401) {
    if (reqToken && reqToken === localStorage.getItem('rq_token')) doLogout();
    throw new Error('登录已过期，请重新选择身份登录');
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* 空响应 */ }
  if (!res.ok) throw new Error((data && data.detail) || ('请求失败（HTTP ' + res.status + '）'));
  return data;
}

/* ==================== 导航与路由 ==================== */
const ICON = {
  dashboard: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/>',
  workspaces: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 11.5a8.5 8.5 0 01-8.5 8.5c-1.5 0-2.9-.38-4.1-1.05L3 20l1.05-5.4A8.5 8.5 0 1121 11.5z"/>',
  agents: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2v3M5 8h14a1 1 0 011 1v9a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zM9 13v2M15 13v2M2 12v4M22 12v4"/>',
  scenarios: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 18h6M10 21h4M12 3a6 6 0 00-3.4 10.9c.8.6 1.4 1.5 1.4 2.5v.6h4v-.6c0-1 .6-1.9 1.4-2.5A6 6 0 0012 3z"/>',
  tasks: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 4h4v16H5zM11 4h4v10h-4zM17 4h4v7h-4z" transform="translate(-1 0)"/>',
  flows: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h16v3.5H4zM4 10.25h16v3.5H4zM4 15.5h16V19H4z"/>',
  skills: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 19.5A2.5 2.5 0 016.5 17H20V4H6.5A2.5 2.5 0 004 6.5v13zM4 19.5A2.5 2.5 0 006.5 22H20v-5"/>',
  knowledge: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>',
  org: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 11a3 3 0 100-6 3 3 0 000 6zM3 20v-1a6 6 0 016-6 6 6 0 016 6v1M17 8a3 3 0 110 6M21 20v-1a5 5 0 00-3.5-4.8"/>',
  governance: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6l7-3zM9.5 12l2 2 3.5-3.5"/>',
  roadmap: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 21V4M5 4h12l-2.5 4L17 12H5"/>',
};
const VIEWS = [
  { key: 'dashboard',  name: '驾驶舱',     render: renderDashboard },
  { key: 'workspaces', name: '协作空间',   render: renderWorkspaces },
  { key: 'agents',     name: '数字员工',   render: renderAgents },
  { key: 'scenarios',  name: '场景库',     render: renderScenarios },
  { key: 'tasks',      name: '任务中心',   render: renderTasks },
  { key: 'flows',      name: '项目流程',   render: renderFlows },
  { key: 'skills',     name: 'Skill 库',   render: renderSkills },
  { key: 'knowledge',  name: '知识库',     render: renderKnowledge },
  { key: 'org',        name: '组织通讯录', render: renderOrg },
  { key: 'governance', name: '治理中心',   render: renderGovernance },
  { key: 'roadmap',    name: '路线图',     render: renderRoadmap },
];
const VIEW_TIERS = {
  dashboard: ['boss', 'coach', 'backbone', 'developer'],
  workspaces: ['boss', 'coach', 'backbone', 'developer', 'staff'],
  agents: ['boss', 'coach', 'backbone', 'developer'],
  scenarios: ['boss', 'coach', 'backbone', 'developer'],
  tasks: ['boss', 'coach', 'backbone', 'developer', 'staff'],
  flows: ['boss', 'coach', 'backbone', 'developer'],
  skills: ['boss', 'coach', 'backbone', 'developer'],
  knowledge: ['boss', 'coach', 'backbone', 'developer', 'staff'],
  org: ['boss', 'coach', 'backbone', 'developer'],
  governance: ['boss', 'coach', 'backbone', 'developer'],
  roadmap: ['boss', 'coach', 'backbone', 'developer'],
};
function availableViews() {
  const tier = state.person && state.person.tier;
  return VIEWS.filter(function (v) {
    return (VIEW_TIERS[v.key] || []).indexOf(tier) >= 0;
  });
}
/* 每个视图顶部的一行人话说明（低学习门槛） */
const VIEW_HINTS = {
  dashboard:  '全公司 AI 推进情况一目了然',
  workspaces: '在这里跟数字员工说话、派活、收结果',
  agents:     '你的 AI 同事花名册',
  scenarios:  '想让 AI 干什么活，从这里提',
  tasks:      '数字员工干的活，在这里检查和确认',
  flows:      '每个场景的落地项目按五阶段推进，智能体自动跑 60% 节点，人类只管 4 道阶段门',
  skills:     '好用的 AI 话术和本领，沉淀在这里大家复用',
  knowledge:  '公司的文件资料柜（NAS）',
  org:        '看看同事和数字员工都在哪个部门',
  governance: '奖励申请、AI 费用报销、操作记录',
  roadmap:    '今年的推进计划',
};
function currentViewKey() {
  const h = (location.hash || '').replace(/^#\/?/, '').split('/')[0];
  const visible = availableViews();
  return visible.some(function (v) { return v.key === h; }) ? h :
    ((visible[0] || {}).key || 'workspaces');
}
function buildSidebar() {
  document.getElementById('side-nav').innerHTML = availableViews().map(function (v) {
    return '<a class="nav-item" data-view="' + v.key + '" href="#/' + v.key + '">' +
      '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">' + ICON[v.key] + '</svg><span>' + v.name + '</span></a>';
  }).join('');
}
function renderSidebarUser() {
  const p = state.person;
  document.getElementById('side-user').innerHTML =
    '<div class="flex items-center space-x-3">' +
      '<div class="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center text-white font-bold shrink-0">' + esc((p.name || '?').slice(0, 1)) + '</div>' +
      '<div class="min-w-0 flex-1">' +
        '<div class="text-white text-sm font-bold truncate">' + esc(p.name) + '</div>' +
        '<div class="text-gray-400 text-xs truncate">' + esc(p.role_title || '') + ' · ' + esc(p.dept_name || '') + '</div>' +
      '</div>' +
      '<button onclick="openImBindModal()" title="IM 绑定（钉钉/飞书）" class="text-gray-400 hover:text-white shrink-0">' +
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"/></svg>' +
      '</button>' +
      '<button onclick="doLogout()" title="退出登录" class="text-gray-400 hover:text-white shrink-0">' +
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>' +
      '</button>' +
    '</div>';
}
function renderTopbarUser() {
  const p = state.person;
  document.getElementById('topbar-user').innerHTML =
    '<span class="text-sm text-gray-600">' + esc(p.name) + '</span>' + tierBadge(p.tier);
}
function disposeCharts() {
  charts.forEach(function (c) { try { c.dispose(); } catch (e) {} });
  charts = [];
}
function makeChart(domId) {
  if (!window.echarts) return null;
  const dom = document.getElementById(domId);
  if (!dom) return null;
  const c = echarts.init(dom);
  charts.push(c);
  return c;
}
let routeSeq = 0;                  // 路由序号：防止 hashchange 与直接调用并发导致说明条重复
async function route() {
  if (!state.person) return;
  const seq = ++routeSeq;
  disposeCharts();
  closeDrawer();
  const key = currentViewKey();
  const view = availableViews().find(function (v) { return v.key === key; });
  const requested = (location.hash || '').replace(/^#\/?/, '').split('/')[0];
  if (requested && requested !== key) {
    location.hash = '#/' + key;
    return;
  }
  document.querySelectorAll('#side-nav .nav-item').forEach(function (n) {
    n.classList.toggle('active', n.dataset.view === key);
  });
  document.getElementById('topbar-title').textContent = view.name;
  document.getElementById('app-view').classList.remove('sidebar-open');
  const c = document.getElementById('view-container');
  try {
    await view.render(c);
    if (seq !== routeSeq) return;   // 渲染期间又触发了新路由，放弃本次插入
    if (VIEW_HINTS[key]) {
      c.querySelectorAll('.view-hint').forEach(function (el) { el.remove(); });
      const hint = document.createElement('div');
      hint.className = 'view-hint';
      hint.innerHTML = '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>' + esc(VIEW_HINTS[key]) + '</span>';
      c.insertBefore(hint, c.firstChild);
    }
  } catch (e) {
    c.innerHTML = errorHtml(e.message);
    toast(e.message, 'error');
  }
}

/* ==================== 登录 / 退出 ==================== */
const TIER_LOGIN_HINT = {
  boss:      '进去后看「驾驶舱」，全公司 AI 进展和投入产出都在这里',
  coach:     '进去后到「任务中心」审核交付物，到「治理中心」复核费用报销',
  backbone:  '进去后到「任务中心」勾选"只看待我审核"，给数字员工的活把关',
  developer: '进去后到「数字员工」维护档案，到「协作空间」调试派活',
  staff:     '进去后点「协作空间」，找你的数字员工聊天派活',
};
/* 运行环境信息：登录页模式判断 + 驾驶舱 KPI 目标值；老版本后端无此接口时按演示模式处理 */
let appEnv = null;
async function fetchEnvironment() {
  if (appEnv) return appEnv;
  try {
    const res = await fetch('/api/environment');
    if (res.ok) appEnv = await res.json();
  } catch (e) { /* 接口不存在或网络异常：按演示模式处理 */ }
  return appEnv;
}
async function bootLogin() {
  const box = document.getElementById('login-people');
  box.innerHTML = '<div class="text-gray-300 flex items-center space-x-2"><span class="spinner"></span><span>正在加载…</span></div>';
  const env = await fetchEnvironment();
  try { publicImProviders = await api('/api/auth/providers/public'); }
  catch (e) { publicImProviders = []; }
  /* 生产模式：/api/login/people 返回 403，直接走企业 IM 扫码/授权登录 */
  if (env && env.demo_login_enabled === false) { applyProductionLogin(); return; }
  box.innerHTML = '<div class="text-gray-300 flex items-center space-x-2"><span class="spinner"></span><span>正在加载组织人员…</span></div>';
  try {
    const people = await api('/api/login/people');
    loginPeopleCache = people;
    let html = '';
    TIER_ORDER.forEach(function (tier) {
      const group = people.filter(function (p) { return p.tier === tier; });
      if (!group.length) return;
      const meta = TIER_META[tier];
      html += '<div class="mb-7"><div class="flex items-center space-x-2 mb-1.5">' +
        '<span class="badge ' + meta.badge + '">' + meta.label + '</span>' +
        '<span class="text-gray-400 text-xs">' + group.length + ' 人</span></div>' +
        (TIER_LOGIN_HINT[tier] ? '<div class="text-gray-300 text-xs mb-2.5">▸ ' + esc(TIER_LOGIN_HINT[tier]) + '</div>' : '') +
        '<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">';
      group.forEach(function (p) {
        html += '<div class="person-card border ' + meta.cardRing + '" onclick="doLogin(' + p.id + ')">' +
          '<div class="flex items-center justify-between"><span class="text-white font-bold">' + esc(p.name) + '</span>' + tierBadge(p.tier) + '</div>' +
          '<div class="text-gray-300 text-xs mt-1">' + esc(p.role_title || '') + '</div>' +
          '<div class="text-gray-400 text-xs mt-0.5">' + esc(p.dept_name || '') + '</div></div>';
      });
      html += '</div></div>';
    });
    box.innerHTML = html || '<div class="text-gray-300">暂无人员数据</div>';
  } catch (e) {
    box.innerHTML = '<div class="text-orange-200 text-sm">' + esc(e.message) + '　<a class="underline cursor-pointer" onclick="bootLogin()">点击重试</a></div>';
  }
}
/* 生产模式登录页：收起免密入口与人员选择器，仅保留企业 IM 扫码/授权登录 */
function applyProductionLogin() {
  const copy = document.getElementById('login-demo-copy');
  if (copy) copy.classList.add('hidden');
  document.getElementById('login-people').innerHTML =
    '<div class="border border-white/25 bg-white/10 rounded-lg px-4 py-3 text-sm text-gray-100 leading-relaxed">' +
    '当前为正式环境，免密登录已关闭。请使用下方企业 IM（钉钉 / 飞书）扫码或授权登录；' +
    '尚未绑定 IM 账号的同事，请联系数字化团队完成绑定后再登录。</div>';
  const imCopy = document.getElementById('login-im-copy');
  if (imCopy) imCopy.textContent = '使用已绑定的企业 IM 账号扫码 / 授权登录：';
}
async function doLogin(personId) {
  try {
    const r = await postApi('/api/login', { person_id: personId });
    acceptSession(r);
    toast('欢迎，' + r.person.name + '（' + (TIER_META[r.person.tier] || {}).label + '）');
    enterApp();
  } catch (e) {
    toast(e.message, 'error');
  }
}
function acceptSession(r) {
  state.token = r.token;
  state.person = r.person;
  localStorage.setItem('rq_token', r.token);
  localStorage.setItem('rq_person', JSON.stringify(r.person));
}
function enterApp() {
  document.getElementById('login-view').classList.add('hidden');
  document.getElementById('app-view').classList.remove('hidden');
  buildSidebar();
  document.getElementById('btn-heartbeat').classList.toggle(
    'hidden', !state.person || ['boss', 'coach', 'backbone'].indexOf(state.person.tier) < 0);
  renderSidebarUser();
  renderTopbarUser();
  if (!location.hash) {
    // staff 默认落协作空间；设置 hash 会触发 hashchange → route()，无需重复调用
    location.hash = (state.person && state.person.tier === 'staff') ? '#/workspaces' : '#/dashboard';
    return;
  }
  route();
}
function doLogout() {
  if (state.token) {
    fetch('/api/logout', {
      method: 'POST', headers: { Authorization: 'Bearer ' + state.token }
    }).catch(function () {});
  }
  localStorage.removeItem('rq_token');
  localStorage.removeItem('rq_person');
  state.token = '';
  state.person = null;
  cache.agents = null; cache.agentMap = {}; cache.platforms = null;
  location.hash = '';
  document.getElementById('app-view').classList.add('hidden');
  document.getElementById('login-view').classList.remove('hidden');
  bootLogin();
}

/* ==================== R4-4：IM 绑定登录（钉钉/飞书） ==================== */
const IM_PROVIDER_META = {
  dingtalk: { label: '钉钉', color: '#1e88e5' },
  feishu:   { label: '飞书', color: '#3370ff' },
};
let loginPeopleCache = null;   // 登录页人员（免 token 接口拉到，IM 登录选人用）
let imProvidersCache = null;   // /api/auth/providers 结果（配置弹窗回显用）
let publicImProviders = [];
let oauthPollTimer = null;

/* 登录页入口：未登录拿不到授权 URL（需 token），演示模式下直接选人模拟 IM 身份完成绑定并进入 */
async function imLogin(provider) {
  const meta = IM_PROVIDER_META[provider] || { label: provider };
  const conf = (publicImProviders || []).find(function (x) { return x.provider === provider; });
  if (conf && conf.configured) {
    try {
      const r = await api('/api/auth/oauth/' + provider + '/login-url');
      openQrModal(provider, r.url, r.request_id, true);
      return;
    } catch (e) {
      toast(e.message, 'error');
      return;
    }
  }
  /* 生产模式未配置真实应用凭证时不提供模拟登录 */
  if (appEnv && appEnv.demo_login_enabled === false) {
    toast(meta.label + ' 登录暂未配置，请联系数字化团队完成应用配置后重试', 'error');
    return;
  }
  const people = loginPeopleCache || [];
  openModal('<h3 class="font-bold text-primary text-lg mb-1">使用' + meta.label + '账号进入</h3>' +
    '<p class="text-xs text-gray-500 mb-3">真实环境下这里会弹出' + meta.label + '扫码授权；演示环境请直接选择你的身份，' +
    '系统将模拟' + meta.label + '授权回调并自动绑定。登录后可在侧边栏「IM 绑定」中管理或配置真实应用凭证。</p>' +
    '<label class="form-label">选择你的身份</label>' +
    '<select id="im-person" class="form-select">' +
      people.map(function (p) {
        return '<option value="' + p.id + '">' + esc(p.name) + ' · ' + esc(p.role_title || '') + '（' + esc(p.dept_name || '') + '）</option>';
      }).join('') + '</select>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="im-submit" onclick="submitImLogin(' + esc(jsStr(provider)) + ')">模拟' + meta.label + '授权并进入</button></div>');
}
async function submitImLogin(provider) {
  const personId = Number(document.getElementById('im-person').value);
  if (!personId) { toast('请选择身份', 'error'); return; }
  await withBusy(document.getElementById('im-submit'), async function () {
    try {
      /* demo 回调为免 token 的同源 JSON 接口，直接 fetch 完成模拟绑定 */
      const res = await fetch('/api/auth/oauth/' + provider + '/callback?demo=1&person_id=' + personId);
      const data = await res.json();
      if (!data.ok) throw new Error(data.detail || '授权回调失败');
      closeModal();
      toast(data.msg || '绑定成功', 'info');
      doLogin(data.binding.person_id);
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* 主界面：侧边栏「IM 绑定」弹窗 */
async function openImBindModal() {
  openModal(loadingHtml('加载绑定信息…'));
  try {
    const bindings = await api('/api/auth/bindings');
    let providers = [];
    try { providers = await api('/api/auth/providers'); } catch (e) { /* 无权限/失败时按未配置展示 */ }
    imProvidersCache = providers;
    const boundMap = {};
    bindings.forEach(function (b) { boundMap[b.provider] = b; });
    let html = '<h3 class="font-bold text-primary text-lg mb-1">IM 账号绑定</h3>' +
      '<p class="text-xs text-gray-500 mb-3">绑定后可在登录页用钉钉/飞书一键进入平台。</p><div class="space-y-3">';
    Object.keys(IM_PROVIDER_META).forEach(function (pk) {
      const meta = IM_PROVIDER_META[pk];
      const b = boundMap[pk];
      const conf = providers.find(function (x) { return x.provider === pk; });
      html += '<div class="border border-gray-100 rounded-lg p-3.5">' +
        '<div class="flex items-center justify-between flex-wrap gap-2">' +
          '<div class="flex items-center space-x-2"><span class="font-bold" style="color:' + meta.color + '">' + meta.label + '</span>' +
          (b
            ? '<span class="badge bg-success">已绑定</span><span class="text-sm text-gray-600">' + esc(b.external_name || '') + '</span>' +
              '<span class="text-xs text-gray-400">' + fmtTime(b.bound_at) + '</span>'
            : '<span class="badge bg-gray-400">未绑定</span>') + '</div>' +
          '<div class="flex space-x-2">' +
            (b
              ? '<button class="btn-danger-sm" onclick="unbindIm(' + esc(jsStr(pk)) + ')">解绑</button>'
              : '<button class="btn-success-sm" onclick="startImBind(' + esc(jsStr(pk)) + ')">绑定</button>') +
          '</div></div>' +
        (conf && !conf.configured ? '<div class="text-[11px] text-gray-400 mt-1.5">未配置应用凭证，当前为演示模式（配置后自动切换真实扫码授权）</div>' : '') +
        (conf && conf.configured ? '<div class="text-[11px] text-teal mt-1.5">已配置应用凭证，将跳转真实授权</div>' : '') +
        '</div>';
    });
    html += '</div>';
    if (canAdmin()) {
      html += '<div class="mt-4 pt-3 border-t border-gray-100 flex justify-end">' +
        '<button class="btn-ghost !text-xs" onclick="openProviderConfModal()">配置应用凭证</button></div>';
    }
    html += '<div class="flex justify-end mt-3"><button class="btn-ghost" onclick="closeModal()">关闭</button></div>';
    openModal(html);
  } catch (e) { openModal(errorHtml(e.message)); }
}
/* 绑定：先取授权 URL——demo 直接回调完成；真实模式弹二维码给手机扫 */
async function startImBind(provider) {
  const meta = IM_PROVIDER_META[provider];
  try {
    const r = await api('/api/auth/oauth/' + provider + '/url');
    if (r.demo) {
      const res = await fetch(r.url);
      const data = await res.json();
      if (!data.ok) throw new Error(data.detail || '绑定失败');
      toast(data.msg || (meta.label + '绑定成功'));
      openImBindModal();
    } else {
      openQrModal(provider, r.url);
    }
  } catch (e) { toast(e.message, 'error'); }
}
function openQrModal(provider, url, requestId, isLogin) {
  const meta = IM_PROVIDER_META[provider];
  if (oauthPollTimer) { clearInterval(oauthPollTimer); oauthPollTimer = null; }
  openModal('<h3 class="font-bold text-primary text-lg mb-1">' + meta.label + '扫码授权</h3>' +
    '<p class="text-xs text-gray-500 mb-3">用手机' + meta.label + '扫码并确认授权；二维码组件已随平台本地部署，不依赖公网 CDN。</p>' +
    '<div class="flex flex-col items-center py-2"><canvas id="qr-canvas"></canvas>' +
      '<div id="qr-fallback" class="hidden text-xs text-gray-400 mt-2">二维码组件加载失败，请复制链接到手机打开：</div>' +
      '<a target="_blank" rel="noopener" class="text-xs text-secondary underline mt-2" href="' + esc(url) + '">无法扫码？在当前电脑打开授权页</a>' +
      '<div id="oauth-poll-state" class="text-[11px] text-gray-400 mt-2">' +
        (isLogin ? '等待扫码确认…' : '授权后点击“我已完成授权”刷新状态') + '</div></div>' +
    '<div class="flex justify-end space-x-2 mt-3">' +
      '<button class="btn-ghost" onclick="openImBindModal()">返回</button>' +
      '<button class="btn-primary" onclick="openImBindModal()">我已完成授权</button></div>');
  if (window.QRCode && QRCode.toCanvas) {
    QRCode.toCanvas(document.getElementById('qr-canvas'), url, { width: 220, margin: 1 }, function (err) {
      if (err) document.getElementById('qr-fallback').classList.remove('hidden');
    });
  } else {
    document.getElementById('qr-fallback').classList.remove('hidden');
  }
  if (isLogin && requestId) {
    oauthPollTimer = setInterval(async function () {
      try {
        const r = await api('/api/auth/oauth/poll?request_id=' + encodeURIComponent(requestId));
        if (!r.pending && r.token) {
          clearInterval(oauthPollTimer); oauthPollTimer = null;
          closeModal();
          acceptSession(r);
          toast(meta.label + '身份验证成功，欢迎 ' + r.person.name);
          enterApp();
        }
      } catch (e) {
        clearInterval(oauthPollTimer); oauthPollTimer = null;
        toast(e.message, 'error');
      }
    }, 2000);
  }
}
async function unbindIm(provider) {
  const meta = IM_PROVIDER_META[provider];
  try {
    await delApi('/api/auth/bindings/' + provider);
    toast('已解绑' + meta.label);
    openImBindModal();
  } catch (e) { toast(e.message, 'error'); }
}
/* boss/coach：配置应用凭证（app_id/app_secret/redirect_uri/enabled） */
function openProviderConfModal() {
  const providers = imProvidersCache || [];
  let html = '<h3 class="font-bold text-primary text-lg mb-1">配置 IM 应用凭证</h3>' +
    '<p class="text-xs text-gray-500 mb-3">在钉钉/飞书开放平台创建应用后填入；密钥只存服务端、不回显。填齐并启用后，绑定自动切换为真实扫码授权。</p>' +
    '<div class="space-y-4">';
  providers.forEach(function (p) {
    const meta = IM_PROVIDER_META[p.provider] || { label: p.provider };
    html += '<div class="border border-gray-100 rounded-lg p-3.5" id="conf-' + esc(p.provider) + '">' +
      '<div class="flex items-center justify-between mb-2"><span class="font-bold" style="color:' + (meta.color || '#1a365d') + '">' + meta.label + '</span>' +
      '<label class="inline-flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer"><input type="checkbox" id="cf-' + p.provider + '-enabled" class="accent-secondary"' + (p.enabled ? ' checked' : '') + '>启用</label></div>' +
      '<div class="grid grid-cols-2 gap-2">' +
        '<div><label class="form-label">App ID</label><input id="cf-' + p.provider + '-appid" class="form-input !text-xs" value="' + esc(p.app_id || '') + '"></div>' +
        '<div><label class="form-label">App Secret</label><input id="cf-' + p.provider + '-secret" type="password" class="form-input !text-xs" placeholder="' + (p.app_secret === '已配置' ? '已配置（留空保持不变）' : '填入密钥') + '"></div></div>' +
      '<div class="mt-2"><label class="form-label">回调地址（留空用默认）</label><input id="cf-' + p.provider + '-redirect" class="form-input !text-xs font-mono" value="' + esc(p.redirect_uri || '') + '" placeholder="http://localhost:8000/api/auth/oauth/' + p.provider + '/callback"></div>' +
      '<div class="flex justify-end mt-2"><button class="btn-primary !py-1 !px-3 !text-xs" id="cf-' + esc(p.provider) + '-submit" onclick="submitProviderConf(' + esc(jsStr(p.provider)) + ')">保存' + meta.label + '配置</button></div>' +
      '</div>';
  });
  html += '</div><div class="flex justify-end mt-4"><button class="btn-ghost" onclick="openImBindModal()">返回</button></div>';
  openModal(html);
}
async function submitProviderConf(provider) {
  const body = { enabled: document.getElementById('cf-' + provider + '-enabled').checked };
  const appid = document.getElementById('cf-' + provider + '-appid').value.trim();
  const secret = document.getElementById('cf-' + provider + '-secret').value.trim();
  const redirect = document.getElementById('cf-' + provider + '-redirect').value.trim();
  if (appid) body.app_id = appid;
  if (secret) body.app_secret = secret;
  if (redirect) body.redirect_uri = redirect;
  await withBusy(document.getElementById('cf-' + provider + '-submit'), async function () {
    try {
      await putApi('/api/auth/providers/' + provider, body);
      toast((IM_PROVIDER_META[provider] || {}).label + ' 应用凭证已保存');
      openImBindModal();
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* ==================== 心跳 ==================== */
async function runHeartbeat() {
  const btn = document.getElementById('btn-heartbeat');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span><span>心跳执行中…</span>';
  try {
    const r = await postApi('/api/heartbeat/run');
    toast('心跳完成：昨日交付 ' + r.done_yesterday + ' 项 · 试点场景 ' + r.pilot_scenarios +
      ' 个 · 覆盖率 ' + r.coverage + '% · 催办临期任务 ' + r.reminded_tasks + ' 项', 'info');
    if (currentViewKey() === 'dashboard') route();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg><span>手动触发心跳</span>';
  }
}

/* ==================== 视图 1：驾驶舱 ==================== */
/* KPI 目标值默认值：/api/environment 的 kpi_targets 可覆盖；接口无此字段时行为与硬编码一致 */
const KPI_TARGET_DEFAULTS = {
  coverage: '≥70%', acceptance_rate: '≥85%', active_rate: '≥60%', accuracy: '≥95%', annual_benefit: '¥79万',
};
async function renderDashboard(c) {
  c.innerHTML = skeletonHtml(5);
  await fetchEnvironment();
  const kt = (appEnv && appEnv.kpi_targets) || {};
  const ktarget = function (key) {
    return (kt[key] != null && kt[key] !== '') ? String(kt[key]) : KPI_TARGET_DEFAULTS[key];
  };
  const d = await api('/api/metrics/dashboard');
  const k = d.kpi || {};
  /* kpi 每项为 {value, note} 结构（note 为口径说明） */
  const kval = function (x) { return (x && typeof x === 'object') ? (x.value ?? 0) : (x ?? 0); };
  const knote = function (x) { return (x && typeof x === 'object' && x.note) ? x.note : ''; };
  const kpis = [
    { label: '试点覆盖率',     v: kval(k.trial_coverage) + '%', sub: '试点中+已验收场景占比', color: 'text-secondary', note: knote(k.trial_coverage) },
    { label: '验收覆盖率',     v: kval(k.coverage) + '%',       sub: '方案口径 · 目标 ' + ktarget('coverage'),  color: 'text-gray-500',  note: knote(k.coverage) },
    { label: '验收通过率',     v: kval(k.acceptance_rate) + '%', sub: '目标 ' + ktarget('acceptance_rate'),    color: 'text-success',   note: knote(k.acceptance_rate) },
    { label: '活跃使用率(7日)', v: kval(k.active_rate) + '%',    sub: '目标 ' + ktarget('active_rate'),        color: 'text-teal',      note: knote(k.active_rate) },
    { label: '累计节省工时',   v: fmtNum(kval(k.hours_saved)) + ' h',   sub: '数字员工产出',   color: 'text-accent',    note: knote(k.hours_saved) },
    { label: '交付准确率',     v: kval(k.accuracy) + '%',       sub: '目标 ' + ktarget('accuracy'),            color: 'text-secondary', note: knote(k.accuracy) },
    { label: '年化综合收益',   v: '¥' + fmtWan(kval(k.annual_benefit)), sub: '目标 ' + ktarget('annual_benefit'), color: 'text-success', note: knote(k.annual_benefit) },
    { label: 'Skill 复用数',   v: fmtNum(kval(k.reuse_count)),  sub: '被引用去重',            color: 'text-primary',   note: knote(k.reuse_count) },
  ];
  const inv = d.investment || { year1: 0, breakdown: {}, breakdown_detail: {} };
  const ben = d.benefit || { direct: 0, total: 0 };
  const maxMoney = Math.max(ben.total || 1, 1);

  let html = '<div class="space-y-5">';
  /* ① 八维 KPI（覆盖率双口径） */
  html += '<div class="grid grid-cols-2 md:grid-cols-4 gap-3">' + kpis.map(function (x) {
    return '<div class="data-card !p-4 card-hover"><div class="text-xs text-gray-500">' + x.label + '</div>' +
      '<div class="text-2xl font-black mt-1 ' + x.color + '">' + x.v + '</div>' +
      '<div class="text-xs text-gray-400 mt-1">' + x.sub + '</div>' +
      (x.note ? '<div class="text-[11px] text-gray-400 mt-1 pt-1 border-t border-gray-50">口径：' + esc(x.note) + '</div>' : '') +
      '</div>';
  }).join('') + '</div>';

  html += '<div class="grid grid-cols-1 xl:grid-cols-3 gap-5">';
  /* ② 投入产出卡 */
  html += '<div class="data-card"><div class="flex items-center justify-between mb-3">' +
    '<h3 class="font-bold text-primary">首年投入 vs 收益</h3>' +
    '<span class="badge bg-success">综合 ROI ' + (inv.year1 ? (ben.total / inv.year1).toFixed(1) : '-') + 'x</span></div>' +
    '<div class="space-y-3 text-sm">' +
      moneyBar('首年投入', inv.year1, maxMoney, '#1a365d') +
      moneyBar('直接收益', ben.direct, maxMoney, '#319795') +
      moneyBar('综合收益', ben.total, maxMoney, '#ed8936') +
    '</div>' +
    ((ben.roi_year1_pct != null || ben.roi_year2_pct != null)
      ? '<div class="mt-3 flex flex-wrap gap-1.5">' +
        (ben.roi_year1_pct != null ? '<span class="badge badge-outline !text-secondary !border-secondary/40">首年净 ROI ' + ben.roi_year1_pct + '%</span>' : '') +
        (ben.roi_year2_pct != null ? '<span class="badge badge-outline !text-teal !border-teal/40">次年净 ROI ' + ben.roi_year2_pct + '%</span>' : '') +
        '</div>' : '') +
    '<div class="mt-4 pt-3 border-t border-gray-100"><div class="text-xs text-gray-500 mb-2">投入构成</div>' +
    Object.keys(inv.breakdown || {}).map(function (name) {
      const detail = (inv.breakdown_detail || {})[name] || {};
      const detailKeys = Object.keys(detail);
      return '<div class="flex justify-between text-xs text-gray-600 py-0.5"><span>' + esc(name) + '</span><span class="font-medium">¥' + fmtWan(inv.breakdown[name]) + '</span></div>' +
        (detailKeys.length
          ? '<div class="pl-3 pb-1">' + detailKeys.map(function (dk) {
              return '<div class="flex justify-between text-[11px] text-gray-400 py-px"><span>· ' + esc(dk) + '</span><span>¥' + fmtWan(detail[dk]) + '</span></div>';
            }).join('') + '</div>'
          : '');
    }).join('') + '</div></div>';
  /* ③ 近 14 天趋势 */
  html += '<div class="data-card xl:col-span-2"><h3 class="font-bold text-primary mb-2">近 14 天任务完成与节省工时</h3><div id="chart-trend" class="chart-box"></div></div>';
  html += '</div>';

  html += '<div class="grid grid-cols-1 xl:grid-cols-2 gap-5">';
  /* ④ 四波次推进 */
  html += '<div class="data-card"><h3 class="font-bold text-primary mb-2">四波次数字员工推进</h3><div id="chart-waves" class="chart-box"></div></div>';
  /* ⑤ 产出榜 TOP8 */
  html += '<div class="data-card"><h3 class="font-bold text-primary mb-2">数字员工产出榜 TOP8</h3><div id="chart-leader" class="chart-box"></div></div>';
  html += '</div>';

  /* ⑥ 心跳动态流 */
  html += '<div class="data-card"><h3 class="font-bold text-primary mb-3">心跳动态流</h3>';
  /* 后端新增 latest_report 时置顶"最新日报"卡（防御性：字段缺失或结构异常时保持现状） */
  const lr = d.latest_report;
  if (lr && typeof lr === 'object' && lr.content) {
    html += '<div class="feed-report p-3 mb-3">' +
      '<div class="flex items-center flex-wrap gap-x-2 text-xs text-gray-500 mb-1.5">' +
        '<span class="badge bg-accent">最新日报</span>' +
        '<span class="font-bold text-gray-700">' + esc(lr.workspace_name || '') + '</span>' +
        '<span>' + fmtTime(lr.created_at) + '</span>' +
        (lr.workspace_id ? '<span class="ml-auto text-xs text-accent font-bold cursor-pointer hover:underline" onclick="gotoWorkspaceZone(' + lr.workspace_id + ',\'agent\')">查看日报 →</span>' : '') +
      '</div>' +
      '<div class="max-h-40 overflow-y-auto">' + mdLite(String(lr.content).slice(0, 600)) + '</div>' +
    '</div>';
  }
  const feed = d.feed || [];
  if (!feed.length) html += emptyHtml('暂无心跳动态');
  else {
    html += '<div class="timeline space-y-3">' + feed.map(function (m) {
      const isReport = m.msg_type === 'report';
      return '<div class="relative pl-2">' +
        '<div class="timeline-dot ' + (m.sender_type === 'agent' ? 'bg-teal' : 'bg-gray-400') + '"></div>' +
        '<div class="p-3 ' + (isReport ? 'feed-report' : 'bg-gray-50 rounded-lg') + '">' +
          '<div class="flex items-center flex-wrap gap-x-2 text-xs text-gray-500 mb-1">' +
            '<span class="font-bold text-gray-700">' + esc(m.sender_name) + '</span>' +
            '<span class="badge badge-outline">' + esc(m.workspace_name || '') + '</span>' +
            (isReport ? '<span class="badge bg-accent">日报</span>' : '') +
            (isReport && m.workspace_id ? '<span class="text-xs text-accent font-bold cursor-pointer hover:underline" onclick="gotoWorkspaceZone(' + m.workspace_id + ',\'agent\')">查看日报 →</span>' : '') +
            '<span>' + fmtTime(m.created_at) + '</span></div>' +
          '<div class="' + (isReport ? 'max-h-48 overflow-y-auto' : '') + '">' + mdLite(m.content) + '</div>' +
        '</div></div>';
    }).join('') + '</div>';
  }
  html += '</div></div>';
  c.innerHTML = html;

  /* 趋势双折线 */
  const trend = d.trend || [];
  const ct = makeChart('chart-trend');
  if (ct) ct.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['任务完成数', '节省工时(h)'], top: 0 },
    grid: { left: 45, right: 45, top: 35, bottom: 25 },
    xAxis: { type: 'category', data: trend.map(function (x) { return (x.date || '').slice(5); }), axisLabel: { fontSize: 10 } },
    yAxis: [{ type: 'value', name: '任务数' }, { type: 'value', name: '工时', splitLine: { show: false } }],
    series: [
      { name: '任务完成数', type: 'line', smooth: true, data: trend.map(function (x) { return x.tasks_done; }), itemStyle: { color: '#2c5282' }, areaStyle: { opacity: 0.08 } },
      { name: '节省工时(h)', type: 'line', smooth: true, yAxisIndex: 1, data: trend.map(function (x) { return x.hours_saved; }), itemStyle: { color: '#ed8936' }, areaStyle: { opacity: 0.08 } },
    ],
  });

  /* 波次堆叠条形图 */
  const waves = d.waves || [];
  const statusKeys = [];
  waves.forEach(function (w) { Object.keys(w.by_status || {}).forEach(function (s) { if (statusKeys.indexOf(s) < 0) statusKeys.push(s); }); });
  const statusColor = { '规划中': '#94a3b8', '开发中': '#2c5282', '试运行': '#ed8936', '试点中': '#319795', '已上线': '#38a169', '已下线': '#e53e3e' };
  const cw = makeChart('chart-waves');
  if (cw) cw.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 45, right: 20, top: 35, bottom: 25 },
    xAxis: { type: 'category', data: waves.map(function (w) { return '第' + w.wave + '波'; }) },
    yAxis: { type: 'value', name: '数量' },
    series: statusKeys.map(function (s) {
      return { name: s, type: 'bar', stack: 'w', barWidth: 38, itemStyle: { color: statusColor[s] || '#64748b' },
        data: waves.map(function (w) { return (w.by_status || {})[s] || 0; }) };
    }),
  });

  /* 产出榜横向条 */
  const lb = (d.leaderboard || []).slice(0, 8);
  const cl = makeChart('chart-leader');
  if (cl) cl.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: function (ps) { const p = ps[0]; const it = lb[p.dataIndex]; return it.name + '<br/>完成任务：' + it.tasks_done + ' 项<br/>节省工时：' + it.hours_saved + ' h'; } },
    grid: { left: 8, right: 40, top: 10, bottom: 25, containLabel: true },
    xAxis: { type: 'value', name: '任务数' },
    yAxis: { type: 'category', inverse: true, data: lb.map(function (x) { return x.name; }), axisLabel: { fontSize: 11, width: 110, overflow: 'truncate' } },
    series: [{ type: 'bar', barWidth: 16, data: lb.map(function (x) { return x.tasks_done; }),
      itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: '#1a365d' }, { offset: 1, color: '#319795' }] }, borderRadius: [0, 8, 8, 0] },
      label: { show: true, position: 'right', fontSize: 11 } }],
  });
}
function moneyBar(label, v, max, color) {
  const pct = Math.min(100, Math.round((Number(v) || 0) / max * 100));
  return '<div><div class="flex justify-between mb-1"><span class="text-gray-600">' + label + '</span>' +
    '<span class="font-bold" style="color:' + color + '">¥' + fmtWan(v) + '</span></div>' +
    '<div class="h-2.5 bg-gray-100 rounded-full"><div class="h-2.5 rounded-full" style="width:' + pct + '%;background:' + color + '"></div></div></div>';
}

/* ==================== 视图 2：协作空间 ==================== */
async function ensureAgentsCache() {
  if (cache.agents) return;
  cache.agents = await api('/api/agents');
  cache.agentMap = {};
  cache.agents.forEach(function (a) { cache.agentMap[a.id] = a; });
}
async function renderWorkspaces(c) {
  c.innerHTML = loadingHtml('加载工作区…');
  const list = await api('/api/workspaces');
  await ensureAgentsCache();
  /* 支持深链 #/workspaces/<id>/<zone>（如驾驶舱"查看日报"跳转） */
  const parts = (location.hash || '').replace(/^#\/?/, '').split('/');
  if (parts[0] === 'workspaces') {
    const wid = Number(parts[1]);
    if (wid && list.some(function (w) { return w.id === wid; })) wsState.id = wid;
    if (parts[2] && ZONE_META[parts[2]]) wsState.zone = parts[2];
  }
  if (!wsState.id || !list.some(function (w) { return w.id === wsState.id; })) {
    wsState.id = list.length ? list[0].id : null;
  }
  let html = '<div class="workspace-layout flex gap-5" style="height:calc(100vh - 7.5rem)">';
  /* 左栏：工作区列表 */
  html += '<div class="workspace-list w-72 shrink-0 data-card !p-3 flex flex-col"><div class="text-sm font-bold text-primary px-2 py-1">工作区列表（' + list.length + '）</div>' +
    '<div class="flex-1 overflow-y-auto space-y-1.5 mt-1">';
  if (!list.length) html += emptyHtml('暂无工作区，可先到场景库发起敏捷立项');
  list.forEach(function (w) {
    const active = w.id === wsState.id;
    html += '<div class="p-2.5 rounded-lg cursor-pointer border transition-all ' + (active ? 'bg-primary/5 border-secondary' : 'border-transparent hover:bg-gray-50') + '" onclick="selectWorkspace(' + w.id + ')">' +
      '<div class="flex items-center justify-between"><span class="font-bold text-sm ' + (active ? 'text-primary' : 'text-gray-700') + ' truncate">' + esc(w.name) + '</span>' +
      '<span class="badge badge-outline shrink-0 ml-1">' + esc(w.type) + '</span></div>' +
      '<div class="text-xs text-gray-400 mt-1">成员 ' + (w.member_count ?? '-') + ' · ' + fmtTime(w.created_at) + '</div></div>';
  });
  html += '</div></div>';
  /* 右侧聊天区 */
  html += '<div class="flex-1 data-card !p-0 flex flex-col min-w-0" id="ws-panel">' + loadingHtml() + '</div>';
  html += '</div>';
  c.innerHTML = html;
  const panel = document.getElementById('ws-panel');
  if (wsState.id) await loadWorkspacePanel();
  else panel.innerHTML = emptyHtml('暂无工作区：可先在「场景库」对待立项场景点击敏捷立项，系统将自动创建项目工作区');
}
async function selectWorkspace(id) {
  wsState.id = id;
  await renderWorkspaces(document.getElementById('view-container'));
}
/* 从驾驶舱动态流等入口跳转到指定工作区的指定分区（深链，hashchange 触发渲染） */
function gotoWorkspaceZone(wsId, zone) {
  wsState.id = wsId;
  wsState.zone = zone || 'discussion';
  const target = '#/workspaces/' + wsId + '/' + wsState.zone;
  if (location.hash === target) route();
  else location.hash = target;
}
async function loadWorkspacePanel() {
  const panel = document.getElementById('ws-panel');
  if (!panel) return;
  const detail = await api('/api/workspaces/' + wsState.id);
  wsState.members = detail.members || [];
  const availableAgents = wsState.members.filter(function (m) {
    return m.member_type === 'agent' && m.status !== '已下线';
  });
  const z = ZONE_META[wsState.zone];
  let html = '<div class="px-4 pt-3 border-b border-gray-100 shrink-0">' +
    '<div class="flex items-center justify-between mb-2">' +
      '<div class="flex items-center space-x-2 min-w-0"><span class="font-bold text-primary truncate">' + esc(detail.name) + '</span>' +
      '<span class="badge badge-outline">' + esc(detail.type) + '</span></div>' +
      '<button class="btn-ghost !py-1 !px-2 text-xs" onclick="loadMessages(false)" title="刷新消息">' +
        '<span class="inline-flex items-center gap-1"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M5 9a8 8 0 0114-3M19 15a8 8 0 01-14 3"/></svg>刷新</span></button>' +
    '</div>' +
    '<div class="flex space-x-1">' +
    Object.keys(ZONE_META).map(function (key) {
      return '<div class="zone-tab ' + (key === wsState.zone ? 'active' : '') + '" onclick="switchZone(' + esc(jsStr(key)) + ')">' + ZONE_META[key].name + '</div>';
    }).join('') +
    '</div></div>' +
    '<div class="px-4 py-1.5 bg-teal/5 text-xs text-teal border-b border-gray-100 shrink-0">💡 ' + esc(z.name) + '：' + esc(z.desc) + '</div>' +
    '<div id="chain-bar" class="shrink-0"></div>' +
    '<div id="msg-list" class="flex-1 overflow-y-auto chat-scroll px-4 py-3 bg-gray-50/50"></div>' +
    /* 输入区 */
    '<div class="p-3 border-t border-gray-100 shrink-0 relative">' +
      '<div id="at-popup" class="at-popup hidden"></div>' +
      (wsState.zone === 'agent'
        ? '<div class="flex flex-wrap items-center gap-2 mb-2">' +
          '<select id="ws-interaction-mode" class="form-select !w-44 !py-1.5 text-xs" onchange="switchAgentInteractionMode(this.value)">' +
            '<option value="chat"' + (wsState.interactionMode === 'chat' ? ' selected' : '') + '>💬 连续对话深化</option>' +
            '<option value="task"' + (wsState.interactionMode === 'task' ? ' selected' : '') + '>⚡ 正式派活交付</option></select>' +
          '<select id="ws-target-agent" class="form-select !w-56 !py-1.5 text-xs">' +
            availableAgents.map(function (m) {
              return '<option value="' + m.member_id + '">' + esc(m.name) + ' · ' + esc(m.status || '可用') + '</option>';
            }).join('') + '</select>' +
          '<span id="interaction-help" class="text-[11px] text-gray-400">' +
            (wsState.interactionMode === 'chat' ? '调用真实模型，自动携带历史与业务上下文' : '生成交付物并进入人工审核') +
          '</span></div>'
        : '') +
      '<div id="dispatch-hint" class="hidden text-xs text-accent font-medium mb-1.5"></div>' +
      '<div class="flex items-end space-x-2">' +
        '<textarea id="ws-input" class="form-textarea flex-1" rows="2" placeholder="' + esc(z.ph || '输入消息，Enter 发送') + '"></textarea>' +
        '<button class="btn-primary shrink-0" id="ws-send" onclick="sendWsMessage()">发送</button>' +
      '</div></div>';
  panel.innerHTML = html;
  const ta = document.getElementById('ws-input');
  ta.addEventListener('input', onWsInput);
  ta.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendWsMessage(); }
  });
  await loadMessages(false);
}
async function switchZone(zone) {
  wsState.zone = zone;
  await loadWorkspacePanel();
}
/* 交付卡片实时上下文：task_id→task 映射 + 每个 task 的最高交付版本（消息 payload 里的状态只是发出时的快照） */
const wsTaskCtx = { map: {}, maxVer: {} };
async function loadMessages(scrollToDeliverable) {
  const box = document.getElementById('msg-list');
  if (!box) return;
  /* 消息与该工作区任务并行拉取；tasks 接口异常时降级为按 payload 快照渲染 */
  const tasksReq = api('/api/tasks?workspace_id=' + wsState.id).catch(function () { return null; });
  const msgs = await api('/api/workspaces/' + wsState.id + '/messages?zone=' + wsState.zone + '&limit=200');
  const tasks = await tasksReq;
  wsTaskCtx.map = {};
  wsTaskCtx.maxVer = {};
  (tasks || []).forEach(function (t) { wsTaskCtx.map[t.id] = t; });
  msgs.forEach(function (m) {
    const p = m.payload || {};
    if (m.msg_type === 'deliverable' && p.task_id && p.version) {
      wsTaskCtx.maxVer[p.task_id] = Math.max(wsTaskCtx.maxVer[p.task_id] || 0, p.version);
    }
  });
  if (!msgs.length) box.innerHTML = emptyHtml('本区暂无消息，来发第一条吧');
  else box.innerHTML = msgs.map(messageHtml).join('');
  if (scrollToDeliverable) {
    const cards = box.querySelectorAll('.deliverable-card');
    if (cards.length) cards[cards.length - 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
    else box.scrollTop = box.scrollHeight;
  } else {
    box.scrollTop = box.scrollHeight;
  }
  refreshChainBar();   // R4-6：链路条随消息列表一起刷新（发消息/审核后同此入口）
}
/* ---------- R4-6：Agent 执行链路横条（过去→现在→未来） ---------- */
async function refreshChainBar() {
  const bar = document.getElementById('chain-bar');
  if (!bar) return;
  if (wsState.zone !== 'agent') { bar.innerHTML = ''; return; }
  try {
    const ch = await api('/api/workspaces/' + wsState.id + '/chain');
    /* 无链路数据（无过去且无未来）时隐藏横条 */
    if (!(ch.past || []).length && !(ch.future || []).length) { bar.innerHTML = ''; return; }
    bar.innerHTML = chainBarHtml(ch);
  } catch (e) { bar.innerHTML = ''; /* 链路拉取失败不阻塞聊天 */ }
}
function chainBarHtml(ch) {
  const nodes = [];
  (ch.past || []).forEach(function (p) {
    const rejected = p.status === '已驳回';
    nodes.push({
      cls: 'cn-past' + (rejected ? ' rejected' : ''),
      icon: rejected ? '❌' : '✅',
      title: p.title || '',
      sub: (p.agent_name || '') + ' · ' + fmtTime(p.time),
      tip: '【过去】' + (p.title || '') + '\n状态：' + (p.status || '-') + ' · 数字员工：' + (p.agent_name || '-') +
        '\n时间：' + fmtTime(p.time) + (p.version ? ' · 交付版本 v' + p.version : ''),
    });
  });
  (ch.present || []).forEach(function (p) {
    nodes.push({
      cls: 'cn-present',
      icon: '🔵',
      title: p.title || '',
      sub: (p.agent_name || '') + ' · ' + (p.status || ''),
      tip: '【当前】' + (p.title || '') + '\n状态：' + (p.status || '-') + ' · 数字员工：' + (p.agent_name || '-') +
        '\n优先级：' + (p.priority || '-') + (p.deadline ? ' · 截止：' + fmtTime(p.deadline) : '') + (p.version ? ' · 交付版本 v' + p.version : ''),
    });
  });
  (ch.future || []).forEach(function (f) {
    nodes.push({
      cls: 'cn-future',
      icon: '⚪',
      title: (f.code ? f.code + ' ' : '') + (f.title || ''),
      sub: (f.role_name || '') + ' · ' + (f.status || ''),
      tip: '【未来】流程节点 ' + (f.code || '') + '：' + (f.title || '') + '\n负责角色：' + (f.role_name || '-') +
        ' · 阶段' + (f.stage || '-') + ' · 状态：' + (f.status || '-'),
    });
  });
  let strip = '';
  nodes.forEach(function (n, i) {
    if (i) strip += '<div class="chain-link"></div>';
    strip += '<div class="chain-node ' + n.cls + '" title="' + esc(n.tip) + '">' +
      '<div class="flex items-center gap-1"><span>' + n.icon + '</span>' +
      '<span class="font-bold text-[11px] truncate">' + esc(n.title) + '</span></div>' +
      '<div class="text-[10px] text-gray-400 truncate mt-0.5">' + esc(n.sub) + '</div></div>';
  });
  return '<div class="px-4 py-2 border-b border-gray-100 bg-white">' +
    '<div class="flex items-center gap-2 mb-1"><span class="text-[11px] font-bold text-gray-500">执行链路</span>' +
    '<span class="text-[10px] text-gray-300">过去 ✅ → 现在 🔵 → 未来 ⚪</span></div>' +
    '<div class="chain-strip">' + strip +
    (ch.flow_id ? '<div class="chain-link"></div><div class="chain-flow" onclick="gotoFlow(' + ch.flow_id + ')" title="打开项目流程泳道">查看完整流程 →</div>' : '') +
    '</div></div>';
}
const ROBOT_SVG = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2v3M5 8h14a1 1 0 011 1v9a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zM9 13v2M15 13v2"/></svg>';
function messageHtml(m) {
  const t = fmtTime(m.created_at);
  if (m.sender_type === 'system') {
    return '<div class="flex justify-center my-2"><div class="md-sys text-xs text-gray-500 bg-gray-200/70 rounded-full px-4 py-1 max-w-[85%] text-center">' + mdLite(m.content) + '</div></div>';
  }
  if (m.msg_type === 'deliverable') return deliverableHtml(m, t);
  if (m.sender_type === 'human') {
    return '<div class="flex justify-end my-2.5"><div class="flex flex-col items-end max-w-full">' +
      '<div class="text-xs text-gray-400 mb-1">' + esc(m.sender_name) + ' · ' + t + '</div>' +
      '<div class="msg-bubble msg-bubble-human">' + esc(m.content) + '</div></div></div>';
  }
  /* agent 消息（含私聊打磨稿、日报 report）：走 mdLite 渲染 markdown */
  const ag = cache.agentMap[m.sender_id] || {};
  const isReport = m.msg_type === 'report';
  const modelInfo = (m.payload || {}).model_info;
  let modelTrace = '';
  if (modelInfo) {
    modelTrace = modelInfo.ok
      ? '<div class="text-[11px] text-teal mt-1">真实模型回复：' + esc(modelInfo.provider || '-') +
        ' / ' + esc(modelInfo.model || '-') + ' · ' + (modelInfo.latency_ms || 0) + 'ms</div>'
      : '<div class="text-[11px] text-danger mt-1">模型未完成：' + esc(modelInfo.reason || '未配置可用模型') + '</div>';
  }
  return '<div class="flex my-2.5"><div class="msg-avatar bg-teal mr-2">' + ROBOT_SVG + '</div>' +
    '<div class="flex flex-col max-w-full"><div class="text-xs text-gray-400 mb-1">' + esc(m.sender_name) +
    (ag.dept_name ? ' · ' + esc(ag.dept_name) : '') + (isReport ? ' · 日报' : '') + ' · ' + t + '</div>' +
    '<div class="msg-bubble msg-bubble-agent' + (isReport ? ' max-h-72 overflow-y-auto' : '') + '">' + mdLite(m.content) + '</div>' +
    modelTrace + '</div></div>';
}
function deliverableHtml(m, t) {
  const p = m.payload || {};
  /* 以任务实时状态为准（tasks 拉取失败时退回 payload 快照）；旧版本卡片显示"已被取代"灰条 */
  const task = p.task_id ? wsTaskCtx.map[p.task_id] : null;
  const effStatus = task ? task.status : (p.status || '');
  const maxV = wsTaskCtx.maxVer[p.task_id] || 0;
  const superseded = !!(p.task_id && p.version && maxV > p.version);
  let actionBar = '';
  if (p.task_id) {
    if (superseded) {
      actionBar = '<div class="mt-3 pt-2 border-t border-gray-100">' +
        '<div class="bg-gray-100 text-gray-400 text-xs rounded px-3 py-1.5 text-center">已被 v' + maxV + ' 取代，请以最新版本为准</div></div>';
    } else if (effStatus === '待审核') {
      if (canReview()) {
        actionBar = '<div class="mt-3 pt-2 border-t border-gray-100 flex items-center justify-end space-x-2">' +
          '<button class="btn-success-sm" onclick="reviewTaskAction(' + p.task_id + ',\'approve\')">通过</button>' +
          '<button class="btn-danger-sm" onclick="openRejectModal(' + p.task_id + ')">驳回</button></div>';
      } else {
        actionBar = '<div class="mt-3 pt-2 border-t border-gray-100 text-right text-xs text-gray-400">需业务骨干/教练团审核</div>';
      }
    }
  }
  /* R5 模型溯源：交付物来自真实模型还是模板，审核人可追溯 */
  const mi = p.model_info;
  let modelLine = '';
  if (mi) {
    modelLine = mi.fallback
      ? '<div class="text-[11px] text-amber-600 mt-1">模板模拟生成' +
        (mi.provider ? '（' + esc(mi.provider) + ' 调用失败已回落' +
          (mi.reason ? '：' + esc(String(mi.reason).slice(0, 60)) : '') + '）' : '（未配置可用模型）') + '</div>'
      : '<div class="text-[11px] text-teal mt-1">真实模型生成：' + esc(mi.provider || '-') +
        ' / ' + esc(mi.model || '-') + ' · ' + (mi.latency_ms || 0) + 'ms</div>';
  }
  return '<div class="flex my-3"><div class="msg-avatar bg-accent mr-2">' + ROBOT_SVG + '</div>' +
    '<div class="deliverable-card">' +
      '<div class="flex items-center justify-between flex-wrap gap-1">' +
        '<div class="flex items-center space-x-2"><span class="font-bold text-primary text-sm">交付卡片</span>' +
        '<span class="text-xs text-gray-500">' + esc(m.sender_name) + '</span>' +
        (p.version ? '<span class="badge bg-secondary">v' + p.version + '</span>' : '') +
        (p.rework ? '<span class="badge bg-accent">按驳回意见修订</span>' : '') +
        (effStatus ? statusBadge(effStatus, TASK_STATUS_META) : '') + '</div>' +
        '<span class="text-xs text-gray-400">任务 #' + (p.task_id ?? '-') + ' · ' + t + '</span></div>' +
      '<div class="deliverable-body mt-2">' + mdLite(m.content) + '</div>' +
      modelLine +
      actionBar +
    '</div></div>';
}
/* @ 候选 */
function onWsInput(e) {
  const ta = e.target;
  const before = ta.value.slice(0, ta.selectionStart);
  const m = before.match(/@([^\s@]{0,12})$/);
  const pop = document.getElementById('at-popup');
  if (m) {
    const q = m[1];
    const cands = wsState.members.filter(function (x) { return x.member_type === 'agent' && x.name.indexOf(q) >= 0; });
    if (cands.length) {
      pop.innerHTML = cands.map(function (a) {
        return '<div class="at-item" onclick="insertAt(' + esc(jsStr(a.name)) + ')">' +
          '<span class="w-6 h-6 rounded bg-teal text-white flex items-center justify-center shrink-0"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2v3M5 8h14a1 1 0 011 1v9a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zM9 13v2M15 13v2"/></svg></span>' +
          '<span>' + esc(a.name) + '</span><span class="text-xs text-gray-400">数字员工</span></div>';
      }).join('');
      pop.classList.remove('hidden');
    } else pop.classList.add('hidden');
  } else pop.classList.add('hidden');
  updateDispatchHint();
}
function insertAt(name) {
  const ta = document.getElementById('ws-input');
  const pos = ta.selectionStart;
  const before = ta.value.slice(0, pos).replace(/@[^\s@]{0,12}$/, '@' + name + ' ');
  ta.value = before + ta.value.slice(pos);
  document.getElementById('at-popup').classList.add('hidden');
  ta.focus();
  ta.selectionStart = ta.selectionEnd = before.length;
  updateDispatchHint();
}
function updateDispatchHint() {
  const ta = document.getElementById('ws-input');
  const hint = document.getElementById('dispatch-hint');
  if (!ta || !hint) return;
  const content = ta.value;
  const mention = wsState.members.some(function (x) { return x.member_type === 'agent' && content.indexOf('@' + x.name) >= 0; });
  const active = wsState.zone === 'agent' || mention;
  const mode = (document.getElementById('ws-interaction-mode') || {}).value || 'task';
  hint.textContent = mode === 'chat'
    ? '💬 将调用所选数字员工的真实模型，结合本项目上下文连续回答'
    : '⚡ 将派发正式任务，生成交付物并进入人工审核';
  hint.classList.toggle('hidden', !active);
}
function switchAgentInteractionMode(mode) {
  wsState.interactionMode = mode === 'task' ? 'task' : 'chat';
  const help = document.getElementById('interaction-help');
  if (help) help.textContent = wsState.interactionMode === 'chat'
    ? '调用真实模型，自动携带历史与业务上下文'
    : '生成交付物并进入人工审核';
  const ta = document.getElementById('ws-input');
  if (ta) ta.placeholder = wsState.interactionMode === 'chat'
    ? '直接提问或继续追问，数字员工会结合项目、知识库和业务数据回答'
    : '@数字员工 + 描述交付要求，如：整理本周订单并给出风险清单';
  updateDispatchHint();
}
async function sendWsMessage() {
  const ta = document.getElementById('ws-input');
  const content = (ta.value || '').trim();
  if (!content) return;
  await withBusy(document.getElementById('ws-send'), async function () {
    try {
      const modeEl = document.getElementById('ws-interaction-mode');
      const targetEl = document.getElementById('ws-target-agent');
      const body = { content: content, zone: wsState.zone };
      if (wsState.zone === 'agent') {
        body.interaction_mode = modeEl ? modeEl.value : wsState.interactionMode;
        if (targetEl && targetEl.value) body.target_agent_id = Number(targetEl.value);
      }
      const r = await postApi('/api/workspaces/' + wsState.id + '/messages', body);
      ta.value = '';
      updateDispatchHint();
      const n = (r.dispatched || []).length;
      if (n) toast('已派发任务给：' + r.dispatched.map(function (d) { return d.agent_name; }).join('、'), 'info');
      const replies = r.replies || [];
      if (replies.length) {
        const ok = replies.filter(function (x) { return x.model_info && x.model_info.ok; }).length;
        toast(ok
          ? replies.map(function (x) { return x.agent_name; }).join('、') + ' 已完成真实模型回复'
          : '模型未完成回复，请查看对话中的原因', ok ? 'info' : 'error');
      }
      if (r.chat_error) toast(r.chat_error, 'error');
      /* R5 兜底：无可用数字员工时明确告知，需求已登记为待处理任务 */
      if (r.undispatched) {
        toast('数字员工暂时不可用，已登记待处理需求 #' + r.undispatched.pending_task_id +
          '，可在任务中心跟进', 'error');
      }
      await loadMessages(n > 0 || replies.length > 0 || !!r.undispatched);
    } catch (e) { toast(e.message, 'error'); }
  });
}
/* 审核（协作空间内） */
async function reviewTaskAction(taskId, action, comment) {
  try {
    await postApi('/api/tasks/' + taskId + '/review', { action: action, comment: comment || '' });
    toast(action === 'approve' ? '已通过，工时与产出已计入' : '已驳回，数字员工将自动重做');
    if (currentViewKey() === 'workspaces') await loadMessages(false);
    if (currentViewKey() === 'tasks') await renderTasks(document.getElementById('view-container'));
  } catch (e) { toast(e.message, 'error'); }
}
function openRejectModal(taskId) {
  openModal('<h3 class="font-bold text-primary text-lg mb-1">驳回交付物</h3>' +
    '<p class="text-xs text-gray-500 mb-3">驳回后数字员工将自动重做一轮，请写明批注。</p>' +
    '<label class="form-label">驳回批注</label>' +
    '<textarea id="reject-comment" class="form-textarea" rows="3" placeholder="请说明驳回原因与修改要求"></textarea>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-danger-sm !px-5 !py-2" onclick="submitReject(' + taskId + ')">确认驳回</button></div>');
}
function submitReject(taskId) {
  const comment = document.getElementById('reject-comment').value.trim();
  if (!comment) { toast('请填写驳回批注', 'error'); return; }
  closeModal();
  reviewTaskAction(taskId, 'reject', comment);
}

/* ==================== 视图 3：数字员工 ==================== */
function agentFiltersHtml() {
  return '<div class="data-card !p-3 flex flex-wrap items-center gap-2 mb-4">' +
    '<select id="f-platform" class="form-select !w-40"><option value="">全部平台</option></select>' +
    '<select id="f-status" class="form-select !w-32"><option value="">全部状态</option>' +
      AGENT_STATUS_LIST.map(function (s) { return '<option>' + s + '</option>'; }).join('') + '</select>' +
    '<select id="f-wave" class="form-select !w-32"><option value="">全部波次</option>' +
      [1, 2, 3, 4].map(function (w) { return '<option value="' + w + '">第' + w + '波</option>'; }).join('') + '</select>' +
    '<select id="f-category" class="form-select !w-44"><option value="">全部方向</option>' +
      AGENT_CATEGORY_LIST.map(function (s) { return '<option>' + s + '</option>'; }).join('') + '</select>' +
    '<button class="btn-primary" onclick="loadAgents()">筛选</button>' +
    '<button class="btn-ghost" onclick="resetAgentFilters()">重置</button>' +
    (canCreateAgent()
      ? '<div class="flex-1"></div><button class="btn-primary !bg-accent hover:!bg-accent/90" onclick="openAgentFormModal()">+ 新建数字员工</button>'
      : '') + '</div>';
}
async function renderAgents(c) {
  c.innerHTML = '<div id="model-default-card"></div>' + agentFiltersHtml() + '<div id="agents-grid">' + loadingHtml('加载数字员工…') + '</div>';
  await ensurePlatforms();
  try { await ensureModelsCache(); } catch (e) { cache.models = []; }
  renderModelDefaultCard();
  const sel = document.getElementById('f-platform');
  (cache.platforms || []).forEach(function (p) {
    const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; sel.appendChild(o);
  });
  await loadAgents();
  /* 深链：#/agents/<id> 直接打开档案抽屉；#/agents/new 直接打开新建弹窗（分享与验收直达） */
  const parts = (location.hash || '').replace(/^#\/?/, '').split('/');
  if (parts[0] === 'agents') {
    if (parts[1] === 'new' && canCreateAgent()) openAgentFormModal();
    else if (Number(parts[1])) openAgentDrawer(Number(parts[1]));
  }
}
async function ensurePlatforms() {
  if (cache.platforms) return;
  const tree = await api('/api/org/tree');
  cache.platforms = tree.map(function (p) { return { id: p.id, name: p.name }; });
  cache.depts = [];
  tree.forEach(function (p) {
    (p.departments || []).forEach(function (d) { cache.depts.push({ id: d.id, name: d.name, platform_name: p.name }); });
  });
}
/* R4 缓存：模型供应商 / Skill / MCP 台账 */
async function ensureModelsCache(force) {
  if (cache.models && !force) return;
  cache.models = await api('/api/models');
}
async function ensureSkillsCache(force) {
  if (cache.skills && !force) return;
  cache.skills = await api('/api/skills');
}
async function ensureMcpCache(force) {
  if (cache.mcp && !force) return;
  cache.mcp = await api('/api/mcp');
}
function defaultProvider() {
  return (cache.models || []).find(function (m) { return m.is_default; }) || null;
}
/* 模型下拉选项：空白=跟随全局默认；每个供应商标注 默认/Key 状态/停用 */
function modelOptionsHtml(selected) {
  const def = defaultProvider();
  let opts = '<option value="">跟随全局默认' + (def ? '（' + esc(def.name) + '）' : '') + '</option>';
  (cache.models || []).forEach(function (m) {
    const tags = [m.name];
    if (m.is_default) tags.push('默认');
    tags.push(m.api_key === '已配置' ? '已配置Key' : '未配置Key');
    if (!m.enabled) tags.push('已停用');
    opts += '<option value="' + esc(m.key) + '"' + (selected === m.key ? ' selected' : '') +
      (m.enabled ? '' : ' disabled') + '>' + esc(tags.join(' · ')) + '</option>';
  });
  return opts;
}
async function loadAgents() {
  const box = document.getElementById('agents-grid');
  box.innerHTML = loadingHtml('加载数字员工…');
  const qs = new URLSearchParams();
  ['platform', 'status', 'wave', 'category'].forEach(function (k) {
    const v = document.getElementById('f-' + k).value;
    if (v) qs.set(k === 'platform' ? 'platform_id' : k, v);
  });
  try {
    const list = await api('/api/agents' + (qs.toString() ? '?' + qs : ''));
    cache.agents = list;
    cache.agentMap = {};
    list.forEach(function (a) { cache.agentMap[a.id] = a; });
    if (!list.length) { box.innerHTML = '<div class="data-card">' + emptyHtml('没有符合条件的数字员工') + '</div>'; return; }
    box.innerHTML = '<div class="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">' + list.map(function (a) {
      return '<div class="data-card card-hover cursor-pointer" onclick="openAgentDrawer(' + a.id + ')">' +
        '<div class="flex items-start justify-between mb-2"><div class="msg-avatar bg-teal">' + ROBOT_SVG + '</div>' + statusBadge(a.status, AGENT_STATUS_META) + '</div>' +
        '<div class="font-bold text-primary truncate" title="' + esc(a.name) + '">' + esc(a.name) + '</div>' +
        '<div class="text-xs text-gray-500 mt-0.5">' + esc(a.dept_name || '') + ' · ' + esc(a.platform_name || '') + '</div>' +
        '<div class="flex flex-wrap gap-1 mt-2"><span class="badge badge-outline">' + esc(a.category || '-') + '</span>' +
        '<span class="badge bg-primary">第' + (a.wave ?? '-') + '波</span></div>' +
        '<div class="flex justify-between mt-3 pt-2 border-t border-gray-100 text-xs text-gray-500">' +
          '<span>累计任务 <b class="text-secondary">' + fmtNum(a.tasks_done) + '</b></span>' +
          '<span>节省工时 <b class="text-accent">' + fmtNum(a.hours_saved) + 'h</b></span></div></div>';
    }).join('') + '</div>';
  } catch (e) { box.innerHTML = errorHtml(e.message); }
}
function resetAgentFilters() {
  ['platform', 'status', 'wave', 'category'].forEach(function (k) { document.getElementById('f-' + k).value = ''; });
  loadAgents();
}
/* R4-1：数字员工视图顶部"全局默认模型"小卡（boss/coach 可切换） */
function renderModelDefaultCard() {
  const box = document.getElementById('model-default-card');
  if (!box) return;
  const def = defaultProvider() || {};
  let html = '<div class="data-card !p-3 mb-4 flex flex-wrap items-center gap-2 text-sm">' +
    '<span class="font-bold text-primary">全局默认模型</span>' +
    '<span class="badge bg-secondary">' + esc(def.name || '未设置') + '</span>' +
    '<span class="text-xs text-gray-400">' + esc(def.default_model || '') +
    (def.name ? ' · ' + (def.api_key === '已配置' ? '已配置 Key' : '未配置 Key（生成交付物时回落内置模板）') : '') + '</span>';
  if (canAdmin()) {
    html += '<span class="flex-1"></span>' +
      '<select id="global-model-sel" class="form-select !w-60">' +
      (cache.models || []).map(function (m) {
        return '<option value="' + esc(m.key) + '"' + (m.is_default ? ' selected' : '') + (m.enabled ? '' : ' disabled') + '>' +
          esc(m.name) + '（' + esc(m.default_model || '-') + '）' + (m.enabled ? '' : '【已停用】') + '</option>';
      }).join('') + '</select>' +
      '<button class="btn-primary" onclick="saveGlobalModel()">设为默认</button>';
  } else {
    html += '<span class="flex-1"></span><span class="text-xs text-gray-400">切换默认模型需高管/教练团权限</span>';
  }
  box.innerHTML = html + '</div>';
}
async function saveGlobalModel() {
  const key = document.getElementById('global-model-sel').value;
  try {
    const r = await putApi('/api/models/default', { key: key });
    const chosen = (r.providers || []).find(function (m) { return m.key === key; });
    toast('全局默认模型已切换为：' + (chosen ? chosen.name : key));
    await ensureModelsCache(true);
    renderModelDefaultCard();
  } catch (e) { toast(e.message, 'error'); }
}
let drawerAgentId = null;   // 当前抽屉中的数字员工 id（配置 Key 后局部刷新模型区用）
async function openAgentDrawer(id) {
  drawerAgentId = id;
  openDrawer(loadingHtml('加载档案…'));
  try {
    const a = await api('/api/agents/' + id);
    try { await ensureModelsCache(); } catch (e) { cache.models = cache.models || []; }
    let html = '<div class="p-5">' +
      '<div class="flex items-start justify-between">' +
        '<div class="flex items-center space-x-3"><div class="msg-avatar bg-teal !w-11 !h-11">' + ROBOT_SVG + '</div>' +
          '<div><div class="font-black text-lg text-primary">' + esc(a.name) + '</div>' +
          '<div class="text-xs text-gray-500">' + esc(a.code || '') + ' · ' + esc(a.dept_name || '') + '</div></div></div>' +
        '<div class="flex items-center space-x-2 shrink-0">' +
          (canEditAgent(a) ? '<button class="btn-ghost !py-1 !px-2.5 text-xs" onclick="openAgentFormModal(' + a.id + ')">编辑</button>' : '') +
          '<button onclick="closeDrawer()" class="text-gray-400 hover:text-gray-700"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></button></div></div>' +
      '<div class="flex flex-wrap gap-1.5 mt-3">' + statusBadge(a.status, AGENT_STATUS_META) +
        '<span class="badge bg-primary">第' + (a.wave ?? '-') + '波</span>' +
        '<span class="badge badge-outline">' + esc(a.category || '-') + '</span></div>' +
      '<div class="grid grid-cols-3 gap-2 mt-4 text-center">' +
        '<div class="bg-gray-50 rounded-lg p-2"><div class="text-lg font-black text-secondary">' + fmtNum(a.tasks_done) + '</div><div class="text-xs text-gray-500">累计任务</div></div>' +
        '<div class="bg-gray-50 rounded-lg p-2"><div class="text-lg font-black text-accent">' + fmtNum(a.hours_saved) + '</div><div class="text-xs text-gray-500">节省工时(h)</div></div>' +
        '<div class="bg-gray-50 rounded-lg p-2"><div class="text-lg font-black text-success">' + (a.accuracy ?? '-') + '%</div><div class="text-xs text-gray-500">准确率</div></div></div>' +
      '<div class="mt-4"><div class="text-xs font-bold text-gray-500 mb-1">负责人（超级个体）</div>' +
        '<div class="text-sm">' + esc(a.owner_name || '未指定') + '</div></div>' +
      '<div class="mt-3"><div class="text-xs font-bold text-gray-500 mb-1">简介</div>' +
        '<div class="text-sm text-gray-700 leading-relaxed">' + esc(a.description || '暂无') + '</div></div>' +
      '<div class="mt-3"><div class="text-xs font-bold text-gray-500 mb-1.5">技能标签云</div><div class="flex flex-wrap gap-1.5">' +
        ((a.skills || []).length ? a.skills.map(function (s) { return '<span class="badge bg-secondary">' + esc(s) + '</span>'; }).join('') : '<span class="text-xs text-gray-400">暂无技能标签</span>') +
      '</div></div>' +
      /* R4-1：模型区 */
      '<div class="mt-4" id="agent-model-box">' + agentModelBoxHtml(a) + '</div>' +
      /* R4-2：MCP 服务区 */
      '<div class="mt-4"><div class="text-xs font-bold text-gray-500 mb-1.5">MCP 服务（' + (a.mcp || []).length + '）</div>' +
        ((a.mcp || []).length ? '<div class="space-y-1.5">' + a.mcp.map(function (m) {
          return '<div class="border border-gray-100 rounded-lg px-3 py-2">' +
            '<div class="flex items-center justify-between"><span class="text-sm font-medium">' + esc(m.name) + '</span>' +
            statusBadge(m.status, { '启用': 'bg-success', '停用': 'bg-gray-400' }) + '</div>' +
            '<div class="text-xs text-gray-400 mt-0.5 font-mono">' + esc(m.endpoint || '') + '</div></div>';
        }).join('') + '</div>' : '<div class="text-xs text-gray-400">未绑定 MCP 服务，可在「编辑」中选择</div>') + '</div>' +
      '<div class="mt-4"><div class="text-xs font-bold text-gray-500 mb-1.5">绑定场景（' + (a.scenarios || []).length + '）</div>' +
        ((a.scenarios || []).length ? '<div class="space-y-1.5">' + a.scenarios.map(function (s) {
          return '<div class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 text-sm">' +
            '<span class="truncate mr-2">' + esc(s.name) + '</span><span class="flex items-center gap-1 shrink-0">' +
            priorityBadge(s.priority) + statusBadge(s.status, SCENARIO_STATUS_META) + '</span></div>';
        }).join('') + '</div>' : '<div class="text-xs text-gray-400">暂未绑定场景</div>') + '</div>' +
      '<div class="mt-4"><div class="text-xs font-bold text-gray-500 mb-1">近 14 天产出</div><div id="chart-agent-14d" class="chart-box-sm"></div></div>' +
      '<div class="mt-4"><div class="text-xs font-bold text-gray-500 mb-1.5">最近任务（' + (a.recent_tasks || []).length + '）</div>' +
        ((a.recent_tasks || []).length ? '<div class="space-y-1.5 mb-4">' + a.recent_tasks.map(function (t) {
          return '<div class="border border-gray-100 rounded-lg px-3 py-2"><div class="flex items-center justify-between">' +
            '<span class="text-sm truncate mr-2">' + esc(t.title) + '</span>' + statusBadge(t.status, TASK_STATUS_META) + '</div>' +
            '<div class="text-xs text-gray-400 mt-0.5">创建 ' + fmtTime(t.created_at) + (t.done_at ? ' · 完成 ' + fmtTime(t.done_at) : '') + '</div></div>';
        }).join('') + '</div>' : '<div class="text-xs text-gray-400 mb-4">暂无任务记录</div>') + '</div>' +
    '</div>';
    openDrawer(html);
    const mc = makeChart('chart-agent-14d');
    if (mc) {
      const m14 = a.metrics_14d || [];
      mc.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['任务数', '工时(h)'], top: 0, textStyle: { fontSize: 10 } },
        grid: { left: 35, right: 35, top: 28, bottom: 22 },
        xAxis: { type: 'category', data: m14.map(function (x) { return (x.date || '').slice(5); }), axisLabel: { fontSize: 9 } },
        yAxis: [{ type: 'value' }, { type: 'value', splitLine: { show: false } }],
        series: [
          { name: '任务数', type: 'line', smooth: true, data: m14.map(function (x) { return x.tasks_done; }), itemStyle: { color: '#2c5282' } },
          { name: '工时(h)', type: 'line', smooth: true, yAxisIndex: 1, data: m14.map(function (x) { return x.hours_saved; }), itemStyle: { color: '#ed8936' } },
        ],
      });
    }
  } catch (e) { openDrawer(errorHtml(e.message)); }
}

/* ---------- R4-1：模型选择 / Key 配置 ---------- */
function agentModelBoxHtml(a) {
  const editable = canEditAgent(a);
  return '<div class="text-xs font-bold text-gray-500 mb-1.5">模型</div>' +
    '<div class="flex items-center gap-2">' +
      '<select class="form-select" id="agent-model-sel"' +
        (editable ? ' onchange="saveAgentModel(' + a.id + ', this.value)"' : ' disabled') + '>' +
        modelOptionsHtml(a.model_key || '') + '</select>' +
      (canAdmin() ? '<button class="btn-ghost !py-1.5 !px-2.5 text-xs shrink-0" title="配置模型供应商的 API Key" onclick="openModelKeyModal()">配置 Key</button>' : '') +
    '</div>' +
    '<div class="text-[11px] text-gray-400 mt-1">' +
      (editable ? '未配置 Key 或已停用的模型，生成交付物时自动回落内置模板' : '仅高管/教练团或负责人本人可调整模型') + '</div>';
}
async function saveAgentModel(agentId, key) {
  try {
    await patchApi('/api/agents/' + agentId, { model_key: key || '' });
    toast(key ? '已切换模型，下次生成交付物生效' : '已恢复跟随全局默认模型');
  } catch (e) {
    toast(e.message, 'error');
    if (drawerAgentId) openAgentDrawer(drawerAgentId);   // 失败回退选中态
  }
}
function openModelKeyModal() {
  const curSel = document.getElementById('agent-model-sel');
  const preKey = (curSel && curSel.value) || (defaultProvider() || {}).key || '';
  openModal('<h3 class="font-bold text-primary text-lg mb-1">配置模型供应商</h3>' +
    '<p class="text-xs text-gray-500 mb-3">Key 只保存在服务端，这里永远看不到明文；留空的字段不会被修改。</p>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">供应商</label><select id="mk-provider" class="form-select" onchange="fillModelKeyForm()">' +
        (cache.models || []).map(function (m) {
          return '<option value="' + esc(m.key) + '"' + (m.key === preKey ? ' selected' : '') + '>' + esc(m.name) + '</option>';
        }).join('') + '</select></div>' +
      '<div><label class="form-label">API Key</label><input id="mk-key" class="form-input" type="password" placeholder="">' +
        '<div id="mk-key-state" class="text-[11px] text-gray-400 mt-1"></div></div>' +
      '<div><label class="form-label">接口地址 Base URL</label><input id="mk-baseurl" class="form-input" placeholder=""></div>' +
      '<div><label class="form-label">默认模型名</label><input id="mk-model" class="form-input" placeholder=""></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">温度 temperature</label><input id="mk-temp" class="form-input" type="number" min="0" max="2" step="0.1" placeholder="0.4">' +
          '<div class="text-[11px] text-gray-400 mt-1">Kimi Coding 等要求 1.0 的服务请改为 1</div></div>' +
        '<div><label class="form-label">超时（秒）</label><input id="mk-timeout" class="form-input" type="number" min="5" max="120" step="1" placeholder="30"></div></div>' +
      '<label class="inline-flex items-center gap-2 text-sm text-gray-600 cursor-pointer">' +
        '<input type="checkbox" id="mk-enabled" class="accent-secondary">启用该供应商（停用后引用它的数字员工回落模板）</label>' +
      '<div id="mk-test-result" class="text-xs"></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-ghost" onclick="testModelConn()">测试连接</button>' +
      '<button class="btn-primary" id="mk-submit" onclick="submitModelKey()">保存配置</button></div>');
  fillModelKeyForm();
}
function fillModelKeyForm() {
  const key = document.getElementById('mk-provider').value;
  const m = (cache.models || []).find(function (x) { return x.key === key; }) || {};
  document.getElementById('mk-key').placeholder = m.api_key === '已配置' ? '已配置（留空保持不变）' : '粘贴 API Key';
  document.getElementById('mk-key-state').textContent = '当前状态：' + (m.api_key || '未配置');
  document.getElementById('mk-baseurl').placeholder = m.base_url || 'https://...';
  document.getElementById('mk-baseurl').value = m.base_url || '';
  document.getElementById('mk-model').placeholder = m.default_model || '如 glm-4-flash';
  document.getElementById('mk-temp').value = (m.temperature != null) ? m.temperature : 0.4;
  document.getElementById('mk-timeout').value = m.timeout || 30;
  document.getElementById('mk-enabled').checked = !!m.enabled;
  document.getElementById('mk-test-result').innerHTML = '';
}
async function testModelConn() {
  const key = document.getElementById('mk-provider').value;
  const box = document.getElementById('mk-test-result');
  box.innerHTML = '<span class="text-gray-400">正在测试连接…</span>';
  try {
    const r = await postApi('/api/models/' + key + '/test', {});
    box.innerHTML = r.ok
      ? '<span class="text-success">连接成功 · ' + r.latency_ms + 'ms · 可用模型 ' + r.models_count + ' 个</span>'
      : '<span class="text-danger">连接失败：' + esc(r.error || '未知错误') + '</span>';
  } catch (e) {
    box.innerHTML = '<span class="text-danger">连接失败：' + esc(e.message) + '</span>';
  }
}
async function submitModelKey() {
  const key = document.getElementById('mk-provider').value;
  const body = { enabled: document.getElementById('mk-enabled').checked };
  const apiKey = document.getElementById('mk-key').value.trim();
  const baseUrl = document.getElementById('mk-baseurl').value.trim();
  const model = document.getElementById('mk-model').value.trim();
  const temp = document.getElementById('mk-temp').value.trim();
  const timeout = document.getElementById('mk-timeout').value.trim();
  if (apiKey) body.api_key = apiKey;
  if (baseUrl) body.base_url = baseUrl;
  if (model) body.default_model = model;
  if (temp) body.temperature = parseFloat(temp);
  if (timeout) body.timeout = parseInt(timeout, 10);
  await withBusy(document.getElementById('mk-submit'), async function () {
    try {
      await putApi('/api/models/' + key, body);
      closeModal();
      toast('模型供应商配置已保存');
      await ensureModelsCache(true);
      renderModelDefaultCard();
      if (drawerAgentId && document.getElementById('agent-model-box')) {
        const a = await api('/api/agents/' + drawerAgentId);
        document.getElementById('agent-model-box').innerHTML = agentModelBoxHtml(a);
      }
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* ---------- R4-2：新建 / 编辑数字员工 ---------- */
async function openAgentFormModal(agentId) {
  await ensurePlatforms();
  await Promise.all([ensureSkillsCache(), ensureMcpCache(), ensureModelsCache()]);
  let a = null;
  if (agentId) a = await api('/api/agents/' + agentId);
  const skillSet = {}; ((a && a.skills) || []).forEach(function (s) { skillSet[s] = 1; });
  const mcpSet = {}; ((a && a.mcp_ids) || []).forEach(function (i) { mcpSet[i] = 1; });
  const categories = AGENT_CATEGORY_LIST.filter(function (x) { return x !== '通用'; });
  openModal('<h3 class="font-bold text-primary text-lg mb-1">' + (a ? '编辑数字员工' : '新建数字员工') + '</h3>' +
    '<p class="text-xs text-gray-500 mb-3">' + (a ? '修改档案信息，保存后立即生效。' : '编号自动生成，初始状态为「规划中」，可稍后在档案中调整。') + '</p>' +
    '<div class="space-y-3">' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">名称 *</label><input id="af-name" class="form-input" placeholder="如：单证审核数字员工" value="' + esc(a ? a.name : '') + '"></div>' +
        '<div><label class="form-label">所属部门 *</label><select id="af-dept" class="form-select">' +
          (cache.depts || []).map(function (d) {
            return '<option value="' + d.id + '"' + (a && a.dept_id === d.id ? ' selected' : '') + '>' + esc(d.platform_name) + ' / ' + esc(d.name) + '</option>';
          }).join('') + '</select></div></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">方向</label><select id="af-category" class="form-select">' +
          categories.map(function (x) {
            return '<option' + (a && a.category === x ? ' selected' : '') + '>' + x + '</option>';
          }).join('') + '</select></div>' +
        '<div><label class="form-label">模型</label><select id="af-model" class="form-select">' + modelOptionsHtml((a && a.model_key) || '') + '</select></div></div>' +
      '<div><label class="form-label">描述</label><textarea id="af-desc" class="form-textarea" rows="2" placeholder="这个数字员工负责什么、怎么用它">' + esc(a ? (a.description || '') : '') + '</textarea></div>' +
      '<div><label class="form-label">技能（多选）</label><div class="border border-gray-200 rounded-lg p-2.5 max-h-32 overflow-y-auto grid grid-cols-2 gap-1">' +
        (cache.skills || []).map(function (s) {
          return '<label class="inline-flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">' +
            '<input type="checkbox" name="af-skill" value="' + esc(s.name) + '"' + (skillSet[s.name] ? ' checked' : '') + ' class="accent-secondary">' + esc(s.name) + '</label>';
        }).join('') + '</div></div>' +
      '<div><label class="form-label">MCP 服务（多选）</label><div class="border border-gray-200 rounded-lg p-2.5 space-y-1">' +
        ((cache.mcp || []).length ? cache.mcp.map(function (m) {
          return '<label class="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">' +
            '<input type="checkbox" name="af-mcp" value="' + m.id + '"' + (mcpSet[m.id] ? ' checked' : '') + ' class="accent-secondary">' +
            '<span class="font-medium">' + esc(m.name) + '</span><span class="text-gray-400 font-mono">' + esc(m.endpoint || '') + '</span>' +
            (m.status === '停用' ? '<span class="badge bg-gray-400">停用</span>' : '') + '</label>';
        }).join('') : '<div class="text-xs text-gray-400">暂无 MCP 服务，可先在「Skill 库」底部的 MCP 台账中登记</div>') + '</div></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="af-submit" onclick="submitAgentForm(' + (a ? a.id : 0) + ')">' + (a ? '保存修改' : '创建') + '</button></div>');
}
async function submitAgentForm(agentId) {
  const body = {
    name: document.getElementById('af-name').value.trim(),
    dept_id: Number(document.getElementById('af-dept').value),
    category: document.getElementById('af-category').value,
    description: document.getElementById('af-desc').value.trim(),
    model_key: document.getElementById('af-model').value || '',
    skills: Array.prototype.map.call(document.querySelectorAll('input[name="af-skill"]:checked'), function (el) { return el.value; }),
    mcp_ids: Array.prototype.map.call(document.querySelectorAll('input[name="af-mcp"]:checked'), function (el) { return Number(el.value); }),
  };
  if (!body.name) { toast('请填写名称', 'error'); return; }
  await withBusy(document.getElementById('af-submit'), async function () {
    try {
      if (agentId) {
        await patchApi('/api/agents/' + agentId, body);
        closeModal();
        toast('数字员工档案已更新');
        openAgentDrawer(agentId);
      } else {
        const r = await postApi('/api/agents', body);
        closeModal();
        toast('数字员工「' + r.name + '」已创建（' + (r.code || '') + '）');
        cache.agents = null;   // 让协作空间 @ 候选等用到缓存的地方下次重新拉取
      }
      const grid = document.getElementById('agents-grid');
      if (grid) loadAgents();
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* ==================== 视图 4：场景库（R4-5：平台/部门分组 + 推荐排序） ==================== */
const scenState = { sort: 'recommend' };   // recommend=推荐排序 benefit=按预期收益 priority=按优先级
const SCEN_PRI_W = { '高': 3, '中': 2, '低': 1 };
/* 从 "12.24万/年" / "预估3万/年" 等文本中解析收益数值（万元） */
function scenBenefitValue(s) {
  const t = String(s.expected_benefit || '');
  let m = t.match(/([\d.]+)\s*万/);
  if (m) return parseFloat(m[1]) || 0;
  m = t.match(/([\d.]+)/);
  if (m) {
    const v = parseFloat(m[1]) || 0;
    return v > 1000 ? v / 10000 : v;   // 无"万"字的大数按元折算
  }
  return 0;
}
/* 推荐分 = 优先级(高3/中2/低1) + 收益归一化(0-2) + 首批试点加成(2) */
function scenScore(s, maxBen) {
  return (SCEN_PRI_W[s.priority] || 0) + (maxBen > 0 ? scenBenefitValue(s) / maxBen * 2 : 0) + (s.batch === '首批' ? 2 : 0);
}
function setScenSort(v) {
  scenState.sort = v;
  loadScenarios();
}
function scenarioFiltersHtml() {
  return '<div class="data-card !p-3 flex flex-wrap items-center gap-2 mb-4">' +
    '<select id="sf-platform" class="form-select !w-40"><option value="">全部平台</option></select>' +
    '<select id="sf-status" class="form-select !w-32"><option value="">全部状态</option>' +
      Object.keys(SCENARIO_STATUS_META).map(function (s) { return '<option>' + s + '</option>'; }).join('') + '</select>' +
    '<select id="sf-priority" class="form-select !w-32"><option value="">全部优先级</option><option>高</option><option>中</option><option>低</option></select>' +
    '<button class="btn-primary" onclick="loadScenarios()">筛选</button>' +
    '<button class="btn-ghost" onclick="resetScenarioFilters()">重置</button>' +
    '<span class="text-xs text-gray-400 ml-2">排序</span>' +
    '<select id="sf-sort" class="form-select !w-36" onchange="setScenSort(this.value)">' +
      '<option value="recommend"' + (scenState.sort === 'recommend' ? ' selected' : '') + '>推荐排序</option>' +
      '<option value="benefit"' + (scenState.sort === 'benefit' ? ' selected' : '') + '>按预期收益</option>' +
      '<option value="priority"' + (scenState.sort === 'priority' ? ' selected' : '') + '>按优先级</option></select>' +
    '<div class="flex-1"></div>' +
    '<button class="btn-primary !bg-accent hover:!bg-accent/90" onclick="openScenarioModal()">+ 新建场景</button></div>';
}
async function renderScenarios(c) {
  c.innerHTML = scenarioFiltersHtml() + '<div id="scenarios-box">' + loadingHtml('加载场景…') + '</div>';
  await ensurePlatforms();
  const sel = document.getElementById('sf-platform');
  (cache.platforms || []).forEach(function (p) {
    const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; sel.appendChild(o);
  });
  await loadScenarios();
}
function resetScenarioFilters() {
  ['sf-platform', 'sf-status', 'sf-priority'].forEach(function (k) { document.getElementById(k).value = ''; });
  loadScenarios();
}
async function loadScenarios() {
  const box = document.getElementById('scenarios-box');
  box.innerHTML = loadingHtml('加载场景…');
  const qs = new URLSearchParams();
  const pf = document.getElementById('sf-platform').value;
  const st = document.getElementById('sf-status').value;
  const pr = document.getElementById('sf-priority').value;
  if (pf) qs.set('platform_id', pf);
  if (st) qs.set('status', st);
  if (pr) qs.set('priority', pr);
  try {
    const list = await api('/api/scenarios' + (qs.toString() ? '?' + qs : ''));
    /* 已立项场景 → 项目流程 id 映射（操作列"流程"跳转按钮用；接口不可用时静默降级） */
    let flowMap = {};
    try { (await api('/api/flows')).forEach(function (f) { flowMap[f.scenario_id] = f.id; }); } catch (e) {}
    if (!list.length) { box.innerHTML = '<div class="data-card">' + emptyHtml('暂无场景，点击右上角「新建场景」发起申报') + '</div>'; return; }
    /* R4-5：收益归一化的分母 = 当前筛选结果中的最大收益 */
    let maxBen = 0;
    list.forEach(function (s) { maxBen = Math.max(maxBen, scenBenefitValue(s)); });
    /* 平台分组 → 部门子分组；排序在部门组内进行（推荐/收益/优先级） */
    const sortFn = {
      recommend: function (a, b) { return scenScore(b, maxBen) - scenScore(a, maxBen); },
      benefit:   function (a, b) { return scenBenefitValue(b) - scenBenefitValue(a); },
      priority:  function (a, b) { return (SCEN_PRI_W[b.priority] || 0) - (SCEN_PRI_W[a.priority] || 0) || scenBenefitValue(b) - scenBenefitValue(a); },
    }[scenState.sort] || function () { return 0; };
    const platMap = {};
    list.forEach(function (s) {
      const k = s.platform_id || 0;
      if (!platMap[k]) platMap[k] = { name: s.platform_name || '其他', items: [] };
      platMap[k].items.push(s);
    });
    const platOrder = (cache.platforms || []).map(function (p) { return p.id; });
    const platKeys = Object.keys(platMap).map(Number).sort(function (a, b) {
      const ia = platOrder.indexOf(a), ib = platOrder.indexOf(b);
      return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
    });
    let html = '';
    platKeys.forEach(function (pk) {
      const g = platMap[pk];
      const pilotCnt = g.items.filter(function (s) { return s.status === '试点中'; }).length;
      const deptMap = {};
      g.items.forEach(function (s) {
        const dk = s.dept_id || 0;
        if (!deptMap[dk]) deptMap[dk] = { name: s.dept_name || '未分配部门', items: [] };
        deptMap[dk].items.push(s);
      });
      const deptKeys = Object.keys(deptMap).map(Number).sort(function (a, b) { return a - b; });
      /* 平台大区块标题：平台名 + 场景数 + 试点数；默认展开可折叠 */
      html += '<details class="tree-platform data-card !p-0 mb-4" open><summary class="flex items-center space-x-3 px-4 py-3">' +
        '<span class="tree-arrow text-gray-400">▶</span>' +
        '<span class="font-bold text-primary">' + esc(g.name) + '</span>' +
        '<span class="badge bg-secondary">场景 ' + g.items.length + '</span>' +
        (pilotCnt ? '<span class="badge bg-teal">试点中 ' + pilotCnt + '</span>' : '<span class="text-xs text-gray-400">暂无试点</span>') +
        '</summary><div class="px-4 pb-4 space-y-3">';
      deptKeys.forEach(function (dk) {
        const dg = deptMap[dk];
        const items = dg.items.slice().sort(sortFn);
        html += '<div class="border border-gray-100 rounded-lg overflow-hidden">' +
          '<div class="flex items-center space-x-2 px-3 py-2 bg-gray-50 border-b border-gray-100">' +
            '<span class="text-sm font-bold text-secondary">' + esc(dg.name) + '</span>' +
            '<span class="text-xs text-gray-400">' + items.length + ' 个场景</span></div>' +
          '<div class="overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
            '<th>场景名称</th><th>数字员工</th><th>优先级</th><th>批次</th><th>预期收益</th><th>状态</th><th>操作</th>' +
            '</tr></thead><tbody>' +
          items.map(function (s) {
            const hot = scenScore(s, maxBen) >= 5;
            return '<tr>' +
              '<td><div class="flex items-center gap-1.5 flex-wrap"><span class="font-medium">' + esc(s.name) + '</span>' +
                (hot ? '<span class="badge bg-danger" title="推荐分≥5：优先级高/收益高/首批试点">🔥重点推荐</span>' : '') +
                (s.batch === '首批' ? '<span class="badge badge-gold">首批试点</span>' : '') + '</div>' +
                '<div class="text-xs text-gray-400 mt-0.5 max-w-xs truncate" title="' + esc(s.description || '') + '">' + esc(s.description || '') + '</div></td>' +
              '<td class="whitespace-nowrap">' + (s.agent_name ? esc(s.agent_name) : '<span class="text-gray-400">未绑定</span>') + '</td>' +
              '<td>' + priorityBadge(s.priority) + '</td>' +
              '<td class="whitespace-nowrap">' + esc(s.batch || '-') + '</td>' +
              '<td class="whitespace-nowrap">' + esc(s.expected_benefit || '-') + '</td>' +
              '<td>' + statusBadge(s.status, SCENARIO_STATUS_META) + '</td>' +
              '<td class="whitespace-nowrap">' + (s.status === '待立项'
                ? '<button class="btn-success-sm" onclick="initiateScenario(' + s.id + ')">敏捷立项</button>'
                : (flowMap[s.id]
                  ? '<button class="btn-ghost !py-1 !px-2.5 !text-xs" title="查看该场景的项目流程泳道" onclick="gotoFlow(' + flowMap[s.id] + ')">流程</button>'
                  : '<span class="text-xs text-gray-300">—</span>')) + '</td></tr>';
          }).join('') + '</tbody></table></div></div>';
      });
      html += '</div></details>';
    });
    box.innerHTML = html;
  } catch (e) { box.innerHTML = errorHtml(e.message); }
}
async function initiateScenario(id) {
  try {
    const r = await postApi('/api/scenarios/' + id + '/initiate');
    toast('立项成功，已自动创建项目工作区「' + (r.workspace || {}).name + '」' + (r.flow_id ? '，项目流程已生成（见「项目流程」）' : ''));
    wsState.id = (r.workspace || {}).id || null;
    wsState.zone = 'discussion';
    if (location.hash === '#/workspaces') route();
    else location.hash = '#/workspaces';
  } catch (e) { toast(e.message, 'error'); }
}
async function openScenarioModal() {
  await ensurePlatforms();
  openModal('<h3 class="font-bold text-primary text-lg mb-4">新建场景申报</h3>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">场景名称 *</label><input id="ns-name" class="form-input" placeholder="如：供应商报价单智能归档"></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">所属部门 *</label><select id="ns-dept" class="form-select">' +
          (cache.depts || []).map(function (d) { return '<option value="' + d.id + '">' + esc(d.platform_name) + ' / ' + esc(d.name) + '</option>'; }).join('') + '</select></div>' +
        '<div><label class="form-label">优先级</label><select id="ns-priority" class="form-select"><option>高</option><option selected>中</option><option>低</option></select></div></div>' +
      '<div><label class="form-label">预期收益</label><input id="ns-benefit" class="form-input" placeholder="如：预估3万/年"></div>' +
      '<div><label class="form-label">场景描述</label><textarea id="ns-desc" class="form-textarea" rows="2" placeholder="业务痛点与期望效果"></textarea></div>' +
      '<div><label class="form-label">动作清单（每行一个）</label><textarea id="ns-actions" class="form-textarea" rows="2" placeholder="报价单识别归档&#10;比价表生成"></textarea></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="ns-submit" onclick="submitScenario()">提交申报</button></div>');
}
async function submitScenario() {
  const body = {
    name: document.getElementById('ns-name').value.trim(),
    dept_id: Number(document.getElementById('ns-dept').value),
    priority: document.getElementById('ns-priority').value,
    expected_benefit: document.getElementById('ns-benefit').value.trim(),
    description: document.getElementById('ns-desc').value.trim(),
    actions: document.getElementById('ns-actions').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean),
  };
  if (!body.name) { toast('请填写场景名称', 'error'); return; }
  await withBusy(document.getElementById('ns-submit'), async function () {
    try {
      await postApi('/api/scenarios', body);
      closeModal();
      toast('场景申报成功，待敏捷立项');
      loadScenarios();
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* ==================== 视图 5：任务中心 ==================== */
const taskState = { onlyMine: false };
function toggleTaskOnlyMine(v) {
  taskState.onlyMine = v;
  renderTasks(document.getElementById('view-container'));
}
async function renderTasks(c) {
  c.innerHTML = loadingHtml('加载任务…');
  taskCache = await api('/api/tasks');
  const myId = state.person ? state.person.id : null;
  const shown = (taskState.onlyMine && myId)
    ? taskCache.filter(function (t) { return t.status === '待审核' && t.reviewer_id === myId; })
    : taskCache;
  const cols = {};
  TASK_COLUMNS.forEach(function (s) { cols[s] = []; });
  shown.forEach(function (t) { if (cols[t.status]) cols[t.status].push(t); });
  const now = Date.now();
  let html = '<div class="flex items-center justify-between flex-wrap gap-2 mb-3">' +
    '<label class="inline-flex items-center gap-2 text-sm text-gray-600 cursor-pointer bg-white border border-gray-200 rounded-lg px-3 py-1.5 shadow-sm">' +
      '<input type="checkbox" ' + (taskState.onlyMine ? 'checked' : '') + ' onchange="toggleTaskOnlyMine(this.checked)" class="accent-secondary">只看待我审核</label>' +
    '<button class="btn-primary" onclick="openTaskModal()">+ 新建任务</button></div>';
  html += '<div class="flex gap-4 overflow-x-auto pb-3">';
  TASK_COLUMNS.forEach(function (s) {
    const items = cols[s];
    html += '<div class="kanban-col"><div class="px-3 py-2.5 border-b border-gray-100 flex items-center justify-between shrink-0">' +
      '<span class="flex items-center gap-1.5">' + statusBadge(s, TASK_STATUS_META) + '</span>' +
      '<span class="text-xs text-gray-400 font-bold">' + items.length + '</span></div>' +
      '<div class="kanban-cards">';
    if (!items.length) {
      html += '<div class="text-center text-xs text-gray-400 py-6 px-2">' +
        (taskState.onlyMine ? '没有待你审核的任务，去协作空间 @数字员工 派一个吧' : '还没有任务，去协作空间 @数字员工 派一个吧') + '</div>';
    }
    items.forEach(function (t) {
      let deadlineCls = 'text-gray-400';
      if (t.deadline && t.status !== '已通过' && t.status !== '已驳回') {
        const diff = new Date(t.deadline).getTime() - now;
        if (diff < 48 * 3600 * 1000) deadlineCls = 'text-danger font-bold';
      }
      const clickable = t.status === '待审核';
      html += '<div class="task-card ' + (clickable ? 'clickable' : '') + '" ' + (clickable ? 'onclick="openTaskReviewModal(' + t.id + ')"' : '') + '>' +
        '<div class="text-sm font-medium leading-snug">' + esc(t.title) + '</div>' +
        '<div class="flex items-center gap-1.5 mt-2 flex-wrap">' + priorityBadge(t.priority) +
          (t.agent_name ? '<span class="badge bg-teal">' + esc(t.agent_name) + '</span>' : '') + '</div>' +
        '<div class="flex items-center justify-between mt-2 text-xs">' +
          '<span class="text-gray-400">创建人：' + esc(t.creator_name || '-') + '</span>' +
          (t.deadline ? '<span class="' + deadlineCls + '">截止 ' + fmtTime(t.deadline) + '</span>' : '') + '</div>' +
        (!t.agent_id ? '<div class="mt-2 bg-orange-50 border border-orange-200 text-orange-700 text-xs rounded px-2 py-1.5 leading-snug">未指派数字员工，不会自动执行，建议去协作空间 @ 派活</div>' : '') +
        (clickable ? '<div class="mt-2 text-xs ' + (canReview() ? 'text-accent font-medium' : 'text-gray-400') + '">' +
          (canReview() ? '点击审核 →' : '需业务骨干/教练团审核') + '</div>' : '') +
      '</div>';
    });
    html += '</div></div>';
  });
  html += '</div>';
  c.innerHTML = html;
}
async function openTaskModal() {
  await ensureAgentsCache();
  openModal('<h3 class="font-bold text-primary text-lg mb-1">新建任务</h3>' +
    '<p class="text-xs text-gray-500 mb-3">指派数字员工后会立即执行并产出交付物；不指派则保持待处理。</p>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">任务标题 *</label><input id="nt-title" class="form-input" placeholder="如：整理8月展会客户名单"></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">数字员工（可选）</label><select id="nt-agent" class="form-select">' +
          '<option value="">暂不指派</option>' +
          (cache.agents || []).map(function (a) { return '<option value="' + a.id + '">' + esc(a.name) + '</option>'; }).join('') + '</select></div>' +
        '<div><label class="form-label">优先级</label><select id="nt-priority" class="form-select"><option>高</option><option selected>中</option><option>低</option></select></div></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="nt-submit" onclick="submitTask()">创建</button></div>');
}
async function submitTask() {
  const body = {
    title: document.getElementById('nt-title').value.trim(),
    priority: document.getElementById('nt-priority').value,
  };
  const agentId = Number(document.getElementById('nt-agent').value);
  if (agentId) body.agent_id = agentId;
  if (!body.title) { toast('请填写任务标题', 'error'); return; }
  await withBusy(document.getElementById('nt-submit'), async function () {
    try {
      const r = await postApi('/api/tasks', body);
      closeModal();
      if (r && r.hint) toast(r.hint, 'info');
      else toast(agentId ? '任务已创建，数字员工已完成执行，待审核' : '任务已创建');
      renderTasks(document.getElementById('view-container'));
    } catch (e) { toast(e.message, 'error'); }
  });
}
function openTaskReviewModal(id) {
  const t = taskCache.find(function (x) { return x.id === id; });
  if (!t) return;
  const canRev = canReview() && t.status === '待审核';
  openModal(
    '<div class="flex items-start justify-between mb-3"><h3 class="font-bold text-primary text-lg">任务审核 #' + t.id + '</h3>' +
    statusBadge(t.status, TASK_STATUS_META) + '</div>' +
    '<div class="space-y-3 text-sm">' +
      '<div><div class="text-xs font-bold text-gray-500 mb-1">任务需求</div>' +
        '<div class="bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">' + esc(t.requirement || t.title) + '</div></div>' +
      '<div><div class="text-xs font-bold text-gray-500 mb-1">交付物</div>' +
        '<div class="bg-gray-50 rounded-lg p-3 max-h-64 overflow-y-auto">' + mdLite(t.deliverable) + '</div></div>' +
      '<div class="grid grid-cols-3 gap-2 text-xs text-gray-500">' +
        '<div>数字员工：<b class="text-gray-700">' + esc(t.agent_name || '-') + '</b></div>' +
        '<div>创建人：<b class="text-gray-700">' + esc(t.creator_name || '-') + '</b></div>' +
        '<div>优先级：' + priorityBadge(t.priority) + '</div></div>' +
      (canRev ? '<div><label class="form-label">审核批注（驳回必填）</label>' +
        '<textarea id="review-comment" class="form-textarea" rows="2" placeholder="通过可不填；驳回请说明修改要求"></textarea></div>' : '') +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      (canRev
        ? '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
          '<button class="btn-danger-sm !px-5 !py-2" onclick="submitTaskReview(' + t.id + ',\'reject\')">驳回</button>' +
          '<button class="btn-success-sm !px-5 !py-2" onclick="submitTaskReview(' + t.id + ',\'approve\')">通过</button>'
        : '<span class="text-xs text-gray-400 self-center mr-auto">需业务骨干/教练团审核</span>' +
          '<button class="btn-ghost" onclick="closeModal()">关闭</button>') +
    '</div>');
}
function submitTaskReview(id, action) {
  const ta = document.getElementById('review-comment');
  const comment = ta ? ta.value.trim() : '';
  if (action === 'reject' && !comment) { toast('驳回请填写批注', 'error'); return; }
  closeModal();
  reviewTaskAction(id, action, comment);
}

/* ==================== 视图 6：Skill 库（含 MCP 服务台账） ==================== */
async function renderSkills(c) {
  c.innerHTML = loadingHtml('加载 Skill 资产…');
  const list = await api('/api/skills');
  cache.skills = list;
  let mcpList = [];
  try { mcpList = await api('/api/mcp'); } catch (e) { /* 台账拉取失败不阻塞 Skill 展示 */ }
  cache.mcp = mcpList;
  const scopes = ['公开', '组织', '个人'];
  const scopeMeta = { '公开': 'bg-success', '组织': 'bg-secondary', '个人': 'bg-accent' };
  const scopeEmpty = {
    '公开': '暂无公开 Skill',
    '组织': '暂无组织级 Skill，好用的团队话术可以沉淀到这里',
    '个人': '还没有个人技能，把你常用的 AI 话术沉淀到这里',
  };
  let html = '<div class="flex items-center justify-between mb-4 flex-wrap gap-2">' +
    '<div class="text-sm text-gray-500">共 ' + list.length + ' 个 Skill · 可被数字员工引用复用</div>' +
    '<button class="btn-primary !bg-accent hover:!bg-accent/90" onclick="openSkillModal()">+ 新建 Skill</button></div>';
  scopes.forEach(function (sc) {
    const items = list.filter(function (s) { return s.scope === sc; });
    html += '<div class="mb-6"><div class="flex items-center space-x-2 mb-3">' +
      '<span class="badge ' + scopeMeta[sc] + '">' + sc + '</span>' +
      '<span class="text-sm text-gray-500">共 ' + items.length + ' 个 Skill</span></div>';
    if (!items.length) html += '<div class="data-card">' + emptyHtml(scopeEmpty[sc] || '该范围暂无 Skill') + '</div>';
    else {
      html += '<div class="grid grid-cols-2 xl:grid-cols-4 gap-3">' + items.map(function (s) {
        return '<div class="data-card !p-4 card-hover">' +
          '<div class="flex items-center justify-between mb-1.5"><span class="font-bold text-primary text-sm truncate">' + esc(s.name) + '</span>' +
          '<span class="badge badge-outline shrink-0 ml-1">' + esc(s.category || '-') + '</span></div>' +
          '<div class="text-xs text-gray-500 leading-relaxed" style="min-height:2.4em">' + esc(s.description || '') + '</div>' +
          '<div class="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">' +
            '<span class="text-xs text-gray-400">Owner：' + esc(s.owner_name || '-') + '</span>' +
            (canAdmin()
              ? '<span class="flex space-x-1.5 shrink-0">' +
                '<button class="btn-ghost !py-0.5 !px-2 !text-xs" onclick="openSkillEditModal(' + s.id + ')">编辑</button>' +
                '<button class="btn-danger-sm !py-0.5 !px-2 !text-xs" onclick="openSkillDelete(' + s.id + ')">删除</button></span>'
              : '') + '</div></div>';
      }).join('') + '</div>';
    }
    html += '</div>';
  });
  /* R4-2：MCP 服务台账分区 */
  html += '<div class="mb-2 mt-8 flex items-center justify-between flex-wrap gap-2">' +
    '<div class="flex items-center space-x-2"><span class="badge bg-teal">MCP 服务</span>' +
    '<span class="text-sm text-gray-500">数字员工可调用的外部系统接口台账，共 ' + mcpList.length + ' 个</span></div>' +
    (canAdmin() ? '<button class="btn-primary" onclick="openMcpModal()">+ 新增 MCP</button>' : '') + '</div>';
  if (!mcpList.length) html += '<div class="data-card">' + emptyHtml('暂无 MCP 服务，高管/教练团可点击右上角登记') + '</div>';
  else {
    html += '<div class="data-card !p-0 overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
      '<th>名称</th><th>接入点</th><th>说明</th><th>状态</th>' + (canAdmin() ? '<th>操作</th>' : '') + '</tr></thead><tbody>' +
      mcpList.map(function (m) {
        return '<tr><td class="font-medium whitespace-nowrap">' + esc(m.name) + '</td>' +
          '<td class="font-mono text-xs text-gray-500">' + esc(m.endpoint || '-') + '</td>' +
          '<td class="text-xs text-gray-500 max-w-md">' + esc(m.description || '-') + '</td>' +
          '<td>' + statusBadge(m.status, { '启用': 'bg-success', '停用': 'bg-gray-400' }) + '</td>' +
          (canAdmin()
            ? '<td class="whitespace-nowrap"><button class="btn-ghost !py-0.5 !px-2 !text-xs" onclick="toggleMcp(' + m.id + ',' + esc(jsStr(m.status)) + ')">' +
              (m.status === '启用' ? '停用' : '启用') + '</button></td>'
            : '') + '</tr>';
      }).join('') + '</tbody></table></div>';
  }
  c.innerHTML = html;
}
/* Skill 新建 / 编辑弹窗（编辑仅 boss/coach 可见入口，后端同样鉴权） */
function openSkillEditModal(id) {
  const s = (cache.skills || []).find(function (x) { return x.id === id; });
  if (!s) { toast('未找到该 Skill，请刷新后重试', 'error'); return; }
  openSkillModal(s);
}
function openSkillModal(s) {
  const editing = !!(s && s.id);
  openModal('<h3 class="font-bold text-primary text-lg mb-4">' + (editing ? '编辑 Skill' : '新建 Skill') + '</h3>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">名称 *</label><input id="sk-name" class="form-input" placeholder="如：信用证审单" value="' + esc(editing ? s.name : '') + '"></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">分类</label><input id="sk-category" class="form-input" placeholder="如：外贸" value="' + esc(editing ? (s.category || '') : '') + '"></div>' +
        '<div><label class="form-label">范围</label><select id="sk-scope" class="form-select">' +
          ['公开', '组织', '个人'].map(function (x) {
            return '<option' + (editing && s.scope === x ? ' selected' : (!editing && x === '组织' ? ' selected' : '')) + '>' + x + '</option>';
          }).join('') + '</select></div></div>' +
      '<div><label class="form-label">说明</label><textarea id="sk-desc" class="form-textarea" rows="3" placeholder="这个 Skill 怎么用、适合什么场景">' + esc(editing ? (s.description || '') : '') + '</textarea></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="sk-submit" onclick="submitSkill(' + (editing ? s.id : 0) + ')">' + (editing ? '保存修改' : '创建') + '</button></div>');
}
async function submitSkill(id) {
  const body = {
    name: document.getElementById('sk-name').value.trim(),
    category: document.getElementById('sk-category').value.trim(),
    scope: document.getElementById('sk-scope').value,
    description: document.getElementById('sk-desc').value.trim(),
  };
  if (!body.name) { toast('请填写 Skill 名称', 'error'); return; }
  await withBusy(document.getElementById('sk-submit'), async function () {
    try {
      if (id) { await patchApi('/api/skills/' + id, body); toast('Skill 已更新'); }
      else { await postApi('/api/skills', body); toast('Skill 已创建'); }
      closeModal();
      renderSkills(document.getElementById('view-container'));
    } catch (e) { toast(e.message, 'error'); }
  });
}
function openSkillDelete(id) {
  const s = (cache.skills || []).find(function (x) { return x.id === id; });
  const name = s ? s.name : ('#' + id);
  openModal('<h3 class="font-bold text-primary text-lg mb-1">删除 Skill</h3>' +
    '<p class="text-sm text-gray-600 mb-1">确定删除「<b>' + esc(name) + '</b>」吗？删除后数字员工技能标签中的同名标签不受影响，但无法再被新引用。</p>' +
    '<p class="text-xs text-gray-400">该操作会写入审计日志。</p>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-danger-sm !px-5 !py-2" id="sk-del-submit" onclick="submitSkillDelete(' + id + ')">确认删除</button></div>');
}
async function submitSkillDelete(id) {
  await withBusy(document.getElementById('sk-del-submit'), async function () {
    try {
      await delApi('/api/skills/' + id);
      closeModal();
      toast('Skill 已删除');
      renderSkills(document.getElementById('view-container'));
    } catch (e) { toast(e.message, 'error'); }
  });
}
/* MCP 台账：新增 / 启停 */
function openMcpModal() {
  openModal('<h3 class="font-bold text-primary text-lg mb-4">新增 MCP 服务</h3>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">名称 *</label><input id="mc-name" class="form-input" placeholder="如：ERP只读接口"></div>' +
      '<div><label class="form-label">接入点 *</label><input id="mc-endpoint" class="form-input font-mono" placeholder="如：mcp://erp.internal/read"></div>' +
      '<div><label class="form-label">说明</label><textarea id="mc-desc" class="form-textarea" rows="2" placeholder="能提供什么数据/能力，有什么使用限制"></textarea></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="mc-submit" onclick="submitMcp()">登记</button></div>');
}
async function submitMcp() {
  const body = {
    name: document.getElementById('mc-name').value.trim(),
    endpoint: document.getElementById('mc-endpoint').value.trim(),
    description: document.getElementById('mc-desc').value.trim(),
  };
  if (!body.name || !body.endpoint) { toast('请填写名称与接入点', 'error'); return; }
  await withBusy(document.getElementById('mc-submit'), async function () {
    try {
      await postApi('/api/mcp', body);
      closeModal();
      toast('MCP 服务已登记（默认停用，确认可用后再启用）');
      renderSkills(document.getElementById('view-container'));
    } catch (e) { toast(e.message, 'error'); }
  });
}
async function toggleMcp(id, current) {
  const next = current === '启用' ? '停用' : '启用';
  try {
    await patchApi('/api/mcp/' + id, { status: next });
    toast('已' + next + '该 MCP 服务');
    renderSkills(document.getElementById('view-container'));
  } catch (e) { toast(e.message, 'error'); }
}

/* ==================== 视图 7：知识库 ==================== */
async function renderKnowledge(c) {
  c.innerHTML = loadingHtml('加载 NAS 空间…');
  const loaded = await Promise.all([
    api('/api/knowledge/spaces'),
    api('/api/knowledge/business-data?limit=8').catch(function () { return null; }),
  ]);
  const spaces = loaded[0];
  const business = loaded[1];
  if (!knState.spaceId || !spaces.some(function (s) { return s.id === knState.spaceId; })) {
    knState.spaceId = spaces.length ? spaces[0].id : null;
  }
  let html = '';
  if (business) {
    const allCount = (business.summary || []).reduce(function (sum, item) { return sum + (item.count || 0); }, 0);
    html += '<div class="data-card mb-5 bg-gradient-to-r from-secondary/5 to-teal/5">' +
      '<div class="flex flex-wrap items-center justify-between gap-3 mb-3">' +
        '<div><div class="font-bold text-primary">制造业务展示数据</div>' +
        '<div class="text-xs text-gray-500 mt-0.5">每次部署自动补齐，可直接用于筛选、统计和数字员工连续问答</div></div>' +
        '<div class="flex items-center gap-2"><span class="text-2xl font-black text-secondary">' + fmtNum(allCount) + '</span>' +
        '<span class="text-xs text-gray-400">条</span><button class="btn-primary !py-1.5" onclick="openBusinessDataModal()">查看数据</button></div></div>' +
      '<div class="flex flex-wrap gap-2">' + (business.summary || []).map(function (item) {
        return '<span class="badge bg-teal">' + esc(item.business_type) + ' ' + item.count + ' 条</span>';
      }).join('') + '</div></div>';
  }
  html += '<div class="grid grid-cols-2 xl:grid-cols-3 gap-4 mb-5">';
  spaces.forEach(function (s) {
    const active = s.id === knState.spaceId;
    html += '<div class="data-card card-hover cursor-pointer ' + (active ? 'ring-2 ring-secondary' : '') + '" onclick="selectSpace(' + s.id + ')">' +
      '<div class="flex items-center justify-between mb-1">' +
        '<span class="font-bold text-primary">' + esc(s.name) + '</span>' +
        '<span class="badge bg-teal">' + (s.doc_count ?? 0) + ' 文档</span></div>' +
      '<div class="text-xs text-gray-500 space-y-0.5">' +
        '<div>设备：' + esc(s.device || NAS_DEFAULT_DEVICE) + ' · 容量 ' + esc(s.capacity || '-') + '</div>' +
        '<div>所属：' + esc(s.dept_name || '-') + ' · 领域：' + esc(s.domain || '-') + '</div></div></div>';
  });
  html += '</div>';
  html += '<div class="data-card"><div class="flex items-center justify-between mb-3 flex-wrap gap-2">' +
    '<h3 class="font-bold text-primary">空间文档</h3>' +
    '<div class="flex space-x-2">' +
      (canUploadDoc() ? '<button class="btn-primary !bg-teal hover:!bg-teal/90" onclick="openUploadModal()">⇪ 上传文档</button>' : '') +
      '<button class="btn-primary" onclick="openDocModal()">+ 登记文档</button></div></div>' +
    '<div id="docs-box">' + loadingHtml() + '</div></div>';
  c.innerHTML = html;
  await loadSpaceDocs();
}
async function selectSpace(id) {
  knState.spaceId = id;
  await renderKnowledge(document.getElementById('view-container'));
}
/* R4-3：转换产物格式徽章（md/sqlite/html 三色） */
const DOC_FORMAT_META = {
  md:     { cls: 'bg-success',   label: '.md' },
  sqlite: { cls: 'bg-secondary', label: '.sqlite' },
  'sqlite+csv': { cls: 'bg-secondary', label: 'SQLite + CSV' },
  html:   { cls: 'bg-accent',    label: '.html' },
};
function docFormatBadge(d) {
  const m = DOC_FORMAT_META[d.converted_format];
  if (!m) return '<span class="text-xs text-gray-300">—</span>';
  return '<span class="badge ' + m.cls + '">' + m.label + '</span>';
}
async function loadSpaceDocs() {
  const box = document.getElementById('docs-box');
  if (!box) return;
  const docs = await api('/api/knowledge/documents?space_id=' + knState.spaceId);
  if (!docs.length) { box.innerHTML = emptyHtml('这个资料柜还是空的，点右上角「上传文档」或「登记文档」把公司文件放进来'); return; }
  box.innerHTML = '<div class="overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
    '<th>标题</th><th>密级</th><th>格式</th><th>块数</th><th>标签</th><th>上传人</th><th>时间</th></tr></thead><tbody>' +
    docs.map(function (d) {
      return '<tr class="cursor-pointer" onclick="openDocDetail(' + d.id + ')" title="点击查看解析详情">' +
        '<td class="font-medium">' + esc(d.title) + '</td>' +
        '<td><span class="badge ' + (LEVEL_META[d.level] || 'bg-gray-400') + '">' + esc(d.level) + '</span></td>' +
        '<td>' + docFormatBadge(d) + '</td>' +
        '<td class="whitespace-nowrap">' + (d.chunk_count ? '<b class="text-secondary">' + d.chunk_count + '</b> 块' : '<span class="text-xs text-gray-300">—</span>') + '</td>' +
        '<td class="text-xs text-gray-500">' + esc(d.tags || '-') + '</td>' +
        '<td class="whitespace-nowrap">' + esc(d.uploaded_by || '-') + '</td>' +
        '<td class="whitespace-nowrap">' + fmtTime(d.created_at) + '</td></tr>';
    }).join('') + '</tbody></table></div>';
}
/* 上传文档：选文件 + 密级 + 标签，FormData 提交 */
function openUploadModal() {
  openModal('<h3 class="font-bold text-primary text-lg mb-1">上传文档到本空间</h3>' +
    '<p class="text-xs text-gray-500 mb-3">支持 txt / md / docx / pdf / Excel / csv / json / html。Excel 会按工作表写入 SQLite，并逐表生成 CSV。</p>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">选择文件 *</label><input id="up-file" type="file" class="form-input !py-2" accept=".txt,.md,.docx,.pdf,.xlsx,.xls,.csv,.json,.html,.htm"></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">密级</label><select id="up-level" class="form-select"><option>L1</option><option>L2</option><option selected>L3</option><option>L4</option></select></div>' +
        '<div><label class="form-label">标签（逗号分隔）</label><input id="up-tags" class="form-input" placeholder="模板,单证"></div></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="up-submit" onclick="submitUpload()">上传并解析</button></div>');
}
async function submitUpload() {
  const fi = document.getElementById('up-file');
  if (!fi.files || !fi.files.length) { toast('请先选择文件', 'error'); return; }
  const fd = new FormData();
  fd.append('file', fi.files[0]);
  fd.append('level', document.getElementById('up-level').value);
  fd.append('tags', document.getElementById('up-tags').value.trim());
  const btn = document.getElementById('up-submit');
  btn.disabled = true;
  btn.textContent = '上传解析中…';
  try {
    const r = await uploadApi('/api/knowledge/spaces/' + knState.spaceId + '/upload', fd);
    closeModal();
    toast('上传成功：已转换为 ' + (r.converted_format || '?') + '，拆分 ' + (r.chunk_count ?? 0) + ' 块');
    await renderKnowledge(document.getElementById('view-container'));
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '上传并解析';
    toast(e.message, 'error');
  }
}
/* 文档详情弹窗：summary + chunks 预览 + 下载转换产物 */
async function openDocDetail(id) {
  openModal(loadingHtml('加载文档解析…'));
  try {
    const d = await api('/api/knowledge/documents/' + id);
    const chunks = d.chunks || [];
    let html = '<div class="flex items-start justify-between mb-2"><h3 class="font-bold text-primary text-lg">' + esc(d.title) + '</h3>' +
      '<span class="flex items-center gap-1.5 shrink-0">' + docFormatBadge(d) +
      '<span class="badge ' + (LEVEL_META[d.level] || 'bg-gray-400') + '">' + esc(d.level) + '</span></span></div>' +
      '<div class="text-xs text-gray-400 mb-3">' + esc(d.space_name || '') + ' · ' + esc(d.uploaded_by || '-') + ' · ' + fmtTime(d.created_at) +
      (d.tags ? ' · 标签：' + esc(d.tags) : '') + '</div>';
    if (d.summary) {
      html += '<div class="mb-3"><div class="text-xs font-bold text-gray-500 mb-1">内容摘要</div>' +
        '<div class="bg-gray-50 rounded-lg p-3 text-sm text-gray-700 leading-relaxed">' + esc(d.summary) + '</div></div>';
    }
    if (chunks.length) {
      html += '<div class="mb-3"><div class="text-xs font-bold text-gray-500 mb-1.5">分块预览（' + chunks.length + ' 块）</div>' +
        '<div class="space-y-2 max-h-64 overflow-y-auto pr-1">' + chunks.map(function (ck) {
          return '<div class="border border-gray-100 rounded-lg p-2.5">' +
            '<div class="flex items-center gap-2 text-xs mb-1"><span class="badge badge-outline">#' + ck.seq + '</span>' +
            '<span class="font-bold text-secondary">' + esc(ck.heading || '（无标题）') + '</span></div>' +
            '<div class="text-xs text-gray-500 leading-relaxed">' + esc((ck.content || '').slice(0, 150)) + ((ck.content || '').length > 150 ? '…' : '') + '</div></div>';
        }).join('') + '</div></div>';
    } else {
      html += '<div class="text-xs text-gray-400 mb-3">本文档尚未解析分块（早期登记的文档仅作台账记录）。</div>';
    }
    const datasets = d.datasets || [];
    if (datasets.length) {
      html += '<div class="mb-3"><div class="flex items-center justify-between mb-1.5">' +
        '<div class="text-xs font-bold text-gray-500">结构化数据表（' + datasets.length + '）</div>' +
        '<button class="btn-ghost !py-1 !px-2 text-xs" onclick="downloadDatasetDb(' + d.id + ')">下载 SQLite</button></div>' +
        '<div class="space-y-1.5">' + datasets.map(function (ds) {
          return '<div class="flex flex-wrap items-center gap-2 border border-gray-100 rounded-lg px-3 py-2 text-xs">' +
            '<span class="font-bold text-secondary">' + esc(ds.sheet_name) + '</span>' +
            '<code class="text-gray-400">' + esc(ds.table_name) + '</code>' +
            '<span>' + ds.row_count + ' 行 × ' + ds.column_count + ' 列</span><span class="flex-1"></span>' +
            '<button class="btn-ghost !py-1 !px-2 text-xs" onclick="previewDocDataset(' + d.id + ',' + esc(jsStr(ds.table_name)) + ')">预览</button>' +
            (d.converted_format === 'sqlite+csv'
              ? '<button class="btn-ghost !py-1 !px-2 text-xs" onclick="downloadDatasetCsv(' + d.id + ',' + esc(jsStr(ds.table_name)) + ')">CSV</button>'
              : '') + '</div>';
        }).join('') + '</div></div>';
    }
    html += '<div class="flex justify-end space-x-2 mt-2">' +
      '<button class="btn-ghost" onclick="closeModal()">关闭</button>' +
      (d.converted_format
        ? '<button class="btn-primary" onclick="downloadDocFile(' + d.id + ',' + esc(jsStr(d.converted_format)) + ')">下载转换产物</button>'
        : '') + '</div>';
    openModal(html);
  } catch (e) { openModal(errorHtml(e.message)); }
}
/* 带鉴权下载统一入口：fetch→blob→a 标签触发；appendChild 挂载 + 延时 revoke/remove 兼容 Firefox */
async function downloadBlob(url, filename) {
  const res = await fetch(url, {
    headers: state.token ? { 'Authorization': 'Bearer ' + state.token } : {},
  });
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (e) { /* 非 JSON */ }
    throw new Error((data && data.detail) || ('下载失败（HTTP ' + res.status + '）'));
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(function () { URL.revokeObjectURL(objectUrl); a.remove(); }, 3000);
}
/* 下载转换产物：接口需带 token，走 fetch→blob→本地下载 */
async function downloadDocFile(id, format) {
  const ext = { md: '.md', html: '.html', sqlite: '.md', 'sqlite+csv': '.md' }[format] || '.txt';
  try {
    await downloadBlob('/api/knowledge/documents/' + id + '/file', 'document_' + id + ext);
    toast('转换产物已开始下载');
  } catch (e) { toast(e.message, 'error'); }
}
async function downloadDatasetDb(id) {
  try {
    await downloadBlob('/api/knowledge/documents/' + id + '/database', 'document_' + id + '.db');
    toast('SQLite 数据库已开始下载');
  } catch (e) { toast(e.message, 'error'); }
}
async function downloadDatasetCsv(id, tableName) {
  try {
    await downloadBlob('/api/knowledge/documents/' + id + '/datasets/' + encodeURIComponent(tableName) + '/csv', tableName + '.csv');
    toast('CSV 已开始下载');
  } catch (e) { toast(e.message, 'error'); }
}
async function previewDocDataset(id, tableName) {
  openModal(loadingHtml('加载数据表…'));
  try {
    const data = await api('/api/knowledge/documents/' + id + '/datasets/' + encodeURIComponent(tableName) + '?limit=30');
    const columns = (data.columns || []).slice(0, 12);
    openModal('<h3 class="font-bold text-primary text-lg mb-1">' + esc(tableName) + '</h3>' +
      '<div class="text-xs text-gray-400 mb-3">共 ' + data.total + ' 行；当前预览前 ' + (data.rows || []).length +
      ' 行、最多 12 列</div>' +
      '<div class="overflow-auto max-h-[60vh]"><table class="gov-table w-full"><thead><tr>' +
      columns.map(function (col) { return '<th class="whitespace-nowrap">' + esc(col) + '</th>'; }).join('') +
      '</tr></thead><tbody>' + (data.rows || []).map(function (row) {
        return '<tr>' + columns.map(function (col) {
          return '<td class="whitespace-nowrap max-w-48 truncate" title="' + esc(row[col]) + '">' + esc(row[col]) + '</td>';
        }).join('') + '</tr>';
      }).join('') + '</tbody></table></div>' +
      '<div class="flex justify-end mt-3"><button class="btn-ghost" onclick="closeModal()">关闭</button></div>');
  } catch (e) { openModal(errorHtml(e.message)); }
}
async function openBusinessDataModal() {
  openModal(loadingHtml('加载 1000 条业务展示数据…'));
  try {
    const data = await api('/api/knowledge/business-data?limit=50');
    const rows = data.items || [];
    openModal('<div class="flex items-start justify-between mb-3"><div><h3 class="font-bold text-primary text-lg">制造业务展示数据</h3>' +
      '<div class="text-xs text-gray-400">系统默认共 ' + data.total + ' 条，数字员工对话会自动召回相关明细</div></div>' +
      '<button class="text-gray-400 text-xl" onclick="closeModal()">×</button></div>' +
      '<div class="overflow-auto max-h-[65vh]"><table class="gov-table w-full"><thead><tr>' +
      '<th>编号</th><th>日期</th><th>类型</th><th>客户</th><th>产品</th><th>数量</th><th>金额</th><th>状态</th><th>指标</th>' +
      '</tr></thead><tbody>' + rows.map(function (r) {
        return '<tr><td class="font-mono whitespace-nowrap">' + esc(r.record_no) + '</td>' +
          '<td class="whitespace-nowrap">' + esc(r.business_date) + '</td><td>' + esc(r.business_type) + '</td>' +
          '<td class="whitespace-nowrap">' + esc(r.customer) + '</td><td class="whitespace-nowrap">' + esc(r.product_code) + ' ' + esc(r.product_name) + '</td>' +
          '<td>' + fmtNum(r.quantity) + '</td><td>¥' + fmtNum(r.amount) + '</td><td class="whitespace-nowrap">' + esc(r.status) + '</td>' +
          '<td class="whitespace-nowrap">' + esc(r.metric_name) + ' ' + esc(r.metric_value) + '</td></tr>';
      }).join('') + '</tbody></table></div>' +
      '<div class="text-xs text-gray-400 mt-2">当前展示最近 50 条；API 支持按业务类型、关键词和分页查询。</div>');
  } catch (e) { openModal(errorHtml(e.message)); }
}
function openDocModal() {
  openModal('<h3 class="font-bold text-primary text-lg mb-4">登记文档</h3>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">文档标题 *</label><input id="nd-title" class="form-input" placeholder="如：外贸单证模板库"></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">密级</label><select id="nd-level" class="form-select"><option>L1</option><option>L2</option><option selected>L3</option><option>L4</option></select></div>' +
        '<div><label class="form-label">标签（逗号分隔）</label><input id="nd-tags" class="form-input" placeholder="模板,单证"></div></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="nd-submit" onclick="submitDoc()">登记</button></div>');
}
async function submitDoc() {
  const title = document.getElementById('nd-title').value.trim();
  if (!title) { toast('请填写文档标题', 'error'); return; }
  await withBusy(document.getElementById('nd-submit'), async function () {
    try {
      await postApi('/api/knowledge/documents', {
        space_id: knState.spaceId,
        title: title,
        level: document.getElementById('nd-level').value,
        tags: document.getElementById('nd-tags').value.trim(),
      });
      closeModal();
      toast('文档登记成功');
      await renderKnowledge(document.getElementById('view-container'));
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* ==================== 视图 8：组织通讯录 ==================== */
async function renderOrg(c) {
  c.innerHTML = loadingHtml('加载组织树…');
  const tree = await api('/api/org/tree');
  let peopleMetrics = [];
  if (canReview()) {
    try { peopleMetrics = await api('/api/metrics/people'); } catch (e) { peopleMetrics = []; }
  }
  let html = '<div class="data-card !py-3 mb-4 flex items-center space-x-3 bg-gradient-to-r from-primary/5 to-teal/5">' +
    '<svg class="w-6 h-6 text-teal shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' +
    '<div class="text-sm text-gray-600">Teams.md 理念：<b class="text-primary">AI 通过通讯录理解组织</b>，调度人与数字员工协同作战——五个业务平台、部门与数字员工在此一图总览。</div></div>';
  if (peopleMetrics.length) {
    const active = peopleMetrics.filter(function (p) { return p.last_active; }).length;
    const totalTasks = peopleMetrics.reduce(function (n, p) { return n + (p.tasks_created || 0); }, 0);
    html += '<div class="data-card mb-4"><div class="flex items-center justify-between mb-3">' +
      '<div><div class="font-bold text-primary">个人 AI 使用成效</div>' +
      '<div class="text-xs text-gray-400">供 HR/管理层识别活跃度、产出与待跟进人员</div></div>' +
      '<div class="flex gap-2"><span class="badge bg-secondary">有使用记录 ' + active + ' 人</span>' +
      '<span class="badge bg-teal">累计发起 ' + totalTasks + ' 项</span></div></div>' +
      '<div class="overflow-x-auto max-h-72 overflow-y-auto"><table class="gov-table w-full"><thead><tr>' +
      '<th>人员</th><th>部门/角色</th><th>发起任务</th><th>已通过</th><th>待处理</th><th>最近活跃</th></tr></thead><tbody>' +
      peopleMetrics.map(function (p) {
        return '<tr><td class="font-medium whitespace-nowrap">' + esc(p.name) + '</td>' +
          '<td>' + esc(p.dept_name || '-') + ' · ' + esc((TIER_META[p.tier] || {}).label || p.tier) + '</td>' +
          '<td>' + (p.tasks_created || 0) + '</td><td class="text-success">' + (p.tasks_approved || 0) + '</td>' +
          '<td class="' + ((p.tasks_open || 0) ? 'text-accent font-bold' : '') + '">' + (p.tasks_open || 0) + '</td>' +
          '<td class="whitespace-nowrap">' + fmtTime(p.last_active) + '</td></tr>';
      }).join('') + '</tbody></table></div></div>';
  }
  tree.forEach(function (p) {
    let deptCount = (p.departments || []).length;
    let agentCount = 0, peopleCount = 0;
    (p.departments || []).forEach(function (d) {
      agentCount += (d.agents || []).length;
      peopleCount += (d.people || []).length;
    });
    /* 默认全部展开（保留 summary 可手动收起），让各平台人员首屏可达 */
    html += '<details class="tree-platform data-card !p-0 mb-3" open><summary class="flex items-center space-x-3 px-4 py-3">' +
      '<span class="tree-arrow text-gray-400">▶</span>' +
      '<span class="w-3 h-3 rounded-full shrink-0" style="background:' + esc(p.color || '#2c5282') + '"></span>' +
      '<span class="font-bold text-primary">' + esc(p.name) + '</span>' +
      '<span class="badge badge-outline">' + esc(p.code || '') + '</span>' +
      '<span class="text-xs text-gray-400">编制 ' + (p.headcount ?? '-') + ' 人 · ' + deptCount + ' 部门 · ' + peopleCount + ' 人员 · ' + agentCount + ' 数字员工</span></summary>' +
      '<div class="px-4 pb-4 space-y-3">';
    (p.departments || []).forEach(function (d) {
      html += '<div class="border border-gray-100 rounded-lg p-3">' +
        '<div class="text-sm font-bold text-secondary mb-2">' + esc(d.name) + '</div>' +
        '<div class="flex flex-wrap gap-1.5 mb-2">';
      (d.people || []).forEach(function (pp) {
        html += '<span class="inline-flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-full px-2.5 py-1 text-xs">' +
          '<b>' + esc(pp.name) + '</b><span class="text-gray-400">' + esc(pp.role_title || '') + '</span>' + tierBadge(pp.tier) +
          (pp.direction ? '<span class="text-gray-400">· ' + esc(pp.direction) + '</span>' : '') + '</span>';
      });
      html += '</div>';
      if ((d.agents || []).length) {
        html += '<div class="flex flex-wrap gap-1.5">';
        d.agents.forEach(function (a) {
          html += '<span class="inline-flex items-center gap-1 bg-teal/5 border border-teal/20 rounded-lg px-2 py-1 text-xs cursor-pointer hover:bg-teal/10" onclick="openAgentDrawer(' + a.id + ')" title="点击查看档案">' +
            '<svg class="w-3.5 h-3.5 text-teal" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2v3M5 8h14a1 1 0 011 1v9a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zM9 13v2M15 13v2"/></svg>' +
            '<span class="text-gray-700">' + esc(a.name) + '</span>' + statusBadge(a.status, AGENT_STATUS_META) + '</span>';
        });
        html += '</div>';
      }
      html += '</div>';
    });
    html += '</div></details>';
  });
  c.innerHTML = html;
}

/* ==================== 视图 9：治理中心 ==================== */
const GOV_TABS = [
  { key: 'incentives', name: '立项与激励' },
  { key: 'reimbursements', name: 'AI 算力费用报销（Token）' },
  { key: 'audits', name: '审计日志' },
  { key: 'redlines', name: '开发红线' },
];
function availableGovTabs() {
  if (!state.person) return [];
  if (['boss', 'coach', 'backbone'].indexOf(state.person.tier) >= 0) return GOV_TABS;
  return GOV_TABS.filter(function (t) { return t.key !== 'audits'; });
}
/* 当前登录人是否可对本单本级审批（与后端分权规则一致，用于角标与按钮禁用） */
function reimbActionable(r) {
  if (!state.person || r.status === '已完成' || r.status === '已驳回') return false;
  const tier = state.person.tier;
  if (r.step === 1 || r.status === '待平台长审批') return ['coach', 'backbone', 'boss'].indexOf(tier) >= 0;
  if (r.step === 2 || r.status === '待数字化复核') return tier === 'coach';
  if (r.step === 3 || r.status === '待财务报销') {
    return (tier === 'backbone' || tier === 'boss') && (state.person.dept_name || '').indexOf('财务') >= 0;
  }
  return false;
}
function reimbWaitTip(r) {
  if (r.status === '待平台长审批') return '此单待平台长审批（需教练团/业务骨干/高管操作）';
  if (r.status === '待数字化复核') return '此单待数字化平台长复核（仅教练团可操作）';
  if (r.status === '待财务报销') return '此单待财务报销（仅财务部骨干/高管可操作）';
  return '当前状态不可审批';
}
async function renderGovernance(c) {
  const tabs = availableGovTabs();
  /* 支持深链 #/governance/<tab> */
  const sub = (location.hash || '').replace(/^#\/?/, '').split('/')[1];
  if (sub && tabs.some(function (t) { return t.key === sub; })) govState.tab = sub;
  if (!tabs.some(function (t) { return t.key === govState.tab; })) govState.tab = tabs[0].key;
  let pendCount = 0;
  try {
    const rl = await api('/api/governance/reimbursements');
    pendCount = rl.filter(reimbActionable).length;
  } catch (e) { /* 角标失败不阻塞页面 */ }
  c.innerHTML = '<div class="data-card !p-0">' +
    '<div class="flex px-4 pt-3 border-b border-gray-100 space-x-1 flex-wrap">' +
    tabs.map(function (t) {
      return '<div class="zone-tab ' + (govState.tab === t.key ? 'active' : '') + '" onclick="switchGovTab(' + esc(jsStr(t.key)) + ')">' + t.name +
        (t.key === 'reimbursements' && pendCount > 0 ? ' <span class="badge bg-danger">' + pendCount + '</span>' : '') + '</div>';
    }).join('') + '</div>' +
    '<div id="gov-body" class="p-4">' + loadingHtml() + '</div></div>';
  await loadGovTab();
}
async function switchGovTab(tab) {
  const tabs = availableGovTabs();
  if (!tabs.some(function (t) { return t.key === tab; })) return;
  govState.tab = tab;
  document.querySelectorAll('#view-container .zone-tab').forEach(function (el, i) {
    el.classList.toggle('active', tabs[i].key === tab);
  });
  document.getElementById('gov-body').innerHTML = loadingHtml();
  await loadGovTab();
}
async function loadGovTab() {
  const box = document.getElementById('gov-body');
  if (!box) return;
  try {
    if (govState.tab === 'incentives') await renderIncentives(box);
    else if (govState.tab === 'reimbursements') await renderReimbursements(box);
    else if (govState.tab === 'audits') await renderAudits(box);
    else await renderRedlines(box);
  } catch (e) { box.innerHTML = errorHtml(e.message); }
}
async function renderIncentives(box) {
  const result = await Promise.all([
    api('/api/governance/incentives'),
    api('/api/governance/incentives/summary'),
  ]);
  const list = result[0], summary = result[1];
  let html = '<div class="grid grid-cols-3 gap-3 mb-3">' +
    '<div class="bg-gray-50 rounded-lg p-3"><div class="text-xs text-gray-500">年度激励池</div><div class="text-xl font-black text-primary">¥' + fmtNum(summary.pool) + '</div></div>' +
    '<div class="bg-gray-50 rounded-lg p-3"><div class="text-xs text-gray-500">已申报/占用</div><div class="text-xl font-black text-accent">¥' + fmtNum(summary.committed) + '</div></div>' +
    '<div class="' + (summary.over_budget ? 'bg-red-50' : 'bg-green-50') + ' rounded-lg p-3"><div class="text-xs text-gray-500">可用余量</div><div class="text-xl font-black ' +
      (summary.over_budget ? 'text-danger' : 'text-success') + '">¥' + fmtNum(summary.remaining) + '</div></div></div>' +
    '<div class="flex justify-end mb-3"><button class="btn-primary" onclick="openIncentiveModal()">+ 申报激励</button></div>';
  if (!list.length) html += emptyHtml('暂无激励申报');
  else {
    html += '<div class="overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
      '<th>奖项</th><th>申报人/候选人</th><th>理由</th><th>金额</th><th>状态</th><th>时间</th><th>操作</th></tr></thead><tbody>' +
      list.map(function (x) {
        return '<tr><td><span class="badge ' + (INCENTIVE_META[x.type] || 'bg-gray-400') + '">' + esc(x.type) + '</span></td>' +
          '<td class="whitespace-nowrap font-medium">' + esc(x.nominee) + '</td>' +
          '<td class="max-w-md">' + esc(x.reason || '-') + '</td>' +
          '<td class="whitespace-nowrap font-bold text-accent">¥' + fmtNum(x.amount) + '</td>' +
          '<td>' + statusBadge(x.status, { '申报中': 'bg-accent', '已评定': 'bg-secondary', '已发放': 'bg-success', '已驳回': 'bg-danger' }) +
            (x.review_comment ? '<div class="text-xs text-gray-400 mt-1">' + esc(x.review_comment) + '</div>' : '') + '</td>' +
          '<td class="whitespace-nowrap">' + fmtTime(x.created_at) + '</td>' +
          '<td class="whitespace-nowrap">' + incentiveActions(x) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  box.innerHTML = html;
}
function incentiveActions(x) {
  if (!state.person || ['boss', 'coach'].indexOf(state.person.tier) < 0) return '<span class="text-gray-300">—</span>';
  if (x.status === '申报中') {
    return '<button class="btn-success-sm" onclick="openIncentiveReviewModal(' + x.id + ',\'approve\')">评定</button> ' +
      '<button class="btn-danger-sm" onclick="openIncentiveReviewModal(' + x.id + ',\'reject\')">驳回</button>';
  }
  if (x.status === '已评定') {
    return '<button class="btn-success-sm" onclick="openIncentiveReviewModal(' + x.id + ',\'release\')">确认发放</button>';
  }
  return '<span class="text-gray-300">—</span>';
}
const INCENTIVE_ACTION_LABEL = { approve: '评定通过', reject: '驳回', release: '确认发放' };
/* 激励审批意见：openModal 模态框（替代原生 window.prompt） */
function openIncentiveReviewModal(id, action) {
  const label = INCENTIVE_ACTION_LABEL[action] || action;
  openModal('<h3 class="font-bold text-primary text-lg mb-1">' + label + ' · 激励申报 #' + id + '</h3>' +
    '<label class="form-label">审批意见（可留空）</label>' +
    '<textarea id="ir-comment" class="form-textarea" rows="3" placeholder="请输入审批意见"></textarea>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" onclick="submitIncentiveReview(' + id + ',\'' + action + '\')">确认' + label + '</button></div>');
}
function submitIncentiveReview(id, action) {
  const comment = document.getElementById('ir-comment').value.trim();
  closeModal();
  reviewIncentive(id, action, comment);
}
async function reviewIncentive(id, action, comment) {
  try {
    await postApi('/api/governance/incentives/' + id + '/review', { action: action, comment: comment || '' });
    toast((INCENTIVE_ACTION_LABEL[action] || action) + '成功');
    renderIncentives(document.getElementById('gov-body'));
  } catch (e) { toast(e.message, 'error'); }
}
function updateIncentiveTierHint() {
  const sel = document.getElementById('ni-type');
  const hint = document.getElementById('ni-tier-hint');
  if (sel && hint) hint.textContent = INCENTIVE_TIER_HINT[sel.value] || '';
}
function openIncentiveModal() {
  openModal('<h3 class="font-bold text-primary text-lg mb-4">申报激励</h3>' +
    '<div class="space-y-3">' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">奖项类型</label><select id="ni-type" class="form-select" onchange="updateIncentiveTierHint()">' +
          ['火花奖', '银齿轮奖', '金扳手奖', '种子基金'].map(function (t) { return '<option>' + t + '</option>'; }).join('') + '</select></div>' +
        '<div><label class="form-label">金额（元）</label><input id="ni-amount" type="number" class="form-input" value="800" min="0">' +
          '<div id="ni-tier-hint" class="text-xs text-accent font-medium mt-1"></div></div></div>' +
      '<div><label class="form-label">申报人/候选人 *</label><input id="ni-nominee" class="form-input" placeholder="姓名"></div>' +
      '<div><label class="form-label">申报理由</label><textarea id="ni-reason" class="form-textarea" rows="3" placeholder="事迹与贡献说明"></textarea></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="ni-submit" onclick="submitIncentive()">提交申报</button></div>');
  updateIncentiveTierHint();
}
async function submitIncentive() {
  const body = {
    type: document.getElementById('ni-type').value,
    nominee: document.getElementById('ni-nominee').value.trim(),
    reason: document.getElementById('ni-reason').value.trim(),
    amount: Number(document.getElementById('ni-amount').value) || 0,
  };
  if (!body.nominee) { toast('请填写申报人', 'error'); return; }
  await withBusy(document.getElementById('ni-submit'), async function () {
    try {
      await postApi('/api/governance/incentives', body);
      closeModal(); toast('激励申报已提交');
      renderIncentives(document.getElementById('gov-body'));
    } catch (e) { toast(e.message, 'error'); }
  });
}
async function renderReimbursements(box) {
  const list = await api('/api/governance/reimbursements');
  let html = '<div class="flex justify-end mb-3"><button class="btn-primary" onclick="openReimbModal()">+ 申报算力费用</button></div>';
  if (!list.length) html += emptyHtml('暂无报销记录');
  else {
    html += '<div class="space-y-3">' + list.map(function (r) {
      const final = r.status === '已完成' || r.status === '已驳回';
      const actionable = !final && reimbActionable(r);
      const tip = reimbWaitTip(r);
      let steps = '<div class="step-flow mt-2">';
      REIMB_STEPS.forEach(function (name, i) {
        const stepNo = i + 1;
        let cls = '';
        if (r.status === '已驳回' && stepNo === r.step) cls = 'rejected';
        else if (r.status === '已完成' || stepNo < r.step) cls = 'done';
        else if (stepNo === r.step) cls = 'current';
        steps += '<div class="step-node"><div class="step-circle ' + cls + '">' + stepNo + '</div>' +
          '<div class="text-xs mt-1 ' + (cls === 'current' ? 'text-accent font-bold' : 'text-gray-500') + '">' + name + '</div></div>';
        if (i < REIMB_STEPS.length - 1) steps += '<div class="step-line ' + ((r.status === '已完成' || stepNo < r.step) ? 'done' : '') + '"></div>';
      });
      steps += '</div>';
      return '<div class="border border-gray-100 rounded-lg p-3.5">' +
        '<div class="flex items-center justify-between flex-wrap gap-2">' +
          '<div class="flex items-center space-x-2"><span class="font-bold text-primary">#' + r.id + ' ' + esc(r.applicant) + '</span>' +
            '<span class="badge badge-outline">' + esc(r.provider) + '</span>' + statusBadge(r.status, { '待平台长审批': 'bg-accent', '待数字化复核': 'bg-secondary', '待财务报销': 'bg-teal', '已完成': 'bg-success', '已驳回': 'bg-danger' }) + '</div>' +
          '<div class="text-sm text-gray-600">' + fmtNum(r.tokens) + ' tokens · <b class="text-accent">¥' + fmtNum(r.amount) + '</b> · ' + fmtTime(r.created_at) + '</div></div>' +
        steps +
        '<div class="flex justify-end space-x-2 mt-2">' +
          (actionable
            ? '<button class="btn-success-sm" onclick="approveReimb(' + r.id + ',\'approve\')">本级通过</button>' +
              '<button class="btn-danger-sm" onclick="openReimbReject(' + r.id + ')">驳回</button>'
            : (final ? '' :
              '<button class="btn-success-sm" disabled title="' + esc(tip) + '">本级通过</button>' +
              '<button class="btn-danger-sm" disabled title="' + esc(tip) + '">驳回</button>')) +
        '</div></div>';
    }).join('') + '</div>';
  }
  box.innerHTML = html;
}
function openReimbModal() {
  openModal('<h3 class="font-bold text-primary text-lg mb-4">申报 AI 算力费用报销（Token）</h3>' +
    '<div class="space-y-3">' +
      '<div><label class="form-label">服务商 *</label><input id="nr-provider" class="form-input" placeholder="如：智谱GLM"></div>' +
      '<div class="grid grid-cols-2 gap-3">' +
        '<div><label class="form-label">Token 用量</label><input id="nr-tokens" type="number" class="form-input" value="1200000" min="0"></div>' +
        '<div><label class="form-label">金额（元）</label><input id="nr-amount" type="number" class="form-input" value="360" min="0"></div></div>' +
    '</div>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-primary" id="nr-submit" onclick="submitReimb()">提交申报</button></div>');
}
async function submitReimb() {
  const body = {
    provider: document.getElementById('nr-provider').value.trim(),
    tokens: Number(document.getElementById('nr-tokens').value) || 0,
    amount: Number(document.getElementById('nr-amount').value) || 0,
  };
  if (!body.provider) { toast('请填写服务商', 'error'); return; }
  await withBusy(document.getElementById('nr-submit'), async function () {
    try {
      await postApi('/api/governance/reimbursements', body);
      closeModal(); toast('报销申报已提交，进入平台长审批');
      renderReimbursements(document.getElementById('gov-body'));
    } catch (e) { toast(e.message, 'error'); }
  });
}
async function approveReimb(id, action, comment) {
  try {
    const r = await postApi('/api/governance/reimbursements/' + id + '/approve', { action: action, comment: comment || '' });
    toast(action === 'approve' ? '已通过，当前状态：' + r.status : '已驳回该报销');
    renderReimbursements(document.getElementById('gov-body'));
  } catch (e) { toast(e.message, 'error'); }
}
function openReimbReject(id) {
  openModal('<h3 class="font-bold text-primary text-lg mb-3">驳回报销 #' + id + '</h3>' +
    '<label class="form-label">驳回原因</label>' +
    '<textarea id="rr-comment" class="form-textarea" rows="3" placeholder="请说明驳回原因"></textarea>' +
    '<div class="flex justify-end space-x-2 mt-4">' +
      '<button class="btn-ghost" onclick="closeModal()">取消</button>' +
      '<button class="btn-danger-sm !px-5 !py-2" onclick="submitReimbReject(' + id + ')">确认驳回</button></div>');
}
function submitReimbReject(id) {
  const comment = document.getElementById('rr-comment').value.trim();
  if (!comment) { toast('请填写驳回原因', 'error'); return; }
  closeModal();
  approveReimb(id, 'reject', comment);
}
async function renderAudits(box) {
  const list = await api('/api/governance/audits');
  if (!list.length) { box.innerHTML = emptyHtml('暂无审计日志'); return; }
  box.innerHTML = (canAdmin()
    ? '<div class="flex justify-end mb-3"><button class="btn-ghost" onclick="downloadAuditCsv()">导出 CSV</button></div>'
    : '') + '<div class="overflow-x-auto max-h-[60vh] overflow-y-auto"><table class="gov-table w-full"><thead><tr>' +
    '<th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>详情</th></tr></thead><tbody>' +
    list.map(function (a) {
      return '<tr><td class="whitespace-nowrap">' + fmtTime(a.created_at) + '</td>' +
        '<td class="whitespace-nowrap font-medium">' + esc(a.actor) + '</td>' +
        '<td><span class="badge bg-secondary">' + esc(a.action) + '</span></td>' +
        '<td class="whitespace-nowrap">' + esc(a.target || '-') + '</td>' +
        '<td class="max-w-md text-xs text-gray-500">' + esc(a.detail || '-') + '</td></tr>';
    }).join('') + '</tbody></table></div>';
}
async function downloadAuditCsv() {
  try {
    await downloadBlob('/api/governance/audits/export', 'rongqi-audits.csv');
  } catch (e) { toast(e.message, 'error'); }
}
async function renderRedlines(box) {
  const list = await api('/api/governance/redlines');
  box.innerHTML = '<div class="flex items-center space-x-2 mb-4 text-danger font-bold">' +
    '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>' +
    '<span>红线不可逾越 —— 所有数字员工开发与运行必须遵守</span></div>' +
    '<div class="grid grid-cols-2 xl:grid-cols-3 gap-3">' +
    list.map(function (r) {
      return '<div class="border-2 border-danger/60 bg-red-50 rounded-lg p-4 flex items-start space-x-3">' +
        '<span class="w-7 h-7 rounded-full bg-danger text-white flex items-center justify-center font-black text-sm shrink-0">' + r.id + '</span>' +
        '<span class="text-sm font-medium text-red-900 leading-relaxed">' + esc(r.text) + '</span></div>';
    }).join('') + '</div>';
}

/* ==================== 视图 10：路线图 ==================== */
function nodeIcon(type) {
  if (type === 'agent') return '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2v3M5 8h14a1 1 0 011 1v9a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zM9 13v2M15 13v2"/></svg>';
  if (type === 'human') return '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.2" stroke-width="2"/><path stroke-linecap="round" stroke-width="2" d="M5.5 20a6.5 6.5 0 0113 0"/></svg>';
  return '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="9" cy="12" r="5" stroke-width="2"/><circle cx="15" cy="12" r="5" stroke-width="2"/></svg>';
}
function milestoneColor(status) {
  if ((status || '').indexOf('完成') >= 0) return 'bg-success';
  if ((status || '').indexOf('进行') >= 0) return 'bg-secondary';
  return 'bg-gray-400';
}
async function renderRoadmap(c) {
  c.innerHTML = loadingHtml('加载路线图…');
  const d = await api('/api/roadmap');
  const phaseGrad = ['gradient-primary', 'gradient-teal', 'gradient-accent'];
  let html = '<div class="relative">' +
    '<div class="absolute top-0 right-0 badge badge-outline !text-xs">智能体主导 60% · 人机协同 22.5% · 人类主导 17.5%（≤20% 红线）</div>';
  /* 三阶段卡 */
  html += '<div class="grid grid-cols-3 gap-4 mb-5">' +
    (d.phases || []).map(function (p, i) {
      return '<div class="' + (phaseGrad[i] || 'gradient-primary') + ' rounded-xl p-4 text-white shadow-md">' +
        '<div class="text-lg font-black">' + esc(p.name) + '</div>' +
        '<div class="text-xs opacity-80 mb-2">' + esc(p.period || '') + '</div>' +
        '<div class="text-sm opacity-90 leading-relaxed">' + esc(p.description || '') + '</div></div>';
    }).join('') + '</div>';
  /* 里程碑时间线（按月份） */
  const months = {};
  (d.milestones || []).forEach(function (m) {
    const k = m.month || '未排期';
    if (!months[k]) months[k] = [];
    months[k].push(m);
  });
  const monthKeys = Object.keys(months).sort();
  html += '<div class="data-card mb-5"><h3 class="font-bold text-primary mb-3">里程碑时间线</h3>' +
    '<div class="flex gap-4 overflow-x-auto pb-2">';
  monthKeys.forEach(function (mk) {
    html += '<div class="min-w-[230px] w-[230px] shrink-0">' +
      '<div class="text-sm font-black text-secondary border-b-2 border-accent pb-1 mb-2">' + esc(mk) + '</div>' +
      '<div class="space-y-2">' +
      months[mk].map(function (m) {
        return '<div class="border border-gray-100 rounded-lg p-2.5 bg-gray-50/60">' +
          '<div class="flex items-center justify-between">' +
            '<span class="inline-flex items-center gap-1 text-xs font-bold ' + (m.node_type === 'agent' ? 'text-teal' : m.node_type === 'human' ? 'text-secondary' : 'text-accent') + '">' +
              nodeIcon(m.node_type) + NODE_TYPE_META[m.node_type] + '</span>' +
            '<span class="badge ' + milestoneColor(m.status) + '">' + esc(m.status || '-') + '</span></div>' +
          '<div class="text-sm font-medium mt-1">' + esc(m.name) + '</div>' +
          '<div class="text-xs text-gray-400 mt-0.5">' + esc(m.phase || '') + ' · 负责：' + esc(m.owner || '-') + '</div></div>';
      }).join('') + '</div></div>';
  });
  html += '</div></div>';
  /* 四波次排期表 */
  html += '<div class="data-card"><h3 class="font-bold text-primary mb-3">四波次排期</h3>' +
    '<div class="overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
    '<th>波次</th><th>时间 / 平台范围 / 交付重点</th><th>数字员工数</th></tr></thead><tbody>' +
    (d.waves || []).map(function (w) {
      return '<tr><td><span class="badge bg-primary">第' + w.wave + '波</span></td>' +
        '<td>' + esc(w.description || '-') + '</td>' +
        '<td class="font-bold text-secondary">' + (w.agent_count ?? '-') + ' 个</td></tr>';
    }).join('') + '</tbody></table></div></div>';
  html += '</div>';
  c.innerHTML = html;
}

/* ==================== 视图：项目流程（N01-N40 五阶段泳道 + G1-G4 阶段门） ==================== */
const FLOW_ROLE_ORDER = ['PMO', '项目经理', '业务部门', '数字化平台', '财务部', '人力资源部', '流程革新部', '咨询委/决策层'];
const FLOW_ROLE_LABEL = { '咨询委/决策层': '咨询委·决策层' };
const FLOW_STAGE_NUM = ['一', '二', '三', '四', '五'];
const FLOW_STAGE_RANGE = { 1: 'N01-08', 2: 'N09-16', 3: 'N17-24', 4: 'N25-32', 5: 'N33-40' };
const FLOW_STAGE_FALLBACK = { 1: '项目启动', 2: '方案与设计', 3: '开发与测试', 4: '试点与验证', 5: '结项与移交' };
const FLOW_EXEC_ICON = { agent: '🤖', hybrid: '🤝', human: '👤' };
const FLOW_EXEC_NAME = { agent: '智能体自动执行', hybrid: 'AI 起草 · 人工确认', human: '人工执行' };
const FLOW_NODE_CLS = { '已完成': 'fn-done', '进行中': 'fn-active', '待确认': 'fn-confirm', '待签核': 'fn-sign', '未开始': 'fn-todo', '已锁定': 'fn-locked' };
const FLOW_NODE_BADGE = { '已完成': 'bg-success', '进行中': 'bg-secondary', '待确认': 'bg-accent', '待签核': 'bg-purple-500', '未开始': 'bg-gray-400', '已锁定': 'bg-gray-500' };
const FLOW_GATE_DOT = { '已通过': 'gate-done', '待签核': 'gate-pending', '未开启': 'gate-off' };
const FLOW_GATE_OF_STAGE = { 1: 'G1', 2: 'G2', 4: 'G3', 5: 'G4' };   /* 各阶段收尾门禁（阶段三无门禁） */
const FLOW_SIGN_TIERS = { G1: ['boss'], G2: ['boss'], G3: ['boss', 'coach', 'backbone'], G4: ['boss'] };
const FLOW_CONFIRM_TIERS = ['boss', 'coach', 'backbone'];
const flowState = { id: null, highlight: false, data: null };

function flowStageName(d, s) {
  const names = d.stage_names || {};
  return names[String(s)] || FLOW_STAGE_FALLBACK[s] || '';
}
function flowHashId() {
  const m = (location.hash || '').match(/^#\/flows\/(\d+)/);
  return m ? Number(m[1]) : null;
}
function canConfirmFlow() {
  return state.person && FLOW_CONFIRM_TIERS.indexOf(state.person.tier) >= 0;
}
function canSignGate(gate) {
  return state.person && (FLOW_SIGN_TIERS[gate] || []).indexOf(state.person.tier) >= 0;
}
function flowLockReason(n) {
  if (n.stage === 4) return '本阶段没有阶段门：等阶段三主链路节点全部完成后自动解锁';
  const g = FLOW_GATE_OF_STAGE[n.stage - 1];
  return g ? ('待 ' + g + ' 阶段门通过后解锁') : '待前置阶段完成后解锁';
}
/* 场景库/列表卡片统一入口：跳 #/flows/<id> 并选中该流程 */
function gotoFlow(id) {
  flowState.id = id;
  const target = '#/flows/' + id;
  if (location.hash === target) route();
  else location.hash = target;   // hashchange 触发路由渲染
}
function selectFlow(id) {
  if (flowState.id === id) return;
  gotoFlow(id);
}

async function renderFlows(c) {
  c.innerHTML = loadingHtml('加载项目流程…');
  const list = await api('/api/flows');
  if (!list.length) {
    c.innerHTML = '<div class="data-card">' + emptyHtml('还没有落地项目：到「场景库」把场景立项后，会自动生成五阶段项目流程') + '</div>';
    return;
  }
  const hashId = flowHashId();
  if (hashId && list.some(function (f) { return f.id === hashId; })) flowState.id = hashId;
  if (!flowState.id || !list.some(function (f) { return f.id === flowState.id; })) flowState.id = list[0].id;
  c.innerHTML = '<div class="flex gap-4 items-start">' +
    '<div class="w-72 shrink-0 space-y-3">' + list.map(flowCardHtml).join('') + '</div>' +
    '<div class="flex-1 min-w-0" id="flow-panel">' + loadingHtml('加载流程图…') + '</div></div>';
  await loadFlowDetail();
}

function flowCardHtml(f) {
  const gates = f.gates || {};
  const dots = ['G1', 'G2', 'G3', 'G4'].map(function (g) {
    const st = gates[g] || '未开启';
    return '<span class="flex items-center gap-1" title="阶段门 ' + g + '：' + st + '">' +
      '<span class="gate-dot ' + (FLOW_GATE_DOT[st] || 'gate-off') + '"></span>' +
      '<span class="text-[10px] text-gray-400">' + g + '</span></span>';
  }).join('');
  return '<div class="data-card !p-3 cursor-pointer card-hover flow-card' + (f.id === flowState.id ? ' flow-card-active' : '') + '" onclick="selectFlow(' + f.id + ')">' +
    '<div class="flex items-center justify-between gap-2">' +
      '<div class="font-bold text-sm text-primary truncate" title="' + esc(f.name) + '">' + esc(f.name) + '</div>' +
      statusBadge(f.status, { '进行中': 'bg-secondary', '已结项': 'bg-success', '已暂停': 'bg-gray-400' }) + '</div>' +
    '<div class="text-xs text-gray-500 mt-1.5">当前：阶段' + FLOW_STAGE_NUM[(f.current_stage || 1) - 1] + '·' + esc(f.current_stage_name || '') + '</div>' +
    '<div class="w-full bg-gray-200 rounded-full h-1.5 mt-2"><div class="gradient-accent h-1.5 rounded-full" style="width:' + (f.overall_progress || 0) + '%"></div></div>' +
    '<div class="text-[11px] text-gray-400 mt-1">总进度 ' + (f.overall_progress || 0) + '% · 节点 ' + f.nodes_done + '/' + f.nodes_total + '</div>' +
    '<div class="flex items-center justify-between mt-2">' +
      '<div class="flex items-center gap-2">' + dots + '</div>' +
      (f.delayed_critical > 0
        ? '<span class="flex items-center gap-1 text-[11px] text-danger font-semibold"><span class="delay-dot"></span>关键路径延迟 ' + f.delayed_critical + ' 处</span>'
        : '') +
    '</div></div>';
}

async function loadFlowDetail() {
  const panel = document.getElementById('flow-panel');
  if (!panel) return;
  panel.innerHTML = loadingHtml('加载流程图…');
  try {
    const d = await api('/api/flows/' + flowState.id);
    flowState.data = d;
    panel.innerHTML = flowToolbarHtml(d) + swimlaneHtml(d);
    /* 深链：#/flows/<fid>/<节点码> 直接打开节点详情抽屉（便于分享与验收截图） */
    const m = (location.hash || '').match(/^#\/flows\/(\d+)\/([Nn]\d{2})/);
    if (m && Number(m[1]) === flowState.id) openFlowNode(m[2].toUpperCase());
  } catch (e) {
    panel.innerHTML = errorHtml(e.message);
  }
}

function stagePct(d, s) {
  const nodes = d.nodes.filter(function (n) { return n.stage === s; });
  const done = nodes.filter(function (n) { return n.status === '已完成'; }).length;
  return { total: nodes.length, done: done, pct: nodes.length ? Math.round(done / nodes.length * 100) : 0 };
}

/* 顶部工具条：推进流程 + 五段阶段概览 + 关键路径高亮开关 */
function flowToolbarHtml(d) {
  const segs = [1, 2, 3, 4, 5].map(function (s) {
    const p = stagePct(d, s);
    const cur = d.current_stage === s && d.status === '进行中';
    return '<div class="flex-1 min-w-[92px]" title="阶段' + FLOW_STAGE_NUM[s - 1] + '·' + esc(flowStageName(d, s)) + '：完成 ' + p.done + '/' + p.total + '">' +
      '<div class="text-[11px] truncate ' + (cur ? 'text-accent font-bold' : 'text-gray-500') + '">阶段' + FLOW_STAGE_NUM[s - 1] + ' ' + p.pct + '%</div>' +
      '<div class="bg-gray-200 rounded-full h-1.5 mt-0.5"><div class="' + (p.pct === 100 ? 'bg-success' : 'gradient-accent') + ' h-1.5 rounded-full" style="width:' + p.pct + '%"></div></div></div>';
  }).join('');
  return '<div class="data-card !p-3 mb-3 flex items-center gap-4 flex-wrap">' +
    '<button class="btn-heartbeat" id="btn-flow-tick" onclick="flowTick()"' + (d.status !== '进行中' ? ' disabled' : '') + ' title="让项目管理智能体自动推进一轮（演示用）">▶ 推进流程</button>' +
    '<div class="flex-1 flex gap-3 min-w-[320px]">' + segs + '</div>' +
    '<label class="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none shrink-0" title="开启后淡化非关键路径节点">' +
      '<input type="checkbox" class="accent-orange-500"' + (flowState.highlight ? ' checked' : '') + ' onchange="toggleFlowHighlight(this.checked)">关键路径高亮</label></div>';
}

function swimlaneHtml(d) {
  const delayed = d.delayed_nodes || [];
  let html = '<div class="data-card !p-3 swim-wrap"><div class="swim-grid' + (flowState.highlight ? ' hl-critical' : '') + '" id="swim-grid">';
  /* 表头：左上角 + 5 个阶段列（带进度） */
  html += '<div class="swim-head swim-corner">角色 ＼ 阶段</div>';
  for (let s = 1; s <= 5; s++) {
    const p = stagePct(d, s);
    const gate = FLOW_GATE_OF_STAGE[s];
    const gStatus = gate ? ((d.gates || {})[gate] || '未开启') : null;
    html += '<div class="swim-head">' +
      '<div class="flex items-center justify-between gap-1"><span class="font-bold text-primary">阶段' + FLOW_STAGE_NUM[s - 1] + '·' + esc(flowStageName(d, s)) + '</span>' +
      (gate ? '<span class="badge ' + (gStatus === '已通过' ? 'bg-success' : gStatus === '待签核' ? 'bg-accent' : 'bg-gray-300') + '" title="阶段门 ' + gate + '：' + gStatus + '">⛳' + gate + '</span>' : '') + '</div>' +
      '<div class="text-[10px] text-gray-400 mt-0.5">' + FLOW_STAGE_RANGE[s] + ' · 完成 ' + p.done + '/' + p.total + '</div>' +
      '<div class="bg-gray-200 rounded-full h-1 mt-1"><div class="' + (p.pct === 100 ? 'bg-success' : 'bg-secondary') + ' h-1 rounded-full" style="width:' + p.pct + '%"></div></div></div>';
  }
  /* 8 行角色 × 5 列阶段 */
  FLOW_ROLE_ORDER.forEach(function (role) {
    html += '<div class="swim-role">' + esc(FLOW_ROLE_LABEL[role] || role) + '</div>';
    for (let s = 1; s <= 5; s++) {
      const cell = d.nodes.filter(function (n) { return n.role_name === role && n.stage === s; });
      html += '<div class="swim-cell">' + cell.map(function (n) { return flowNodeCard(n, delayed); }).join('') + '</div>';
    }
  });
  html += '</div>';
  /* 图例 */
  html += '<div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-[11px] text-gray-500">' +
    '<span>🤖 智能体</span><span>🤝 AI起草·人工确认</span><span>👤 人工</span><span>⛳ 阶段门</span>' +
    '<span class="flex items-center gap-1"><span class="legend-line"></span>加粗橙边 = 关键路径</span>' +
    '<span class="flex items-center gap-1"><span class="legend-chip fn-done"></span>已完成</span>' +
    '<span class="flex items-center gap-1"><span class="legend-chip fn-active"></span>进行中</span>' +
    '<span class="flex items-center gap-1"><span class="legend-chip fn-confirm"></span>待确认</span>' +
    '<span class="flex items-center gap-1"><span class="legend-chip fn-sign"></span>待签核</span>' +
    '<span class="flex items-center gap-1"><span class="legend-chip fn-todo"></span>未开始</span>' +
    '<span class="flex items-center gap-1"><span class="legend-chip fn-locked"></span>已锁定</span>' +
    '<span class="flex items-center gap-1"><span class="delay-dot"></span>延迟预警</span></div>';
  return html + '</div>';
}

function flowNodeCard(n, delayed) {
  const cls = FLOW_NODE_CLS[n.status] || 'fn-todo';
  const isDelay = delayed.indexOf(n.code) >= 0;
  return '<div class="flow-node ' + cls + (n.is_critical ? ' fn-critical' : '') + '" onclick="openFlowNode(' + esc(jsStr(n.code)) + ')"' +
    ' title="' + esc(n.title + (n.outputs ? '\n产出物：' + n.outputs : '') + '\n点击查看详情') + '">' +
    (isDelay ? '<span class="fn-delay" title="关键路径延迟预警"></span>' : '') +
    '<div class="flex items-center gap-1">' +
      '<span class="font-bold text-[11px] text-primary">' + esc(n.code) + '</span>' +
      '<span>' + (FLOW_EXEC_ICON[n.exec_type] || '') + '</span>' +
      (n.gate_code ? '<span class="fn-gate-badge">⛳' + esc(n.gate_code) + '</span>' : '') +
      '<span class="flex-1"></span>' +
      '<span class="fn-status">' + esc(n.status) + '</span></div>' +
    '<div class="fn-title">' + esc(n.title) + '</div></div>';
}

function flowRow(label, value) {
  return '<div class="flex py-1.5 border-b border-gray-100 text-sm"><span class="w-20 shrink-0 text-gray-400 text-xs pt-0.5">' + label + '</span><span class="flex-1 text-gray-700">' + value + '</span></div>';
}

/* 节点详情抽屉：完整信息 + 按状态/权限给动作 */
function openFlowNode(code) {
  const d = flowState.data;
  if (!d) return;
  const n = d.nodes.find(function (x) { return x.code === code; });
  if (!n) return;
  const gateRec = n.gate_code ? (d.gate_records || []).find(function (g) { return g.gate === n.gate_code; }) : null;
  let html = '<div class="p-5">' +
    '<div class="flex items-center justify-between mb-3">' +
      '<div class="flex items-center gap-2 flex-wrap"><span class="text-lg font-black text-primary">' + esc(n.code) + '</span>' +
      (n.gate_code ? '<span class="fn-gate-badge !text-xs">⛳阶段门 ' + esc(n.gate_code) + '</span>' : '') +
      (n.is_critical ? '<span class="badge bg-accent">关键路径</span>' : '') + '</div>' +
      '<button onclick="closeDrawer()" class="text-gray-400 hover:text-gray-600 shrink-0" title="关闭">' +
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></button></div>' +
    '<div class="font-bold text-gray-800 mb-2">' + esc(n.title) + '</div>' +
    '<div class="mb-2">' + statusBadge(n.status, FLOW_NODE_BADGE) + '</div>' +
    flowRow('所属阶段', '阶段' + FLOW_STAGE_NUM[n.stage - 1] + '·' + esc(flowStageName(d, n.stage))) +
    flowRow('负责角色', esc(FLOW_ROLE_LABEL[n.role_name] || n.role_name)) +
    flowRow('执行方式', (FLOW_EXEC_ICON[n.exec_type] || '') + ' ' + esc(FLOW_EXEC_NAME[n.exec_type] || n.exec_type)) +
    flowRow('产出物', esc(n.outputs || '—')) +
    flowRow('开始时间', fmtTime(n.started_at)) +
    flowRow('完成时间', fmtTime(n.done_at)) +
    (n.note ? flowRow('备注', esc(n.note)) : '');
  if (gateRec) {
    html += '<div class="mt-3 p-3 rounded-lg bg-purple-50 border border-purple-100 text-xs text-gray-600">' +
      '<div class="font-bold text-purple-700 mb-1">⛳ 阶段门 ' + gateRec.gate + '（' + esc(gateRec.status) + '）</div>' +
      (gateRec.signed_by
        ? '签核人：' + esc(gateRec.signed_by) + ' · ' + fmtTime(gateRec.signed_at) + (gateRec.comment ? '<br>签核意见：' + esc(gateRec.comment) : '')
        : '尚未签核') + '</div>';
  }
  /* 动作区 */
  html += '<div class="mt-4">';
  if (n.status === '待确认' && !n.gate_code) {
    html += canConfirmFlow()
      ? '<button class="btn-primary w-full" onclick="openNodeConfirmModal(' + esc(jsStr(n.code)) + ')">确认生效</button>'
      : '<div class="text-xs text-gray-500">AI 已起草完成，需骨干及以上同事确认生效。</div>';
  } else if (n.status === '进行中' && n.exec_type === 'human' && !n.gate_code) {
    html += canConfirmFlow()
      ? '<button class="btn-primary w-full" onclick="openNodeConfirmModal(' + esc(jsStr(n.code)) + ')">标记完成</button>'
      : '<div class="text-xs text-gray-500">该节点需人工完成，完成后由骨干及以上同事标记。</div>';
  } else if (n.status === '待签核' && n.gate_code) {
    html += canSignGate(n.gate_code)
      ? '<button class="btn-primary w-full" onclick="openGateSignModal(' + esc(jsStr(n.gate_code)) + ')">签核通过</button>'
      : '<div class="text-xs text-gray-500">' + (n.gate_code === 'G3' ? '需骨干及以上签核（G3 开放教练团/业务骨干）。' : '需决策层签核。') + '</div>';
  } else if (n.status === '已锁定') {
    html += '<div class="text-xs text-gray-500">🔒 ' + esc(flowLockReason(n)) + '</div>';
  } else if (n.status === '已完成') {
    html += '<div class="text-xs text-success font-semibold">✓ 该节点已完成</div>';
  } else if (n.status === '未开始') {
    html += '<div class="text-xs text-gray-500">排队中：点上方「推进流程」可让智能体跑一轮。</div>';
  }
  html += '</div></div>';
  openDrawer(html);
}

/* 🤝待确认节点确认生效 / 👤进行中节点标记完成（带备注弹窗） */
function openNodeConfirmModal(code) {
  const d = flowState.data;
  const n = d.nodes.find(function (x) { return x.code === code; });
  openModal('<h3 class="font-bold text-primary text-lg mb-1">' + (n.exec_type === 'hybrid' ? '确认生效' : '标记完成') + ' · ' + esc(code) + '</h3>' +
    '<div class="text-sm text-gray-600 mb-3">' + esc(n.title) + '</div>' +
    '<label class="form-label">备注（可选，会写进节点记录）</label>' +
    '<textarea id="fc-comment" class="form-textarea" rows="3" placeholder="如：UAT 反馈已核对，同意生效"></textarea>' +
    '<div class="flex justify-end space-x-2 mt-4"><button class="btn-ghost" onclick="closeModal()">取消</button>' +
    '<button class="btn-primary" id="fc-submit" onclick="submitNodeConfirm(' + esc(jsStr(code)) + ')">提交</button></div>');
}
async function submitNodeConfirm(code) {
  const comment = document.getElementById('fc-comment').value.trim();
  await withBusy(document.getElementById('fc-submit'), async function () {
    try {
      await postApi('/api/flows/' + flowState.id + '/nodes/' + encodeURIComponent(code) + '/confirm', { comment: comment });
      closeModal();
      toast(code + ' 已确认生效');
      route();
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* 阶段门签核弹窗 */
function openGateSignModal(gate) {
  openModal('<h3 class="font-bold text-primary text-lg mb-1">阶段门签核 · ' + esc(gate) + '</h3>' +
    '<div class="text-sm text-gray-600 mb-3">签核通过后自动解锁下一阶段，操作会记入审计。</div>' +
    '<label class="form-label">签核意见（可选）</label>' +
    '<textarea id="fg-comment" class="form-textarea" rows="3" placeholder="如：同意进入下一阶段"></textarea>' +
    '<div class="flex justify-end space-x-2 mt-4"><button class="btn-ghost" onclick="closeModal()">取消</button>' +
    '<button class="btn-primary" id="fg-submit" onclick="submitGateSign(' + esc(jsStr(gate)) + ')">签核通过</button></div>');
}
async function submitGateSign(gate) {
  const comment = document.getElementById('fg-comment').value.trim();
  await withBusy(document.getElementById('fg-submit'), async function () {
    try {
      await postApi('/api/flows/' + flowState.id + '/gates/' + encodeURIComponent(gate) + '/sign', { comment: comment });
      closeModal();
      toast(gate + ' 签核通过，下一阶段已解锁');
      route();
    } catch (e) { toast(e.message, 'error'); }
  });
}

/* 手动推进一轮（演示用），toast 汇报推进了哪些节点 */
async function flowTick() {
  const btn = document.getElementById('btn-flow-tick');
  if (btn) btn.disabled = true;
  try {
    const r = await postApi('/api/flows/' + flowState.id + '/tick');
    const p = r.processed || [];
    toast(p.length
      ? '本轮推进：' + p.map(function (x) { return x.code + (FLOW_EXEC_ICON[x.exec_type] || ''); }).join('、')
      : '没有可自动推进的节点（等待人工确认或签核）', p.length ? 'success' : 'info');
    route();
  } catch (e) {
    toast(e.message, 'error');
    if (btn) btn.disabled = false;
  }
}

function toggleFlowHighlight(v) {
  flowState.highlight = v;
  const g = document.getElementById('swim-grid');
  if (g) g.classList.toggle('hl-critical', v);
}

/* ==================== 初始化 ==================== */
async function exchangeImLoginCode(code) {
  try {
    const r = await postApi('/api/auth/oauth/session', { code: code });
    acceptSession(r);
    history.replaceState(null, '', location.pathname + location.hash);
    toast('IM 身份验证成功，欢迎 ' + r.person.name);
    enterApp();
  } catch (e) {
    history.replaceState(null, '', location.pathname);
    toast(e.message, 'error');
    bootLogin();
  }
}
window.addEventListener('DOMContentLoaded', function () {
  buildSidebar();
  document.getElementById('btn-heartbeat').addEventListener('click', runHeartbeat);
  var menuBtn = document.getElementById('btn-menu');
  if (menuBtn) menuBtn.addEventListener('click', function () {
    document.getElementById('app-view').classList.toggle('sidebar-open');
  });
  window.addEventListener('hashchange', route);
  window.addEventListener('resize', function () {
    charts.forEach(function (c) { try { c.resize(); } catch (e) {} });
  });
  // IM 扫码登录回调：URL 带 ?im_login=<code> 时换发会话
  const urlParams = new URLSearchParams(location.search);
  const imCode = urlParams.get('im_login');
  if (imCode) {
    exchangeImLoginCode(imCode);
  } else if (state.token && state.person) enterApp();
  else bootLogin();
});
