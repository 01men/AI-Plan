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

print('=== 步骤4a: 驳回任务#8 ===')
code, r = req('POST','/api/tasks/8/review', {'action':'reject','comment':'内容太笼统：没有分平台明细，环比口径也没写清，请补充后重做。'})
print('驳回返回:', code)
print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])

print('\n=== 驳回后任务状态 ===')
_, tasks = req('GET','/api/tasks?workspace_id=7')
for t in (tasks if isinstance(tasks,list) else tasks.get('items',[])):
    print('  task#%s [%s] attempts字段:%s review_comment:%s' % (t['id'], t['status'], t.get('attempts','-'), (t.get('review_comment') or '')[:40]))
    print('  deliverable前80字:', (t.get('deliverable') or '')[:80].replace('\n',' '))

print('\n=== 驳回后工作区消息(看重做痕迹) ===')
_, msgs = req('GET','/api/workspaces/7/messages?zone=agent')
for m in (msgs if isinstance(msgs,list) else msgs.get('items',[])):
    print('  #%s [%s/%s] %s' % (m['id'], m['sender_name'], m['msg_type'], m['content'][:60].replace('\n',' ')))

print('\n=== 步骤4b: 审核通过任务#8 ===')
code, r = req('POST','/api/tasks/8/review', {'action':'approve','comment':'分平台明细已补齐，通过。'})
print('通过返回:', code)
print(json.dumps(r, ensure_ascii=False, indent=1)[:1500])

_, tasks = req('GET','/api/tasks?workspace_id=7')
for t in (tasks if isinstance(tasks,list) else tasks.get('items',[])):
    print('最终 task#%s [%s] done_at:%s' % (t['id'], t['status'], t.get('done_at')))
print('\nLOCK_COUNT =', LOCK_COUNT)
