from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from app.adapters import AdapterError, for_resource
from app.config import Config
from app.database import session
from app.security import PolicyError, issue_token, require_policy


STATES = {'Draft', 'AwaitingApproval', 'Queued', 'Dispatched', 'Running', 'InputRequired', 'Review', 'Completed', 'Rework', 'Degraded', 'HumanTakeover', 'Cancelled'}
TRANSITIONS = {
    'Draft': {'AwaitingApproval', 'Queued', 'Cancelled'}, 'AwaitingApproval': {'Queued', 'Cancelled'},
    'Queued': {'Dispatched', 'Degraded', 'Cancelled'}, 'Dispatched': {'Running', 'InputRequired', 'Review', 'Degraded', 'Cancelled'},
    'Running': {'InputRequired', 'Review', 'Degraded', 'Cancelled'}, 'InputRequired': {'Queued', 'Cancelled'},
    'Review': {'Completed', 'Rework', 'Degraded'}, 'Rework': {'Queued', 'Cancelled'},
    'Degraded': {'HumanTakeover', 'Queued', 'Cancelled'}, 'HumanTakeover': {'Completed', 'Cancelled'},
}


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def later(seconds): return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec='seconds')
def jid(): return str(uuid.uuid4())
def dump(v): return json.dumps(v, ensure_ascii=False, sort_keys=True)
def load(v, default=None): return json.loads(v) if v else (default if default is not None else {})


class ControlError(RuntimeError): pass


class ControlPlane:
    def __init__(self, config: Config): self.config = config

    def audit(self, conn, actor, action, target, detail, correlation_id=None):
        conn.execute('INSERT INTO audit_logs(correlation_id,actor,action,target,detail,created_at) VALUES(?,?,?,?,?,?)',
                     (correlation_id, actor, action, target, dump(detail), now()))

    def resource(self, resource_id):
        with session(self.config.db_path) as conn:
            row = conn.execute('SELECT * FROM resources WHERE id=?', (resource_id,)).fetchone()
            if not row: raise ControlError('资源不存在')
            return dict(row)

    def list_resources(self):
        with session(self.config.db_path) as conn:
            return [dict(x) for x in conn.execute('SELECT * FROM resources ORDER BY updated_at DESC')]

    def register(self, body, actor):
        required = ('type', 'name', 'owner', 'execution_domain')
        if any(not str(body.get(k, '')).strip() for k in required): raise ControlError('type、name、owner、execution_domain 必填')
        if body['type'] not in {'agent','knowledge_base','skill','mcp'}: raise ControlError('资源类型无效')
        rid, ts = jid(), now()
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('''INSERT INTO resources(id,type,name,owner,endpoint,auth_profile_ref,execution_domain,status,capability_manifest,data_scope_template,tool_policy,write_policy,cost_policy,health_profile,version,trust_level,approval_required,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,'registered',?,?,?,?,?,?,?,?,?,?,?)''',
                         (rid, body['type'], body['name'].strip(), body['owner'].strip(), body.get('endpoint','').rstrip('/'), body.get('auth_profile_ref',''), body['execution_domain'], dump({'adapter':body.get('adapter','native_a2a')}), dump(body.get('data_scope_template',[])), dump(body.get('tool_policy',[])), body.get('write_policy','forbid'), dump(body.get('cost_policy',{})), dump(body.get('health_profile',{})), body.get('version',''), body.get('trust_level','sandbox'), 1 if body.get('approval_required',True) else 0, ts, ts))
            self.audit(conn, actor, '登记资源', rid, {'name':body['name'],'type':body['type']})
            conn.commit()
        return self.resource(rid)

    def discover(self, resource_id, actor):
        resource = self.resource(resource_id)
        if resource['type'] != 'agent': raise ControlError('仅 Agent 支持 Agent Card 发现')
        try: manifest = for_resource(resource).capabilities(resource)
        except AdapterError as exc: raise ControlError(str(exc)) from exc
        if not manifest.get('name') or not (manifest.get('capabilities') or manifest.get('skills')): raise ControlError('Agent Card 缺少 name 或 capabilities/skills')
        version, ts = str(manifest.get('version','unknown')), now()
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('UPDATE resources SET capability_manifest=?,version=?,status="discovered",updated_at=? WHERE id=?', (dump(dict(manifest, adapter=load(resource['capability_manifest']).get('adapter','native_a2a'))),version,ts,resource_id))
            conn.execute('INSERT INTO capability_manifests(resource_id,version,source,payload,discovered_at) VALUES(?,?,?,?,?)', (resource_id,version,resource['endpoint']+'/.well-known/agent-card.json',dump(manifest),ts))
            self.audit(conn,actor,'发现能力',resource_id,{'version':version})
            conn.commit()
        return {'ok':True,'manifest':manifest,'resource':self.resource(resource_id)}

    def sandbox_validate(self, resource_id, actor):
        resource = self.resource(resource_id)
        if resource['status'] not in {'discovered','sandbox','paused'}: raise ControlError('资源尚未完成发现或当前不可验证')
        card = load(resource['capability_manifest'])
        checks = {'reachable': bool(resource.get('endpoint')), 'authenticated': True, 'executable': bool(card), 'capacity': bool(card.get('capabilities') or card.get('skills'))}
        if not all(checks.values()): raise ControlError('沙箱验证失败：'+dump(checks))
        with session(self.config.db_path) as conn:
            conn.execute('UPDATE resources SET status="sandbox",last_verified_at=?,updated_at=? WHERE id=?',(now(),now(),resource_id)); self.audit(conn,actor,'沙箱验证',resource_id,checks); conn.commit()
        return {'ok':True,'side_effect_free':True,'checks':checks}

    def enable(self, resource_id, actor, approval_ticket_id=''):
        resource = self.resource(resource_id)
        if resource['status'] not in {'sandbox','paused'}: raise ControlError('资源必须先完成无副作用沙箱验证')
        if resource['approval_required'] and not approval_ticket_id: raise ControlError('启用资源需要审批票据')
        with session(self.config.db_path) as conn:
            conn.execute('UPDATE resources SET status="enabled",paused_reason=NULL,updated_at=? WHERE id=?',(now(),resource_id)); self.audit(conn,actor,'启用资源',resource_id,{'approval_ticket_id':approval_ticket_id}); conn.commit()
        return self.resource(resource_id)

    def pause(self, resource_id, actor, reason=''):
        with session(self.config.db_path) as conn:
            conn.execute('UPDATE resources SET status="paused",paused_reason=?,updated_at=? WHERE id=?',(reason,now(),resource_id)); self.audit(conn,actor,'暂停资源',resource_id,{'reason':reason}); conn.commit()
        return self.resource(resource_id)

    def unbind(self, resource_id, actor):
        with session(self.config.db_path) as conn:
            active = conn.execute("SELECT count(*) FROM ext_agent_runs WHERE resource_id=? AND state IN ('queued','dispatched','running','input_required')",(resource_id,)).fetchone()[0]
            if active: raise ControlError('存在在途任务，须先取消或人工接手')
            conn.execute('UPDATE resources SET status="unbound",updated_at=? WHERE id=?',(now(),resource_id)); self.audit(conn,actor,'解绑资源',resource_id,{}); conn.commit()
        return self.resource(resource_id)

    def create_ticket(self, body, actor):
        tid=jid()
        with session(self.config.db_path) as conn:
            conn.execute('INSERT INTO approval_tickets(id,contract_id,level,requested_by,reason,created_at) VALUES(?,?,?,?,?,?)',(tid,body.get('contract_id'),body.get('level','L1'),actor,body.get('reason','人工审核'),now())); self.audit(conn,actor,'创建审批票据',tid,body); conn.commit()
        return {'id':tid,'status':'pending'}

    def decide_ticket(self, ticket_id, actor, approve):
        with session(self.config.db_path) as conn:
            row=conn.execute('SELECT * FROM approval_tickets WHERE id=?',(ticket_id,)).fetchone()
            if not row or row['status']!='pending': raise ControlError('审批票据不存在或已处理')
            status='approved' if approve else 'rejected'; conn.execute('UPDATE approval_tickets SET status=?,approved_by=?,decided_at=? WHERE id=?',(status,actor,now(),ticket_id)); self.audit(conn,actor,'审批票据',ticket_id,{'approved':approve}); conn.commit()
        return {'id':ticket_id,'status':status}

    def create_contract(self, body, actor):
        resource=self.resource(body.get('resource_id',''))
        if resource['status']!='enabled': raise ControlError('资源未启用，不能派发')
        contract={k:body.get(k, [] if k in {'skills','tools','data_scope'} else '') for k in ('role','skills','tools','data_scope','write_policy','runtime')}
        contract['write_policy'] = contract['write_policy'] or 'forbid'; contract['approval_ticket_id']=body.get('approval_ticket_id','')
        try: require_policy(contract)
        except PolicyError as exc: raise ControlError(str(exc)) from exc
        idem=str(body.get('idempotency_key','')).strip()
        if not idem: raise ControlError('idempotency_key 必填')
        if body.get('approval_ticket_id'):
            with session(self.config.db_path) as c:
                t=c.execute('SELECT status FROM approval_tickets WHERE id=?',(body['approval_ticket_id'],)).fetchone()
                if not t or t['status']!='approved': raise ControlError('任务关联审批票据未通过')
        cid, outbox, ts=jid(),jid(),now()
        runtime=dict(body.get('runtime') or {}); runtime.setdefault('timeout_seconds',self.config.default_timeout_seconds); runtime.setdefault('fallback','human_takeover')
        token=issue_token({'contract_id':cid,'resource_id':resource['id'],'data_scope':contract['data_scope'],'tools':contract['tools'],'write_policy':contract['write_policy']},self.config.signing_key,self.config.issuer)
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            existing=conn.execute('SELECT * FROM task_contracts WHERE idempotency_key=?',(idem,)).fetchone()
            if existing: conn.commit(); return {'idempotent':True,'contract':dict(existing)}
            conn.execute('''INSERT INTO task_contracts(id,idempotency_key,subject,initiator,resource_id,role,skills,tools,data_scope,write_policy,runtime,authorization,state,input_payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'Queued',?,?,?)''',
                         (cid,idem,body.get('subject','未命名行动'),actor,resource['id'],contract['role'],dump(contract['skills']),dump(contract['tools']),dump(contract['data_scope']),contract['write_policy'],dump(runtime),token,dump(body.get('input_payload',{})),ts,ts))
            conn.execute('INSERT INTO dispatch_outbox(id,contract_id,kind,payload,available_at,created_at,updated_at) VALUES(?,?,"dispatch",?,?,?,?)',(outbox,cid,dump({'contract_id':cid}),ts,ts,ts))
            self.audit(conn,actor,'创建任务契约',cid,{'resource_id':resource['id'],'subject':body.get('subject'),'idempotency_key':idem},cid); conn.commit()
        return {'idempotent':False,'contract_id':cid,'state':'Queued'}

    def contract(self, contract_id):
        with session(self.config.db_path) as conn:
            row=conn.execute('SELECT * FROM task_contracts WHERE id=?',(contract_id,)).fetchone()
            if not row: raise ControlError('任务契约不存在')
            data=dict(row); data.update({k:load(data[k]) for k in ('skills','tools','data_scope','runtime','input_payload')}); return data

    def _transition(self, conn, contract_id, new, actor='system', detail=None):
        row=conn.execute('SELECT state,version FROM task_contracts WHERE id=?',(contract_id,)).fetchone()
        if not row: raise ControlError('任务契约不存在')
        if new not in TRANSITIONS.get(row['state'],set()): raise ControlError(f'不允许状态迁移 {row["state"]} → {new}')
        conn.execute('UPDATE task_contracts SET state=?,version=?,updated_at=? WHERE id=?',(new,row['version']+1,now(),contract_id)); self.audit(conn,actor,'状态迁移',contract_id,{'from':row['state'],'to':new,'detail':detail or {}},contract_id)

    def process_outbox(self, worker_id='local-worker', limit=20):
        results=[]
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            rows=[dict(x) for x in conn.execute("SELECT * FROM dispatch_outbox WHERE status='pending' AND available_at<=? AND (lease_until IS NULL OR lease_until<?) ORDER BY created_at LIMIT ?",(now(),now(),limit))]
            for row in rows: conn.execute('UPDATE dispatch_outbox SET status="leased",leased_by=?,lease_until=?,updated_at=? WHERE id=?',(worker_id,later(30),now(),row['id']))
            conn.commit()
        for row in rows:
            try: results.append(self._dispatch(row,worker_id))
            except Exception as exc: results.append({'outbox_id':row['id'],'ok':False,'error':str(exc)})
        return results

    def _dispatch(self,outbox,worker_id):
        contract=self.contract(outbox['contract_id']); resource=self.resource(contract['resource_id'])
        if resource['status']!='enabled': raise ControlError('资源已不可派发')
        try:
            result=for_resource(resource).send(resource,contract,contract['authorization'])
            external=str(result.get('run_id') or result.get('id') or result.get('task_id') or '')
            if not external: raise ControlError('远端未返回 run_id')
        except (AdapterError,ControlError) as exc:
            return self._fail_dispatch(outbox,contract,str(exc))
        rid=jid()
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            # 驳回重做必须先显式重新排队，统一走与新任务相同的派发路径。
            if contract['state'] == 'Rework':
                self._transition(conn, contract['id'], 'Queued', detail={'reason':'review_rework'})
            self._transition(conn,contract['id'],'Dispatched',detail={'external_run_id':external})
            conn.execute('''INSERT INTO ext_agent_runs(id,contract_id,resource_id,external_run_id,state,created_at,updated_at)
                         VALUES(?,?,?,?,"dispatched",?,?)
                         ON CONFLICT(contract_id) DO UPDATE SET external_run_id=excluded.external_run_id,
                         state='dispatched',last_sequence=0,error=NULL,updated_at=excluded.updated_at''',(rid,contract['id'],resource['id'],external,now(),now()))
            conn.execute('UPDATE dispatch_outbox SET status="sent",external_run_id=?,lease_until=NULL,updated_at=? WHERE id=?',(external,now(),outbox['id'])); conn.commit()
        return {'outbox_id':outbox['id'],'ok':True,'run_id':rid,'external_run_id':external}

    def _fail_dispatch(self,outbox,contract,error):
        attempts=int(outbox['attempts'])+1
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            if attempts>=3:
                self._transition(conn,contract['id'],'Degraded',detail={'error':error}); conn.execute('UPDATE dispatch_outbox SET status="dead",attempts=?,error=?,lease_until=NULL,updated_at=? WHERE id=?',(attempts,error,now(),outbox['id'])); conn.execute('INSERT INTO dead_letters(outbox_id,reason,payload,created_at) VALUES(?,?,?,?)',(outbox['id'],error,outbox['payload'],now()))
            else: conn.execute('UPDATE dispatch_outbox SET status="pending",attempts=?,error=?,lease_until=NULL,available_at=?,updated_at=? WHERE id=?',(attempts,error,later(2**attempts),now(),outbox['id']))
            conn.commit()
        return {'outbox_id':outbox['id'],'ok':False,'attempts':attempts,'error':error}

    def receive_event(self, run_id, body, actor='remote-agent'):
        event_id=str(body.get('event_id','')); sequence=int(body.get('sequence',0)); typ=str(body.get('event_type',''))
        if not event_id or sequence<1 or typ not in {'started','progress','input_required','deliverable','failed','cancelled'}: raise ControlError('事件 event_id、sequence、event_type 无效')
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE'); run=conn.execute('SELECT * FROM ext_agent_runs WHERE id=?',(run_id,)).fetchone()
            if not run: raise ControlError('运行记录不存在')
            previous=conn.execute('SELECT 1 FROM run_events WHERE run_id=? AND event_id=?',(run_id,event_id)).fetchone()
            if previous: conn.commit(); return {'ok':True,'idempotent':True}
            if sequence<=run['last_sequence']: conn.rollback(); raise ControlError('乱序事件不能覆盖较新状态')
            conn.execute('INSERT INTO run_events(run_id,event_id,sequence,event_type,payload,created_at) VALUES(?,?,?,?,?,?)',(run_id,event_id,sequence,typ,dump(body),now()))
            state_map={'started':'Running','progress':'Running','input_required':'InputRequired','deliverable':'Review','failed':'Degraded','cancelled':'Cancelled'}
            self._transition(conn,run['contract_id'],state_map[typ],actor,body)
            run_state={'started':'running','progress':'running','input_required':'input_required','deliverable':'review','failed':'degraded','cancelled':'cancelled'}[typ]
            conn.execute('UPDATE ext_agent_runs SET state=?,last_sequence=?,updated_at=? WHERE id=?',(run_state,sequence,now(),run_id))
            if typ=='deliverable':
                artifact=body.get('artifact') or body.get('content')
                if not isinstance(artifact,str) or not artifact.strip(): raise ControlError('交付事件必须包含 artifact')
                conn.execute('INSERT INTO artifacts(id,contract_id,run_id,kind,content,provenance,created_at) VALUES(?,?,?,?,?,?,?)',(jid(),run['contract_id'],run_id,'deliverable',artifact[:200000],dump(body.get('provenance',{})),now()))
            conn.commit()
        return {'ok':True,'idempotent':False,'state':state_map[typ]}

    def review(self, contract_id, actor, approve, comment=''):
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE'); row=conn.execute('SELECT state FROM task_contracts WHERE id=?',(contract_id,)).fetchone()
            if not row or row['state']!='Review': raise ControlError('仅待审核任务可审核')
            self._transition(conn,contract_id,'Completed' if approve else 'Rework',actor,{'comment':comment}); conn.execute('UPDATE artifacts SET status=?,reviewer=?,review_comment=?,reviewed_at=? WHERE contract_id=? AND status="pending_review"',('accepted' if approve else 'rework',actor,comment,now(),contract_id))
            if not approve: conn.execute('INSERT INTO dispatch_outbox(id,contract_id,kind,payload,available_at,created_at,updated_at) VALUES(?,?,"dispatch",?,?,?,?)',(jid(),contract_id,dump({'rework':comment}),now(),now(),now()))
            conn.commit()
        return {'ok':True,'state':'Completed' if approve else 'Rework'}

    def provide_input(self,contract_id,actor,payload):
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE'); self._transition(conn,contract_id,'Queued',actor,{'input':payload}); conn.execute('UPDATE task_contracts SET input_payload=?,updated_at=? WHERE id=?',(dump(payload),now(),contract_id)); conn.execute('INSERT INTO dispatch_outbox(id,contract_id,kind,payload,available_at,created_at,updated_at) VALUES(?,?,"resume",?,?,?,?)',(jid(),contract_id,dump(payload),now(),now(),now())); conn.commit()
        return {'ok':True,'state':'Queued'}

    def takeover(self,contract_id,actor,summary):
        with session(self.config.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE'); self._transition(conn,contract_id,'HumanTakeover',actor,{'summary':summary}); conn.execute('INSERT INTO artifacts(id,contract_id,kind,content,provenance,status,reviewer,reviewed_at,created_at) VALUES(?,?,?,?,?,"accepted",?,?,?)',(jid(),contract_id,'human_takeover',summary,dump({'actor':actor}),actor,now(),now())); conn.commit()
        return {'ok':True,'state':'HumanTakeover'}

    def runs(self):
        with session(self.config.db_path) as conn: return [dict(x) for x in conn.execute('SELECT * FROM ext_agent_runs ORDER BY updated_at DESC')]
