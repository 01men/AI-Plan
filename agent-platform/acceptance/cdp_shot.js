/* 一次性 CDP 截图工具：打开 URL → 等待加载 → 执行 JS 表达式 → 截图
   同时采集浏览器 console/页面异常，随截图落 <outPng>.console.json 留档。
   用法: node cdp_shot.js <url> <outPng> [evalExpr] [settleMs] */
const { spawn } = require('child_process');
const fs = require('fs');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9223;
const [url, outPng, evalExpr, settleMsArg] = process.argv.slice(2);
const settleMs = Number(settleMsArg || 4000);
const consoleLog = [];   // {type, level, text, url?, line?}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function getTarget() {
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json`);
      const list = await res.json();
      const page = list.find(t => t.type === 'page' && t.url.startsWith('http'));
      if (page) return page;
    } catch (e) { /* chrome 还没起来 */ }
    await sleep(500);
  }
  throw new Error('找不到 CDP page target');
}

async function main() {
  const chrome = spawn(CHROME, [
    '--headless', '--disable-gpu', `--remote-debugging-port=${PORT}`,
    '--window-size=1600,950', '--user-data-dir=/tmp/chrome-r4-cdp', url,
  ], { stdio: 'ignore' });
  try {
    const target = await getTarget();
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    let seq = 0;
    const pending = new Map();
    const send = (method, params) => new Promise((resolve, reject) => {
      const id = ++seq;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params: params || {} }));
    });
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        const p = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
      } else if (msg.method === 'Runtime.consoleAPICalled') {
        const p = msg.params;
        consoleLog.push({ type: 'console', level: p.type,
          text: p.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 500),
          url: p.stackTrace?.callFrames?.[0]?.url, line: p.stackTrace?.callFrames?.[0]?.lineNumber });
      } else if (msg.method === 'Runtime.exceptionThrown') {
        const d = msg.params.exceptionDetails;
        consoleLog.push({ type: 'exception', level: 'error',
          text: (d.exception?.description || d.text || '').slice(0, 500),
          url: d.url, line: d.lineNumber });
      }
    };
    await new Promise(r => { ws.onopen = r; });
    await send('Runtime.enable');
    await send('Page.enable');
    await sleep(settleMs);   // 等页面渲染与 API 返回
    if (evalExpr) {
      const r = await send('Runtime.evaluate', { expression: evalExpr, awaitPromise: true });
      if (r.exceptionDetails) console.error('EVAL ERROR:', JSON.stringify(r.exceptionDetails).slice(0, 500));
      await sleep(1200);     // 等弹窗渲染
    }
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(outPng, Buffer.from(shot.data, 'base64'));
    const errors = consoleLog.filter(e => e.level === 'error');
    fs.writeFileSync(outPng + '.console.json', JSON.stringify(
      { url, captured_at: new Date().toISOString(), error_count: errors.length, entries: consoleLog }, null, 2));
    console.log('saved:', outPng);
    console.log(`console: ${errors.length} error(s), ${consoleLog.length - errors.length} other entr(ies) -> ${outPng}.console.json`);
    if (errors.length) errors.forEach(e => console.error('CONSOLE ERROR:', e.text));
    ws.close();
  } finally {
    chrome.kill('SIGKILL');
  }
}
main().catch(e => { console.error(e.message); process.exit(1); });
