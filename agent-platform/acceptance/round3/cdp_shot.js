// CDP 截图：任务中心（勾选/未勾选"只看待我审核"）、组织、路线图
const fs = require('fs');
const BASE = 'http://127.0.0.1:9333';
const OUT = __dirname;

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 0;
    const pending = new Map();
    ws.onopen = () => resolve(api);
    ws.onerror = (e) => reject(new Error('ws error'));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
      }
    };
    const api = {
      send(method, params = {}) {
        return new Promise((res, rej) => {
          const mid = ++id;
          pending.set(mid, { res, rej });
          ws.send(JSON.stringify({ id: mid, method, params }));
        });
      },
      close() { ws.close(); }
    };
  });
}

async function newTab(url) {
  const r = await fetch(`${BASE}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  return r.json();
}

async function waitFor(client, expr, timeoutMs = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const r = await client.send('Runtime.evaluate', { expression: expr, returnByValue: true });
    if (r.result && r.result.value) return true;
    await new Promise(s => setTimeout(s, 400));
  }
  return false;
}

async function shot(client, file) {
  const r = await client.send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(`${OUT}/${file}`, Buffer.from(r.data, 'base64'));
  console.log('saved', file);
}

(async () => {
  // 1) 任务中心：勾选"只看待我审核"
  let tab = await newTab('http://127.0.0.1:8000/?person=6#/tasks');
  let c = await connect(tab.webSocketDebuggerUrl);
  await c.send('Page.enable');
  let ok = await waitFor(c, "document.querySelectorAll('.task-card').length>0 && typeof toggleTaskOnlyMine==='function'");
  console.log('tasks loaded:', ok);
  await c.send('Runtime.evaluate', { expression: 'toggleTaskOnlyMine(true)' });
  await new Promise(s => setTimeout(s, 1200));
  const info = await c.send('Runtime.evaluate', {
    expression: "JSON.stringify({cards:[...document.querySelectorAll('.task-card')].map(e=>e.querySelector('.text-sm').textContent), cols:[...document.querySelectorAll('.kanban-col')].map(e=>e.querySelector('.font-bold').textContent)})",
    returnByValue: true
  });
  console.log('toggle-on board:', info.result.value);
  await shot(c, 'daishuan_tasks_onlymine.png');
  await c.send('Runtime.evaluate', { expression: 'toggleTaskOnlyMine(false)' });
  await new Promise(s => setTimeout(s, 1200));
  await shot(c, 'daishuan_tasks_all.png');
  c.close();
  await fetch(`${BASE}/json/close/${tab.id}`);

  // 2) 组织
  tab = await newTab('http://127.0.0.1:8000/?person=6#/org');
  c = await connect(tab.webSocketDebuggerUrl);
  await c.send('Page.enable');
  await waitFor(c, "document.body.innerText.includes('平台')");
  await new Promise(s => setTimeout(s, 800));
  await shot(c, 'daishuan_org.png');
  c.close();
  await fetch(`${BASE}/json/close/${tab.id}`);

  // 3) 路线图
  tab = await newTab('http://127.0.0.1:8000/?person=6#/roadmap');
  c = await connect(tab.webSocketDebuggerUrl);
  await c.send('Page.enable');
  await waitFor(c, "document.body.innerText.includes('里程碑') || document.body.innerText.includes('筑基')");
  await new Promise(s => setTimeout(s, 800));
  await shot(c, 'daishuan_roadmap.png');
  c.close();
  await fetch(`${BASE}/json/close/${tab.id}`);
  console.log('done');
})().catch(e => { console.error(e); process.exit(1); });
