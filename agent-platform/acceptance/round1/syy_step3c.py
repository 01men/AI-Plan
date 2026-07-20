# -*- coding: utf-8 -*-
import json, urllib.request, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE='http://127.0.0.1:8000'
T='c51cb228793f468192f960fb12ab45f2'
LOCK_COUNT=0

def req(method, path, body=None, retry=1):
    global LOCK_COUNT
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE+path, data=data, method=method,
        headers={'Authorization':'Bearer '+T, 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')
        if e.code==500 and 'locked' in txt and retry>0:
            LOCK_COUNT+=1
            print(f'  [database is locked 重试 #{LOCK_COUNT}] {method} {path}')
            time.sleep(0.5)
            return req(method, path, body, retry-1)
        print(f'  HTTP {e.code}: {txt[:400]}')
        return e.code, txt

print('=== 步骤3: 工作区#7 Agent区 @数字员工 派活 ===')
code, r = req('POST','/api/workspaces/7/messages', {
    'zone':'agent',
    'content':'@财务经营数字员工 请把今天各平台经营数据汇总成日报初稿，包含销售额、订单量、环比变化，下午5点前给我。'
})
print('发消息返回:', code)
print(json.dumps(r, ensure_ascii=False, indent=1)[:2500])

print('\n=== 工作区#7 消息流(agent区) ===')
_, msgs = req('GET','/api/workspaces/7/messages?zone=agent')
print(json.dumps(msgs, ensure_ascii=False, indent=1)[:2500])

print('\n=== 工作区#7 关联任务 ===')
_, tasks = req('GET','/api/tasks?workspace_id=7')
print(json.dumps(tasks, ensure_ascii=False, indent=1)[:2500])
print('\nLOCK_COUNT =', LOCK_COUNT)
