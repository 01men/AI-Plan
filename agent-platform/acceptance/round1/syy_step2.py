# -*- coding: utf-8 -*-
import json, urllib.request, sys, io
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
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')
        if e.code==500 and 'locked' in txt and retry>0:
            LOCK_COUNT+=1
            print(f'  [database is locked 重试 #{LOCK_COUNT}] {method} {path}')
            return req(method, path, body, retry-1)
        print(f'  HTTP {e.code}: {txt[:300]}')
        return e.code, txt

# 1. 场景库：找一个“待立项”场景
_, sc = req('GET','/api/scenarios')
items = sc if isinstance(sc,list) else sc.get('items', sc.get('scenarios',[]))
pending = [s for s in items if s.get('status')=='待立项']
print('待立项场景数:', len(pending))
for s in pending[:5]:
    print('  ', s.get('id'), s.get('name'), '| wave:', s.get('wave'), '| owner:', s.get('owner_id'), '| agents:', s.get('agent_ids'))
target = pending[0]
sid = target['id']
print('\n=== 步骤2: 敏捷立项 场景#%s %s ===' % (sid, target['name']))
code, r = req('POST', f'/api/scenarios/{sid}/initiate')
print('立项返回:', code, json.dumps(r, ensure_ascii=False)[:600] if not isinstance(r,str) else r)

# 确认场景状态 & workspace
_, sc2 = req('GET','/api/scenarios')
items2 = sc2 if isinstance(sc2,list) else sc2.get('items', sc2.get('scenarios',[]))
me = [s for s in items2 if s['id']==sid][0]
print('\n立项后场景状态:', me.get('status'), '| workspace_id:', me.get('workspace_id'))
wid = me.get('workspace_id')
if wid:
    _, ws = req('GET', f'/api/workspaces/{wid}')
    print('\n=== 工作区详情 ===')
    print(json.dumps(ws, ensure_ascii=False, indent=1)[:2500])
print('\nLOCK_COUNT =', LOCK_COUNT)
