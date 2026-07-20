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
  '种子基金': '档位参考：不设上下限，按项目评审确定',
};
const SCENARIO_STATUS_META = { '待立项': 'bg-gray-400', '已立项': 'bg-secondary', '开发中': 'bg-accent', '试点中': 'bg-teal', '已验收': 'bg-success', '已下线': 'bg-danger' };
const ZONE_META = {
  discussion: { name: '讨论区',       desc: '和同事讨论，AI 不打扰', ph: '和同事聊聊想法……（AI 不会在这里插话）' },
  agent:      { name: 'Agent 执行区', desc: '@数字员工 直接派活，它干完你检查', ph: '@数字员工 + 说人话描述任务，如：整理本周订单资料并生成唛头' },
  private:    { name: '私聊打磨区',   desc: '先和 AI 助手一对一理清需求（它只回建议不干活），想清楚了再去执行区派活', ph: '把想法说给 AI 助手听，它帮你理成任务草稿（不会派活）' },
};
const TASK_COLUMNS = ['待处理', '进行中', '待审核', '已通过', '已驳回'];
const TASK_STATUS_META = { '待处理': 'bg-gray-400', '进行中': 'bg-secondary', '待审核': 'bg-accent', '已通过': 'bg-success', '已驳回': 'bg-danger' };
const REIMB_STEPS = ['平台长审批', '数字化复核', '财务报销'];
const NODE_TYPE_META = { agent: '智能体主导', hybrid: '人机协同', human: '人类主导' };

/* ==================== 全局状态 ==================== */
const state = {
  token: localStorage.getItem('rq_token') || '',
  person: JSON.parse(localStorage.getItem('rq_person') || 'null'),
};
let charts = [];                    // ECharts 实例注册表，切换视图时统一 dispose
const wsState = { id: null, zone: 'discussion', members: [] };  // 协作空间选中态
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
function closeModal() { document.getElementById('modal-root').innerHTML = ''; }
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
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  let res;
  try {
    res = await fetch(path, Object.assign({}, options || {}, { headers: headers }));
  } catch (e) {
    throw new Error('网络异常，请确认后端服务已启动');
  }
  if (res.status === 401) {
    doLogout();
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

/* ==================== 导航与路由 ==================== */
const ICON = {
  dashboard: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/>',
  workspaces: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 11.5a8.5 8.5 0 01-8.5 8.5c-1.5 0-2.9-.38-4.1-1.05L3 20l1.05-5.4A8.5 8.5 0 1121 11.5z"/>',
  agents: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2v3M5 8h14a1 1 0 011 1v9a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zM9 13v2M15 13v2M2 12v4M22 12v4"/>',
  scenarios: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 18h6M10 21h4M12 3a6 6 0 00-3.4 10.9c.8.6 1.4 1.5 1.4 2.5v.6h4v-.6c0-1 .6-1.9 1.4-2.5A6 6 0 0012 3z"/>',
  tasks: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 4h4v16H5zM11 4h4v10h-4zM17 4h4v7h-4z" transform="translate(-1 0)"/>',
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
  { key: 'skills',     name: 'Skill 库',   render: renderSkills },
  { key: 'knowledge',  name: '知识库',     render: renderKnowledge },
  { key: 'org',        name: '组织通讯录', render: renderOrg },
  { key: 'governance', name: '治理中心',   render: renderGovernance },
  { key: 'roadmap',    name: '路线图',     render: renderRoadmap },
];
/* 每个视图顶部的一行人话说明（低学习门槛） */
const VIEW_HINTS = {
  dashboard:  '全公司 AI 推进情况一目了然',
  workspaces: '在这里跟数字员工说话、派活、收结果',
  agents:     '你的 AI 同事花名册',
  scenarios:  '想让 AI 干什么活，从这里提',
  tasks:      '数字员工干的活，在这里检查和确认',
  skills:     '好用的 AI 话术和本领，沉淀在这里大家复用',
  knowledge:  '公司的文件资料柜（NAS）',
  org:        '看看同事和数字员工都在哪个部门',
  governance: '奖励申请、AI 费用报销、操作记录',
  roadmap:    '今年的推进计划',
};
function currentViewKey() {
  const h = (location.hash || '').replace(/^#\/?/, '').split('/')[0];
  return VIEWS.some(function (v) { return v.key === h; }) ? h : 'dashboard';
}
function buildSidebar() {
  document.getElementById('side-nav').innerHTML = VIEWS.map(function (v) {
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
  const view = VIEWS.find(function (v) { return v.key === key; });
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
async function bootLogin() {
  const box = document.getElementById('login-people');
  box.innerHTML = '<div class="text-gray-300 flex items-center space-x-2"><span class="spinner"></span><span>正在加载组织人员…</span></div>';
  try {
    const people = await api('/api/people');
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
async function doLogin(personId) {
  try {
    const r = await postApi('/api/login', { person_id: personId });
    state.token = r.token;
    state.person = r.person;
    localStorage.setItem('rq_token', r.token);
    localStorage.setItem('rq_person', JSON.stringify(r.person));
    toast('欢迎，' + r.person.name + '（' + (TIER_META[r.person.tier] || {}).label + '）');
    enterApp();
  } catch (e) {
    toast(e.message, 'error');
  }
}
function enterApp() {
  document.getElementById('login-view').classList.add('hidden');
  document.getElementById('app-view').classList.remove('hidden');
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
async function renderDashboard(c) {
  c.innerHTML = skeletonHtml(5);
  const d = await api('/api/metrics/dashboard');
  const k = d.kpi || {};
  /* kpi 每项为 {value, note} 结构（note 为口径说明） */
  const kval = function (x) { return (x && typeof x === 'object') ? (x.value ?? 0) : (x ?? 0); };
  const knote = function (x) { return (x && typeof x === 'object' && x.note) ? x.note : ''; };
  const kpis = [
    { label: '试点覆盖率',     v: kval(k.trial_coverage) + '%', sub: '试点中+已验收场景占比', color: 'text-secondary', note: knote(k.trial_coverage) },
    { label: '验收覆盖率',     v: kval(k.coverage) + '%',       sub: '方案口径 · 目标 ≥70%',  color: 'text-gray-500',  note: knote(k.coverage) },
    { label: '验收通过率',     v: kval(k.acceptance_rate) + '%', sub: '目标 ≥85%',            color: 'text-success',   note: knote(k.acceptance_rate) },
    { label: '活跃使用率(7日)', v: kval(k.active_rate) + '%',    sub: '目标 ≥60%',            color: 'text-teal',      note: knote(k.active_rate) },
    { label: '累计节省工时',   v: fmtNum(kval(k.hours_saved)) + ' h',   sub: '数字员工产出',   color: 'text-accent',    note: knote(k.hours_saved) },
    { label: '交付准确率',     v: kval(k.accuracy) + '%',       sub: '目标 ≥95%',             color: 'text-secondary', note: knote(k.accuracy) },
    { label: '年化综合收益',   v: '¥' + fmtWan(kval(k.annual_benefit)), sub: '目标 ¥79万',     color: 'text-success',   note: knote(k.annual_benefit) },
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
  let html = '<div class="flex gap-5" style="height:calc(100vh - 7.5rem)">';
  /* 左栏：工作区列表 */
  html += '<div class="w-72 shrink-0 data-card !p-3 flex flex-col"><div class="text-sm font-bold text-primary px-2 py-1">工作区列表（' + list.length + '）</div>' +
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
      return '<div class="zone-tab ' + (key === wsState.zone ? 'active' : '') + '" onclick="switchZone(\'' + key + '\')">' + ZONE_META[key].name + '</div>';
    }).join('') +
    '</div></div>' +
    '<div class="px-4 py-1.5 bg-teal/5 text-xs text-teal border-b border-gray-100 shrink-0">💡 ' + esc(z.name) + '：' + esc(z.desc) + '</div>' +
    '<div id="msg-list" class="flex-1 overflow-y-auto chat-scroll px-4 py-3 bg-gray-50/50"></div>' +
    /* 输入区 */
    '<div class="p-3 border-t border-gray-100 shrink-0 relative">' +
      '<div id="at-popup" class="at-popup hidden"></div>' +
      '<div id="dispatch-hint" class="hidden text-xs text-accent font-medium mb-1.5">⚡ 将派发任务给数字员工执行</div>' +
      '<div class="flex items-end space-x-2">' +
        '<textarea id="ws-input" class="form-textarea flex-1" rows="2" placeholder="' + esc(z.ph || '输入消息，Enter 发送') + '"></textarea>' +
        '<button class="btn-primary shrink-0" onclick="sendWsMessage()">发送</button>' +
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
  return '<div class="flex my-2.5"><div class="msg-avatar bg-teal mr-2">' + ROBOT_SVG + '</div>' +
    '<div class="flex flex-col max-w-full"><div class="text-xs text-gray-400 mb-1">' + esc(m.sender_name) +
    (ag.dept_name ? ' · ' + esc(ag.dept_name) : '') + (isReport ? ' · 日报' : '') + ' · ' + t + '</div>' +
    '<div class="msg-bubble msg-bubble-agent' + (isReport ? ' max-h-72 overflow-y-auto' : '') + '">' + mdLite(m.content) + '</div></div></div>';
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
        return '<div class="at-item" onclick="insertAt(\'' + esc(a.name) + '\')">' +
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
  hint.classList.toggle('hidden', !(wsState.zone === 'agent' || mention));
}
async function sendWsMessage() {
  const ta = document.getElementById('ws-input');
  const content = (ta.value || '').trim();
  if (!content) return;
  try {
    const r = await postApi('/api/workspaces/' + wsState.id + '/messages', { content: content, zone: wsState.zone });
    ta.value = '';
    updateDispatchHint();
    const n = (r.dispatched || []).length;
    if (n) toast('已派发任务给：' + r.dispatched.map(function (d) { return d.agent_name; }).join('、'), 'info');
    await loadMessages(n > 0);
  } catch (e) { toast(e.message, 'error'); }
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
    '<button class="btn-ghost" onclick="resetAgentFilters()">重置</button></div>';
}
async function renderAgents(c) {
  c.innerHTML = agentFiltersHtml() + '<div id="agents-grid">' + loadingHtml('加载数字员工…') + '</div>';
  await ensurePlatforms();
  const sel = document.getElementById('f-platform');
  (cache.platforms || []).forEach(function (p) {
    const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; sel.appendChild(o);
  });
  await loadAgents();
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
async function openAgentDrawer(id) {
  openDrawer(loadingHtml('加载档案…'));
  try {
    const a = await api('/api/agents/' + id);
    let html = '<div class="p-5">' +
      '<div class="flex items-start justify-between">' +
        '<div class="flex items-center space-x-3"><div class="msg-avatar bg-teal !w-11 !h-11">' + ROBOT_SVG + '</div>' +
          '<div><div class="font-black text-lg text-primary">' + esc(a.name) + '</div>' +
          '<div class="text-xs text-gray-500">' + esc(a.code || '') + ' · ' + esc(a.dept_name || '') + '</div></div></div>' +
        '<button onclick="closeDrawer()" class="text-gray-400 hover:text-gray-700"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></button></div>' +
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

/* ==================== 视图 4：场景库 ==================== */
function scenarioFiltersHtml() {
  return '<div class="data-card !p-3 flex flex-wrap items-center gap-2 mb-4">' +
    '<select id="sf-platform" class="form-select !w-40"><option value="">全部平台</option></select>' +
    '<select id="sf-status" class="form-select !w-32"><option value="">全部状态</option>' +
      Object.keys(SCENARIO_STATUS_META).map(function (s) { return '<option>' + s + '</option>'; }).join('') + '</select>' +
    '<select id="sf-priority" class="form-select !w-32"><option value="">全部优先级</option><option>高</option><option>中</option><option>低</option></select>' +
    '<button class="btn-primary" onclick="loadScenarios()">筛选</button>' +
    '<button class="btn-ghost" onclick="resetScenarioFilters()">重置</button>' +
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
    let list = await api('/api/scenarios' + (qs.toString() ? '?' + qs : ''));
    /* 首批试点置顶 */
    list = list.slice().sort(function (a, b) { return (b.batch === '首批' ? 1 : 0) - (a.batch === '首批' ? 1 : 0); });
    if (!list.length) { box.innerHTML = '<div class="data-card">' + emptyHtml('暂无场景，点击右上角「新建场景」发起申报') + '</div>'; return; }
    box.innerHTML = '<div class="data-card !p-0 overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
      '<th>场景名称</th><th>部门</th><th>数字员工</th><th>优先级</th><th>批次</th><th>预期收益</th><th>状态</th><th>操作</th>' +
      '</tr></thead><tbody>' + list.map(function (s) {
        return '<tr>' +
          '<td><div class="flex items-center gap-1.5"><span class="font-medium">' + esc(s.name) + '</span>' +
            (s.batch === '首批' ? '<span class="badge badge-gold">首批试点</span>' : '') + '</div>' +
            '<div class="text-xs text-gray-400 mt-0.5 max-w-xs truncate" title="' + esc(s.description || '') + '">' + esc(s.description || '') + '</div></td>' +
          '<td class="whitespace-nowrap">' + esc(s.dept_name || '-') + '</td>' +
          '<td class="whitespace-nowrap">' + (s.agent_name ? esc(s.agent_name) : '<span class="text-gray-400">未绑定</span>') + '</td>' +
          '<td>' + priorityBadge(s.priority) + '</td>' +
          '<td class="whitespace-nowrap">' + esc(s.batch || '-') + '</td>' +
          '<td class="whitespace-nowrap">' + esc(s.expected_benefit || '-') + '</td>' +
          '<td>' + statusBadge(s.status, SCENARIO_STATUS_META) + '</td>' +
          '<td>' + (s.status === '待立项'
            ? '<button class="btn-success-sm" onclick="initiateScenario(' + s.id + ')">敏捷立项</button>'
            : '<span class="text-xs text-gray-300">—</span>') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  } catch (e) { box.innerHTML = errorHtml(e.message); }
}
async function initiateScenario(id) {
  try {
    const r = await postApi('/api/scenarios/' + id + '/initiate');
    toast('立项成功，已自动创建项目工作区「' + (r.workspace || {}).name + '」');
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
      '<button class="btn-primary" onclick="submitScenario()">提交申报</button></div>');
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
  try {
    await postApi('/api/scenarios', body);
    closeModal();
    toast('场景申报成功，待敏捷立项');
    loadScenarios();
  } catch (e) { toast(e.message, 'error'); }
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
      '<button class="btn-primary" onclick="submitTask()">创建</button></div>');
}
async function submitTask() {
  const body = {
    title: document.getElementById('nt-title').value.trim(),
    priority: document.getElementById('nt-priority').value,
  };
  const agentId = Number(document.getElementById('nt-agent').value);
  if (agentId) body.agent_id = agentId;
  if (!body.title) { toast('请填写任务标题', 'error'); return; }
  try {
    const r = await postApi('/api/tasks', body);
    closeModal();
    if (r && r.hint) toast(r.hint, 'info');
    else toast(agentId ? '任务已创建，数字员工已完成执行，待审核' : '任务已创建');
    renderTasks(document.getElementById('view-container'));
  } catch (e) { toast(e.message, 'error'); }
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

/* ==================== 视图 6：Skill 库 ==================== */
async function renderSkills(c) {
  c.innerHTML = loadingHtml('加载 Skill 资产…');
  const list = await api('/api/skills');
  const scopes = ['公开', '组织', '个人'];
  const scopeMeta = { '公开': 'bg-success', '组织': 'bg-secondary', '个人': 'bg-accent' };
  const scopeEmpty = {
    '公开': '暂无公开 Skill',
    '组织': '暂无组织级 Skill，好用的团队话术可以沉淀到这里',
    '个人': '还没有个人技能，把你常用的 AI 话术沉淀到这里',
  };
  let html = '';
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
          '<div class="text-xs text-gray-400 mt-2 pt-2 border-t border-gray-100">Owner：' + esc(s.owner_name || '-') + '</div></div>';
      }).join('') + '</div>';
    }
    html += '</div>';
  });
  c.innerHTML = html;
}

/* ==================== 视图 7：知识库 ==================== */
async function renderKnowledge(c) {
  c.innerHTML = loadingHtml('加载 NAS 空间…');
  const spaces = await api('/api/knowledge/spaces');
  if (!knState.spaceId || !spaces.some(function (s) { return s.id === knState.spaceId; })) {
    knState.spaceId = spaces.length ? spaces[0].id : null;
  }
  let html = '<div class="grid grid-cols-2 xl:grid-cols-3 gap-4 mb-5">';
  spaces.forEach(function (s) {
    const active = s.id === knState.spaceId;
    html += '<div class="data-card card-hover cursor-pointer ' + (active ? 'ring-2 ring-secondary' : '') + '" onclick="selectSpace(' + s.id + ')">' +
      '<div class="flex items-center justify-between mb-1">' +
        '<span class="font-bold text-primary">' + esc(s.name) + '</span>' +
        '<span class="badge bg-teal">' + (s.doc_count ?? 0) + ' 文档</span></div>' +
      '<div class="text-xs text-gray-500 space-y-0.5">' +
        '<div>设备：' + esc(s.device || '群晖DS925+') + ' · 容量 ' + esc(s.capacity || '-') + '</div>' +
        '<div>所属：' + esc(s.dept_name || '-') + ' · 领域：' + esc(s.domain || '-') + '</div></div></div>';
  });
  html += '</div>';
  html += '<div class="data-card"><div class="flex items-center justify-between mb-3">' +
    '<h3 class="font-bold text-primary">空间文档</h3>' +
    '<button class="btn-primary" onclick="openDocModal()">+ 登记文档</button></div>' +
    '<div id="docs-box">' + loadingHtml() + '</div></div>';
  c.innerHTML = html;
  await loadSpaceDocs();
}
async function selectSpace(id) {
  knState.spaceId = id;
  await renderKnowledge(document.getElementById('view-container'));
}
async function loadSpaceDocs() {
  const box = document.getElementById('docs-box');
  if (!box) return;
  const docs = await api('/api/knowledge/documents?space_id=' + knState.spaceId);
  if (!docs.length) { box.innerHTML = emptyHtml('这个资料柜还是空的，点右上角「登记文档」把公司文件放进来'); return; }
  box.innerHTML = '<div class="overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
    '<th>标题</th><th>密级</th><th>标签</th><th>上传人</th><th>时间</th></tr></thead><tbody>' +
    docs.map(function (d) {
      return '<tr><td class="font-medium">' + esc(d.title) + '</td>' +
        '<td><span class="badge ' + (LEVEL_META[d.level] || 'bg-gray-400') + '">' + esc(d.level) + '</span></td>' +
        '<td class="text-xs text-gray-500">' + esc(d.tags || '-') + '</td>' +
        '<td class="whitespace-nowrap">' + esc(d.uploaded_by || '-') + '</td>' +
        '<td class="whitespace-nowrap">' + fmtTime(d.created_at) + '</td></tr>';
    }).join('') + '</tbody></table></div>';
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
      '<button class="btn-primary" onclick="submitDoc()">登记</button></div>');
}
async function submitDoc() {
  const title = document.getElementById('nd-title').value.trim();
  if (!title) { toast('请填写文档标题', 'error'); return; }
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
}

/* ==================== 视图 8：组织通讯录 ==================== */
async function renderOrg(c) {
  c.innerHTML = loadingHtml('加载组织树…');
  const tree = await api('/api/org/tree');
  let html = '<div class="data-card !py-3 mb-4 flex items-center space-x-3 bg-gradient-to-r from-primary/5 to-teal/5">' +
    '<svg class="w-6 h-6 text-teal shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' +
    '<div class="text-sm text-gray-600">Teams.md 理念：<b class="text-primary">AI 通过通讯录理解组织</b>，调度人与数字员工协同作战——五个业务平台、部门与数字员工在此一图总览。</div></div>';
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
  /* 支持深链 #/governance/<tab> */
  const sub = (location.hash || '').replace(/^#\/?/, '').split('/')[1];
  if (sub && GOV_TABS.some(function (t) { return t.key === sub; })) govState.tab = sub;
  let pendCount = 0;
  try {
    const rl = await api('/api/governance/reimbursements');
    pendCount = rl.filter(reimbActionable).length;
  } catch (e) { /* 角标失败不阻塞页面 */ }
  c.innerHTML = '<div class="data-card !p-0">' +
    '<div class="flex px-4 pt-3 border-b border-gray-100 space-x-1 flex-wrap">' +
    GOV_TABS.map(function (t) {
      return '<div class="zone-tab ' + (govState.tab === t.key ? 'active' : '') + '" onclick="switchGovTab(\'' + t.key + '\')">' + t.name +
        (t.key === 'reimbursements' && pendCount > 0 ? ' <span class="badge bg-danger">' + pendCount + '</span>' : '') + '</div>';
    }).join('') + '</div>' +
    '<div id="gov-body" class="p-4">' + loadingHtml() + '</div></div>';
  await loadGovTab();
}
async function switchGovTab(tab) {
  govState.tab = tab;
  document.querySelectorAll('#view-container .zone-tab').forEach(function (el, i) {
    el.classList.toggle('active', GOV_TABS[i].key === tab);
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
  const list = await api('/api/governance/incentives');
  let html = '<div class="flex justify-end mb-3"><button class="btn-primary" onclick="openIncentiveModal()">+ 申报激励</button></div>';
  if (!list.length) html += emptyHtml('暂无激励申报');
  else {
    html += '<div class="overflow-x-auto"><table class="gov-table w-full"><thead><tr>' +
      '<th>奖项</th><th>申报人/候选人</th><th>理由</th><th>金额</th><th>状态</th><th>时间</th></tr></thead><tbody>' +
      list.map(function (x) {
        return '<tr><td><span class="badge ' + (INCENTIVE_META[x.type] || 'bg-gray-400') + '">' + esc(x.type) + '</span></td>' +
          '<td class="whitespace-nowrap font-medium">' + esc(x.nominee) + '</td>' +
          '<td class="max-w-md">' + esc(x.reason || '-') + '</td>' +
          '<td class="whitespace-nowrap font-bold text-accent">¥' + fmtNum(x.amount) + '</td>' +
          '<td>' + statusBadge(x.status, { '申报中': 'bg-accent', '已发放': 'bg-success', '已驳回': 'bg-danger' }) + '</td>' +
          '<td class="whitespace-nowrap">' + fmtTime(x.created_at) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  box.innerHTML = html;
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
      '<button class="btn-primary" onclick="submitIncentive()">提交申报</button></div>');
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
  try {
    await postApi('/api/governance/incentives', body);
    closeModal(); toast('激励申报已提交');
    renderIncentives(document.getElementById('gov-body'));
  } catch (e) { toast(e.message, 'error'); }
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
      '<button class="btn-primary" onclick="submitReimb()">提交申报</button></div>');
}
async function submitReimb() {
  const body = {
    provider: document.getElementById('nr-provider').value.trim(),
    tokens: Number(document.getElementById('nr-tokens').value) || 0,
    amount: Number(document.getElementById('nr-amount').value) || 0,
  };
  if (!body.provider) { toast('请填写服务商', 'error'); return; }
  try {
    await postApi('/api/governance/reimbursements', body);
    closeModal(); toast('报销申报已提交，进入平台长审批');
    renderReimbursements(document.getElementById('gov-body'));
  } catch (e) { toast(e.message, 'error'); }
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
  box.innerHTML = '<div class="overflow-x-auto max-h-[60vh] overflow-y-auto"><table class="gov-table w-full"><thead><tr>' +
    '<th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>详情</th></tr></thead><tbody>' +
    list.map(function (a) {
      return '<tr><td class="whitespace-nowrap">' + fmtTime(a.created_at) + '</td>' +
        '<td class="whitespace-nowrap font-medium">' + esc(a.actor) + '</td>' +
        '<td><span class="badge bg-secondary">' + esc(a.action) + '</span></td>' +
        '<td class="whitespace-nowrap">' + esc(a.target || '-') + '</td>' +
        '<td class="max-w-md text-xs text-gray-500">' + esc(a.detail || '-') + '</td></tr>';
    }).join('') + '</tbody></table></div>';
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

/* ==================== 初始化 ==================== */
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
  // 一键体验：URL 带 ?person=<id> 时自动以该身份登录（便于演示与验收测试直达内页）
  const urlPerson = new URLSearchParams(location.search).get('person');
  if (urlPerson) {
    history.replaceState(null, '', location.pathname + location.hash);
    doLogin(Number(urlPerson));
  } else if (state.token && state.person) enterApp();
  else bootLogin();
});
