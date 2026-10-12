"""Transactional TEMP/TMP switching; existing temporary files are never moved."""
import os
from pathlib import Path
import tempfile
import uuid
import winreg
from bbys_system import ps,quote,broadcast_environment
import bbys_registry as reg

SCOPES={'user':r'HKCU\Environment','machine':r'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment'}

def current():
    return {f'{scope}_{name.lower()}':reg.read(key,name) for scope,key in SCOPES.items() for name in ('TEMP','TMP')}

def normalize(value,scope):
    value=str(value).strip().strip('"')
    if not value:raise ValueError('TEMP/TMP не может быть пустым.')
    if '%' in value:raise ValueError('Выберите полный путь без переменных окружения.')
    if not os.path.isabs(value) or value.startswith(('\\\\','\\?\\')):raise ValueError('Нужен абсолютный путь на локальном диске.')
    path=Path(os.path.abspath(value))
    if str(path)==path.anchor:raise ValueError('Корень диска нельзя использовать как TEMP.')
    protected=[Path(os.environ.get('SystemRoot',r'C:\Windows')),Path.home(),Path(os.environ.get('ProgramFiles',r'C:\Program Files'))]
    if any(os.path.normcase(str(path))==os.path.normcase(str(p)) for p in protected):raise ValueError('Выберите отдельную папку TEMP.')
    import ctypes
    if ctypes.windll.kernel32.GetDriveTypeW(path.anchor)!=3:raise ValueError('TEMP должен находиться на постоянном локальном диске.')
    if not Path(path.anchor).is_dir():raise ValueError('Диск назначения недоступен.')
    for p in (path,*path.parents):
        if p.exists() and (p.is_symlink() or p.is_junction()):raise ValueError('Путь TEMP не должен проходить через ссылку или junction.')
    if path.exists() and not path.is_dir():raise ValueError('Вместо каталога выбран файл.')
    return str(path)

def validate(values):
    expected={f'{s}_{n}' for s in SCOPES for n in ('temp','tmp')}
    if set(values)!=expected:raise ValueError('Нужно указать все четыре пути TEMP/TMP.')
    clean={k:normalize(v,k.split('_',1)[0]) for k,v in values.items()}
    for a in ('user_temp','user_tmp'):
        for b in ('machine_temp','machine_tmp'):
            try:common=os.path.normcase(os.path.commonpath([clean[a],clean[b]]))
            except ValueError:continue
            if common in (os.path.normcase(clean[a]),os.path.normcase(clean[b])):
                raise ValueError('Пользовательские и системные TEMP должны быть отдельными, не вложенными каталогами.')
    return clean

def prepare_directory(path,source,scope):
    target=Path(path);created=not target.exists()
    if created:
        target.mkdir(parents=True,exist_ok=False)
        # Only a newly created destination receives ACLs; existing folders are not relaxed.
        source=os.path.expandvars(str(source))
        if not Path(source).is_dir():
            source=str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))/'Temp') if scope=='user' else str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Temp')
        if not Path(source).is_dir():raise RuntimeError('Не найден исходный каталог для переноса прав TEMP.')
        ps('$acl=Get-Acl -LiteralPath '+quote(source)+'; $acl.SetAccessRuleProtection($true,$true); Set-Acl -LiteralPath '+quote(path)+' -AclObject $acl')
    probe=target/('.bbys-write-'+uuid.uuid4().hex)
    try:
        with probe.open('xb') as f:f.write(b'BBYS');f.flush();os.fsync(f.fileno())
        if probe.read_bytes()!=b'BBYS':raise OSError('Ошибка проверки записи в TEMP.')
    finally:
        if probe.exists():probe.unlink()
    # Effective ACL check for LocalSystem (system TEMP), including inherited deny entries.
    # AccessCheck uses an impersonation token for current user; SYSTEM permissions are
    # checked separately from the DACL without changing it.
    if scope=='user':return
    script='''$p=PATH; $a=Get-Acl -LiteralPath $p;
$rules=$a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]);
$wanted=@('S-1-5-18');
foreach($s in $wanted){
  $allow=0L;$deny=0L;
  foreach($r in $rules){if(($r.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]::InheritOnly) -eq 0){
    if($r.IdentityReference.Value -in @($s,'S-1-1-0','S-1-5-11')){
      if($r.AccessControlType -eq 'Deny'){$deny=$deny -bor [long]$r.FileSystemRights}else{$allow=$allow -bor [long]$r.FileSystemRights}
    }
  }}
  $need=0x100116L; if(($deny -band $need) -ne 0 -or ($allow -band $need) -ne $need){throw "Недостаточно прав TEMP для SID $s"}
}'''.replace('PATH',quote(path))
    ps(script)

def switch(values,prepare=prepare_directory,read_current=current,write=reg.write,broadcast=broadcast_environment):
    values=validate(values)
    before=read_current()
    changed={k:v for k,v in values.items() if os.path.normcase(os.path.expandvars(str(before[k].get('data',''))))!=os.path.normcase(v)}
    if not changed:return 'TEMP/TMP уже настроены.'
    # Prepare every destination before the first environment write.
    prepared=set()
    for k,v in changed.items():
        scope=k.split('_',1)[0]
        if (scope,os.path.normcase(v)) not in prepared:
            prepare(v,before[k].get('data',''),scope);prepared.add((scope,os.path.normcase(v)))
    # Do not overwrite an external edit made during validation.
    if read_current()!=before:raise RuntimeError('TEMP/TMP изменены другой программой. Обновите пути и повторите.')
    touched=[];old_env={n:os.environ.get(n) for n in ('TEMP','TMP')};old_cache=tempfile.tempdir
    try:
        for k,v in changed.items():
            scope,name=k.split('_',1);touched.append(k)
            write(SCOPES[scope],name.upper(),{'exists':True,'type':winreg.REG_EXPAND_SZ,'data':v})
        after=read_current()
        if any(after[k]!={'exists':True,'type':winreg.REG_EXPAND_SZ,'data':v} for k,v in changed.items()):raise RuntimeError('Контрольное чтение TEMP/TMP не совпало с заданными путями.')
        for n in ('TEMP','TMP'):os.environ[n]=values['user_'+n.lower()]
        tempfile.tempdir=None
    except Exception as exc:
        failures=[]
        for k in reversed(touched):
            scope,name=k.split('_',1)
            try:write(SCOPES[scope],name.upper(),before[k])
            except Exception as error:failures.append(f'{k}: {error}')
        for n,v in old_env.items():
            if v is None:os.environ.pop(n,None)
            else:os.environ[n]=v
        tempfile.tempdir=old_cache
        try:
            restored=read_current()
            failures.extend(k+': контроль отката не пройден' for k in touched if restored[k]!=before[k])
        except Exception as error:failures.append('Контроль отката: '+str(error))
        broadcast()
        if failures:raise RuntimeError(f'{exc}\nНе завершён откат: '+ '; '.join(failures)) from exc
        raise RuntimeError(f'{exc}\nИсходные TEMP/TMP восстановлены.') from exc
    notified=broadcast()
    return 'TEMP/TMP переключены и проверены. Уже запущенные программы и службы используют прежнее окружение до перезапуска.'+('' if notified else ' Уведомление Windows не доставлено всем окнам; выйдите из учётной записи.')
