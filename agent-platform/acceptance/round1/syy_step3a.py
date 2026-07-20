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

_, ws = req('GET','/api/workspaces/7')
print('=== 工作区#7 详情 ===')
print(json.dumps(ws, ensure_ascii=False, indent=1))

_, wslist = req('GET','/api/workspaces')
print('\n=== 工作区列表(前3) ===')
print(json.dumps(wslist, ensure_ascii=False, indent=1)[:1500])
print('\nLOCK_COUNT =', LOCK_COUNT)
