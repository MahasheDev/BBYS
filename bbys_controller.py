"""One source of desired state, shared ownership, exact per-property undo."""
import copy
import json
import os
from pathlib import Path
import threading
from bbys_registry import token,canonical

def aggregate(checks,claimed=False):
    relevant=[c for c in checks if c['status']!='na']
    if not relevant:return 'unknown'
    good=sum(c['status']=='match' for c in relevant)
    errors=any(c['status']=='unknown' for c in relevant)
    if good==len(relevant):return 'enabled'
    if good or errors or claimed:return 'partial'
    return 'disabled'

class Controller:
    def __init__(self,backend,features,state_path):
        self.backend=backend;self.features=features;self.path=Path(state_path)
        self.lock=threading.RLock();self.state={'schema':1,'features':[],'properties':{}}
        if self.path.exists():
            self.state=json.loads(self.path.read_text(encoding='utf-8'))
            if self.state.get('schema')!=1:raise ValueError('Неизвестный формат состояния BBYS.')

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.pending')
        with temp.open('w',encoding='utf-8') as f:json.dump(self.state,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(temp,self.path)

    def ops(self,fid):
        result=[]
        for op in self.features[fid]['ops']:
            try:result.extend(self.backend.expand_ops([op]))
            except Exception as exc:result.append({'kind':'probe_error','name':op.get('name',op['kind']),'error':str(exc)})
        return result

    def check(self,fid):
        checks=[]
        try:ops=self.ops(fid)
        except Exception as exc:return {'status':'partial','checks':[{'status':'unknown','name':str(exc)}]}
        # Include dynamic properties already touched: reappearance must be detected.
        bytoken={token(o):o for o in ops}
        for t,p in self.state['properties'].items():
            if fid in p['owners']:bytoken.setdefault(t,p['op'])
        for op in bytoken.values():
            if op['kind']=='command':continue
            name=op.get('key','')+' '+str(op.get('name',op['kind']))
            try:
                if op['kind']=='probe_error':raise RuntimeError(op['error'])
                current=self.backend.read(op)
                status='na' if current=='N/A' else ('match' if self.backend.matches(op,current) else 'mismatch')
                checks.append({'name':name.strip(),'status':status,'actual':current,'expected':self.backend.desired(op)})
            except Exception as exc:checks.append({'name':name.strip(),'status':'unknown','error':str(exc)})
        pending=self.state.get('pending_restart',{}).get(fid)
        if pending is not None:
            try:
                rebooted=abs(self.backend.boot_marker()-float(pending))>120
                if rebooted:
                    with self.lock:
                        self.state.get('pending_restart',{}).pop(fid,None);self.save()
                else:
                    checks.append({'status':'unknown','name':'Ожидается перезапуск Windows',
                                   'error':'После системной операции необходим перезапуск для подтверждения её вступления в силу.'})
            except Exception as exc:
                checks.append({'status':'unknown','name':'Не проверен перезапуск Windows','error':str(exc)})
        for error in self.state.get('errors',{}).get(fid,[]):checks.append({'status':'unknown','name':'Последнее применение','error':error})
        return {'status':aggregate(checks,fid in self.state['features']),'checks':checks}

    def set_feature(self,fid,enabled):
        with self.lock:
            return self._enable(fid) if enabled else self._disable(fid)

    def _enable(self,fid):
        ops=self.ops(fid);errors=[]
        # All referenced source assets must exist before the first registry write.
        # Some portable distributions omit source/ entirely; never register dead commands.
        if any('${APP}' in str(item) and 'source' in str(item).casefold() for item in ops):
            source=self.backend.app_dir/'source'
            if not source.is_dir():
                raise RuntimeError('Отсутствует каталог source/ с ресурсами. Функция не применена: '+fid)
        # Expansion errors aren't actionable operations: fail before touching the system.
        bad=[o for o in ops if o['kind']=='probe_error']
        if bad:raise RuntimeError('Ошибка развёртывания операций: '+ '; '.join(str(o.get('error')) for o in bad))
        for op in ops:
            if op.get('check_only') and not op.get('post_apply'):
                if not self.backend.matches(op,self.backend.read(op)):
                    raise RuntimeError('Отсутствует обязательный ресурс: '+op.get('name',op['kind']))
        # Validate all ownership constraints before changing anything.
        for op in ops:
            if op.get('check_only'):
                if not op.get('post_apply') and not self.backend.matches(op,self.backend.read(op)):
                    raise RuntimeError('Не пройдена обязательная проверка ресурса: '+op['name'])
                continue
            t=token(op);existing=self.state['properties'].get(t)
            if existing and set(existing['owners'])-{fid} and self.backend.desired(existing['op'])!=self.backend.desired(op):
                raise RuntimeError('Конфликт общих параметров: '+t)
            if op['kind']=='delete_key':
                prefix='reg:'+canonical(op['key']).casefold()
                if any(k.startswith(prefix+'\\') or k.startswith(prefix+'|') for k,p in self.state['properties'].items() if set(p['owners'])-{fid}):raise RuntimeError('Удаляемая ветка используется другой функцией: '+op['key'])
        if fid not in self.state['features']:self.state['features'].append(fid)
        self.save()
        needs_reboot=False
        for op in ops:
            try:
                if op.get('check_only'):continue
                if op['kind']=='command':self.backend.apply(op,None);continue
                before=self.backend.read(op)
                if before=='N/A':continue
                t=token(op);prop=self.state['properties'].get(t)
                if prop is None:
                    prop={'op':copy.deepcopy(op),'before':before,'owners':[]};self.state['properties'][t]=prop
                if fid not in prop['owners']:prop['owners'].append(fid)
                self.save() # Write-ahead undo journal, not a registry-branch backup.
                if not self.backend.matches(op,before):
                    self.backend.apply(op,self.backend.desired(op))
                    if op['kind'] in ('bcd','optional','capability') or fid=='disable_uwp_background':
                        needs_reboot=True
            except Exception as exc:errors.append(f'{op.get("name",op.get("description",op["kind"]))}: {exc}')
        if needs_reboot:
            try:self.state.setdefault('pending_restart',{})[fid]=self.backend.boot_marker()
            except Exception as exc:errors.append('Не удалось зафиксировать необходимость перезагрузки: '+str(exc))
        self.state.setdefault('errors',{})[fid]=errors;self.save()
        self.backend.refresh()
        result=self.check(fid);result['errors']=errors
        if fid=='disable_uwp_background':
            result['notice']='Политика UWP требует перезапуска затронутых приложений/Windows; Win32-программы не затрагиваются.'
        return result

    def _disable(self,fid):
        if fid not in self.state['features']:raise RuntimeError('Нет исходного состояния для отката: функция применена вне этой версии BBYS. Сначала примените её через BBYS.')
        errors=[]
        shared_with_other_features=False
        needs_reboot=False
        for t,p in reversed(list(self.state['properties'].items())):
            if fid not in p['owners']:continue
            others=[x for x in p['owners'] if x!=fid]
            if others:shared_with_other_features=True
            try:
                if not others:
                    self.backend.apply(p['op'],p['before'])
                    if p['op']['kind'] in ('bcd','optional','capability') or fid=='disable_uwp_background':
                        needs_reboot=True
                else:
                    # Keep the shared setting, even if another program changed it.
                    current=self.backend.read(p['op'])
                    if not self.backend.matches(p['op'],current):self.backend.apply(p['op'],self.backend.desired(p['op']))
                if others:p['owners']=others
                else:del self.state['properties'][t]
                self.save()
            except Exception as exc:errors.append(t+': '+str(exc))
        if not errors:
            self.state['features'].remove(fid);self.state.setdefault('errors',{}).pop(fid,None)
            self.state.setdefault('pending_restart',{}).pop(fid,None)
        self.save();self.backend.refresh()
        result=self.check(fid);result['errors']=errors
        result['shared']=bool(shared_with_other_features and result['status']=='enabled' and not errors)
        if needs_reboot:
            result['notice']='Откат записан, но вступление изменений в силу может потребовать перезагрузки Windows.'
        return result
