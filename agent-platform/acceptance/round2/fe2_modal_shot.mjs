// 第二轮验收辅助：通过 CDP 打开激励申报弹窗并截图（无头 Chrome 无法点击，故用 DevTools 协议驱动）
// 用法: node fe2_modal_shot.mjs
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const CDP_HTTP = 'http://127.0.0.1:9223';
const PAGE_URL = 'http://127.0.0.1:8000/?person=1#/governance/incentives';
const OUT_DIR = dirname(fileURLToPath(import.meta.url));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const ver = await (await fetch(CDP_HTTP + '/json/version')).json();
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let seq = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    else if (m.method) events.push(m);
  };
  const send = (method, params = {}, sessionId) => new Promise((res) => {
    const id = ++seq;
    pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params, sessionId }));
  });

  const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' }).then((m) => {
    if (!m.result) throw new Error('createTarget failed: ' + JSON.stringify(m));
    return m;
  });
  const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Page.enable', {}, sessionId);
  await send('Runtime.enable', {}, sessionId);
  await send('Page.navigate', { url: PAGE_URL }, sessionId);
  await sleep(6000); // 等登录 + 视图数据渲染

  const evalJs = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }, sessionId);
    return r.result && r.result.result ? r.result.result.value : undefined;
  };
  const shot = async (name) => {
    const r = await send('Page.captureScreenshot', { format: 'png' }, sessionId);
    writeFileSync(join(OUT_DIR, name), Buffer.from(r.result.data, 'base64'));
    console.log('saved', name);
  };

  // 打开申报弹窗（直接调用页内函数，等价于点击"+ 申报激励"）
  await evalJs('openIncentiveModal()');
  await sleep(500);
  console.log('hint(火花奖):', await evalJs("document.getElementById('ni-tier-hint') && document.getElementById('ni-tier-hint').textContent"));
  await shot('fe2_gov_incentive_modal_spark.png');

  // 联动切换到金扳手奖
  await evalJs("var s=document.getElementById('ni-type'); s.value='金扳手奖'; s.dispatchEvent(new Event('change'));");
  await sleep(300);
  console.log('hint(金扳手奖):', await evalJs("document.getElementById('ni-tier-hint').textContent"));
  await shot('fe2_gov_incentive_modal_gold.png');

  // 切换到种子基金
  await evalJs("var s=document.getElementById('ni-type'); s.value='种子基金'; s.dispatchEvent(new Event('change'));");
  await sleep(300);
  console.log('hint(种子基金):', await evalJs("document.getElementById('ni-tier-hint').textContent"));

  await send('Target.closeTarget', { targetId });
  ws.close();
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
