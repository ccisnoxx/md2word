"""按已批准窗口顺序切换；失败由主会话核对写入状态并执行旧JSON回退。"""
import sys;sys.path.insert(0,'/root/md2word-releases/b8b2779a-list-loading/window');sys.path.insert(0,'/root/md2word-releases/b8b2779a-list-loading/release-ops')
from window_lib import *
os.umask(0o077)
from window_helpers import filesystem_manifest,compare_filesystems
from datetime import datetime,timezone
import urllib.request,tempfile
state=json.loads((W/'state.json').read_text());assert state['stage']=='rehearsal_passed'
assert json.loads((W/'rehearsal-result.json').read_text())['passed']
assert (datetime.fromisoformat(state['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()>15*60,'窗口剩余不足15分钟，不开始生产迁移'
ng=json.loads((P/'nginx-review.json').read_text());site=Path(ng['active_site']);freeze_bytes=site.read_bytes();assert hashlib.sha256(freeze_bytes).hexdigest()==ng['candidates']['freeze']['sha256']
for n,h in json.loads((P/'release-ops-manifest.json').read_text())['files'].items():assert hashlib.sha256((R/'release-ops'/n).read_bytes()).hexdigest()==h
for role in ['api','worker']:assert not json.loads(subprocess.check_output(['docker','inspect',container(role)],text=True))[0]['State']['Running']
for role in ['mysql','redis']:
 now=json.loads(subprocess.check_output(['docker','inspect',container(role)],text=True))[0];before=json.loads((W/(role+'-inspect.json')).read_text());assert now['Id']==before['Id'] and now['Image']==before['Image'] and now['State']['StartedAt']==before['State']['StartedAt'] and now['State']['Running']
q='SELECT (SELECT COUNT(*) FROM information_schema.INNODB_TRX),(SELECT COUNT(*) FROM performance_schema.replication_connection_status);'
rp=subprocess.run(['docker','exec',container('mysql'),'sh','-c','export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot --batch --skip-column-names -e "$1"','--',q],text=True,capture_output=True,check=True);assert [int(x) for x in rp.stdout.split()]==[0,0]
op('pre-production-all',OLD,['/ops/snapshot.py','snapshot',*target(),'--include-derived']);compare_snapshot('pre-production-unchanged.json','source-all','pre-production-all')
api=json.loads((W/'api-inspect.json').read_text());var=Path(next(m['Source'] for m in api['Mounts'] if m['Destination']=='/app/var'))
assert compare_filesystems(json.loads((W/'fs-var-source.json').read_text()),filesystem_manifest(var))['equal']
for name in json.loads((W/'config-backup-files.json').read_text()):
 assert compare_filesystems(filesystem_manifest(Path(name)),filesystem_manifest(W/'restore-config'/name.lstrip('/')))['equal'],'运行配置在窗口内变化'

# 启动前核对有效配置，避免先启动写者后才发现数据库/对象挂载漂移。
import shlex
files=json.loads((P/'compose-files.json').read_text())
argv=['docker','compose','-p',PROJECT]+[x for f in files for x in ['-f',f]]
rendered=json.loads(subprocess.check_output(argv+['config','--format','json'],cwd=B['compose_workdir'],text=True))
image_ref=json.loads((P/'compose-review.json').read_text())['image_ref']
resolved_image=json.loads(subprocess.check_output(['docker','image','inspect',image_ref],text=True))[0]
assert resolved_image['Id']==NEW,'固定引用未解析到已批准镜像'
image_config=resolved_image['Config']
proof=[]
def command_value(value, default):
    value=default if value is None else value
    return shlex.split(value) if isinstance(value,str) else value
for role in ['api','worker']:
    svc=rendered['services'][role];old=json.loads((W/(role+'-inspect.json')).read_text())
    assert svc['image']==json.loads((P/'compose-review.json').read_text())['image_ref']
    effective=dict(x.split('=',1) for x in image_config['Env'])
    for key,value in svc.get('environment',{}).items():
        if value is None:effective.pop(key,None)
        else:effective[key]=str(value)
    expected=env(role);expected.update(APP_VERSION='b8b2779a',DEPLOYMENT_ID=json.loads((P/'compose-review.json').read_text())['deployment_id'])
    assert effective==expected,'启动前有效环境不符'
    original_mounts=sorted((m['Type'],m.get('Name') if m['Type']=='volume' else m['Source'],m['Destination'],m['RW']) for m in old['Mounts'])
    intended_mounts=sorted((m['type'],rendered['volumes'][m['source']]['name'] if m['type']=='volume' else m['source'],m['target'],not m.get('read_only',False)) for m in svc.get('volumes',[]))
    assert intended_mounts==original_mounts,'启动前挂载不符'
    assert command_value(svc.get('command'),image_config.get('Cmd'))==old['Config'].get('Cmd')
    assert command_value(svc.get('entrypoint'),image_config.get('Entrypoint'))==old['Config'].get('Entrypoint')
    assert svc.get('user',image_config.get('User',''))==old['Config'].get('User','')
    assert svc.get('working_dir',image_config.get('WorkingDir',''))==old['Config'].get('WorkingDir','')
    assert sorted(rendered['networks'][n]['name'] for n in svc['networks'])==sorted(old['NetworkSettings']['Networks'])
    intended_ports=sorted((str(x['target'])+'/'+x.get('protocol','tcp'),x.get('host_ip','0.0.0.0'),str(x['published'])) for x in svc.get('ports',[]))
    original_ports=sorted((key,x['HostIp'],x['HostPort']) for key,values in (old['HostConfig'].get('PortBindings') or {}).items() for x in values)
    assert intended_ports==original_ports,'启动前端口不符'
    proof.append({'role':role,'image_environment_mounts_command_user_network_ports_match':True})
save('pre-start-render-proof.json',{'roles':proof})

state['stage']='production-migration';(W/'state.json').write_text(json.dumps(state,indent=2)+'\n')
print('生产前现场与全列复核通过，开始dry-run。',flush=True)
print('production dry-run',migrate_all('production-dry',NEW,'dry-run'),flush=True)
state['production_write_started']=True;(W/'state.json').write_text(json.dumps(state,indent=2)+'\n')
print('production apply',migrate_all('production-apply',NEW,'apply'),flush=True)
print('production verify',verify('production-verify',NEW),flush=True)
op('production-original',NEW,['/ops/snapshot.py','snapshot',*target()]);compare_snapshot('production-preservation.json','source-original','production-original',True)
result=compare_filesystems(json.loads((W/'fs-var-source.json').read_text()),filesystem_manifest(var));save('production-fs-preservation.json',result);assert result['equal']
state['stage']='production-migrated';(W/'state.json').write_text(json.dumps(state,indent=2)+'\n')
files=json.loads((P/'compose-files.json').read_text());argv=['docker','compose','-p',PROJECT]+[s for f in files for s in ['-f',f]]
assert json.loads(subprocess.check_output(argv+['config','--format','json'],cwd=B['compose_workdir'],text=True))==rendered,'迁移期间Compose有效配置发生变化'
with (W/'new-compose-up.log').open('x') as f:
 rp=subprocess.run(argv+['up','-d','--no-deps','--no-build','--pull','never','api','worker'],cwd=B['compose_workdir'],stdout=f,stderr=subprocess.STDOUT)
assert rp.returncode==0,'新版本启动失败，执行旧JSON回退'
identities=[]
for role in ['api','worker']:
 c=json.loads(subprocess.check_output(['docker','inspect',container(role)],text=True))[0];e=dict(x.split('=',1) for x in c['Config']['Env']);expected=env(role);expected.update(APP_VERSION='b8b2779a',DEPLOYMENT_ID=json.loads((P/'compose-review.json').read_text())['deployment_id']);assert c['Image']==NEW and e==expected,'实际运行环境超出两处发布标识变化';old=json.loads((W/(role+'-inspect.json')).read_text());mount=lambda value:sorted((m['Type'],m['Source'],m['Destination'],m['RW']) for m in value['Mounts']);assert mount(c)==mount(old),'运行挂载变化';identities.append({'role':role,'id':c['Id'],'image':c['Image'],'version':e['APP_VERSION'],'deployment_id':e['DEPLOYMENT_ID'],'started':c['State']['StartedAt']})
save('new-runtime-identities.json',identities)
until=time.monotonic()+120;health=None
while time.monotonic()<until:
 try:
  with urllib.request.urlopen('http://127.0.0.1:18000/api/v1/health/ready',timeout=10) as response:health=json.load(response)
  if health['deployment']['version']=='b8b2779a':break
 except (OSError,ValueError):pass
 time.sleep(1)
assert health and health['deployment']['version']=='b8b2779a' and health['status']=='ok'
checks=health['dependency_checks'];assert checks['effective_repository_backend']=='mysql' and checks['document_jobs_worker_backend']=='celery';assert all(checks[k] is True for k in checks['readiness_required_checks'])
save('new-local-ready.json',health)
code="""import json
from app.core.config import Settings
from app.workers.celery_app import create_celery_app
s=Settings(_env_file=None);d=create_celery_app(s).control.inspect(timeout=10).active_queues();assert d and len(d)==1
assert {q['name'] for qs in d.values() for q in qs}=={s.document_jobs_celery_queue,s.document_jobs_translation_batch_celery_queue}
print(json.dumps({'nodes':len(d),'queues':2,'ready':True}))
"""
until=time.monotonic()+120;worker_logs=[]
while time.monotonic()<until:
 rp=subprocess.run(['docker','exec',container('api'),'python','-B','-c',code],text=True,capture_output=True);worker_logs.append(rp.stdout+rp.stderr)
 if rp.returncode==0:break
 time.sleep(1)
(W/'new-worker-ready.log').write_text('\n'.join(worker_logs));assert rp.returncode==0
for role in ['api','worker']:
 logs=subprocess.run(['docker','logs',container(role)],text=True,capture_output=True);(W/('new-'+role+'.log')).write_text(logs.stdout+logs.stderr);assert 'Traceback (most recent call last)' not in logs.stdout+logs.stderr
assert hashlib.sha256(site.read_bytes()).hexdigest()==ng['candidates']['freeze']['sha256']
s=site.stat();fd,tmp=tempfile.mkstemp(prefix='.md2word-list-loading-',dir='/etc/nginx')
with os.fdopen(fd,'wb') as f:f.write(Path(ng['original_copy']).read_bytes());os.fchmod(f.fileno(),s.st_mode&0o7777);os.fchown(f.fileno(),s.st_uid,s.st_gid)
os.replace(tmp,site)
try:
 rp=subprocess.run(['nginx','-t'],text=True,capture_output=True);save('nginx-open-check.json',{'exit_code':rp.returncode});assert rp.returncode==0
 subprocess.run(['systemctl','reload','nginx'],check=True)
except BaseException:
 # 失败时磁盘与活动入口都回到已验证freeze，不让后续reload意外开放。
 fd,restore_tmp=tempfile.mkstemp(prefix='.md2word-list-loading-',dir='/etc/nginx')
 with os.fdopen(fd,'wb') as f:f.write(freeze_bytes);os.fchmod(f.fileno(),s.st_mode&0o7777);os.fchown(f.fileno(),s.st_uid,s.st_gid)
 os.replace(restore_tmp,site)
 validation=subprocess.run(['nginx','-t'],text=True,capture_output=True)
 reload_result=subprocess.run(['systemctl','reload','nginx'],text=True,capture_output=True) if validation.returncode==0 else None
 save('nginx-open-failure-freeze.json',{'restored_disk_freeze':True,'validation_exit_code':validation.returncode,'reload_exit_code':None if reload_result is None else reload_result.returncode})
 raise
state['stage']='new-live-pending-acceptance';state['cutover_at']=datetime.now(timezone.utc).isoformat();(W/'state.json').write_text(json.dumps(state,indent=2)+'\n')
save('cutover-result.json',{'passed':True,'runtime':identities,'health_version':health['deployment']['version'],'worker_nodes':1,'queues':2,'mysql_redis_preserved':True,'cutover_at':state['cutover_at']})
print('API/Worker已统一新镜像，健康/双队列通过，原入口已恢复，等待正常认证验收。',flush=True)
