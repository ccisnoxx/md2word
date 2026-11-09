
from pathlib import Path
import subprocess,json,os,time,hashlib
R=Path('/root/md2word-releases/b8b2779a-list-loading'); W=R/'window'; P=R/'release-preparation'
B=json.loads((P/'build-inputs.json').read_text()); S=json.loads((W/'state.json').read_text())
OLD=S['old_image'];NEW=S['new_image'];PROD_UUID=S['production_uuid'];PROJECT=B['compose_project']
def save(name,value):
 with (W/name).open('x') as f:
  f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.fchmod(f.fileno(),0o600)
def env(name):return dict(x.split('=',1) for x in (W/(name+'.env')).read_text().splitlines())
def container(role):return json.loads((W/(role+'-inspect.json')).read_text())['Name'].lstrip('/')
def op(name,image,args,*,clone=False,reader=False,objects=False):
 cfg='clone-readonly' if reader else ('clone' if clone else 'api')
 network='md2word-list-loading-rehearsal' if clone else PROJECT+'_default'
 cmd=['docker','run','--rm','--network',network,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--cpus','1','--env-file',str(W/(cfg+'.env')),'--env','PYTHONPATH=/app','--mount','type=bind,src='+str(R/'release-ops')+',dst=/ops,readonly']
 if objects:
  cmd+=['--mount','type=bind,src='+str(W/'control/cases.json')+',dst=/control/cases.json,readonly']
  cmd+=['--mount','type=bind,src='+str(W/'restore-var')+',dst=/app/var,readonly']
  bindings=json.loads((W/'restore-bindings.json').read_text())
  for b in bindings:cmd+=['--mount','type=bind,src='+b['copy']+',dst='+b['destination']+',readonly']
 cmd+=[image,'python','-B',*args]
 start=time.monotonic();rp=subprocess.run(cmd,text=True,capture_output=True)
 with (W/(name+'.stdout')).open('x') as f:f.write(rp.stdout);os.fchmod(f.fileno(),0o600)
 with (W/(name+'.stderr')).open('x') as f:f.write(rp.stderr);os.fchmod(f.fileno(),0o600)
 save(name+'-execution.json',{'exit_code':rp.returncode,'seconds':time.monotonic()-start,'image':image,'clone':clone,'reader':reader})
 try:report=json.loads(rp.stdout)
 except ValueError:raise RuntimeError(name+':输出不是单JSON，已保留受限stderr')
 if rp.returncode or report.get('exit_code',0):raise RuntimeError(name+':工具失败，见受限报告')
 return report
def target(clone=False):
 return ['--expect-database','md2word','--expect-server-uuid',json.loads((W/'clone-identity.json').read_text())['uuid'] if clone else PROD_UUID]
def compare_snapshot(name,a,b,keys=False):
 cmd=['python3',str(R/'release-ops/snapshot.py'),'compare',str(W/(a+'.stdout')),str(W/(b+'.stdout'))]+(['--require-new-keys'] if keys else [])
 rp=subprocess.run(cmd,text=True,capture_output=True);save(name,{'result':json.loads(rp.stdout),'exit_code':rp.returncode});assert rp.returncode==0,name
 return json.loads(rp.stdout)
def migrate_all(prefix,image,mode,clone=False):
 f=j=''; reports=[]
 for index in range(100):
  args=['/ops/migrate.py',*target(clone),'--'+mode,'--batch-size','100']
  if f:args+=['--after-file-id',f]
  if j:args+=['--after-job-id',j]
  report=op(prefix+'-'+str(index),image,args,clone=clone);reports.append(report)
  ts=report['tables'];fs=ts['document_files'];js=ts['document_jobs']
  if any(x['errors'] for x in ts.values()):raise RuntimeError(prefix+':迁移数据错误')
  key='last_scanned_' if mode=='dry-run' else 'last_successful_'
  f=fs[key+'file_id'] or f;j=js[key+'job_id'] or j
  if all(x['status']=='complete' and x['has_more'] is False for x in ts.values()):break
 else:raise RuntimeError('批次超过100，停止')
 return {'batches':len(reports),'rows':sum(sum(x['processed_rows'] for x in report['tables'].values()) for report in reports)}
def verify(name,image,clone=False):
 d=op(name,image,['/ops/migrate.py',*target(clone),'--verify','--batch-size','100'],clone=clone)
 assert d['all_ready'] and all(x['status']=='complete' and not x['schema_missing'] and not x['mismatches'] and not x['errors'] for x in d['tables'].values())
 return {'all_ready':True,'tables':{k:{'rows':v['scanned_rows'],'version':v['projection_version']} for k,v in d['tables'].items()}}
