"""Windows adapters. No system change occurs when this module is imported."""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import winreg
import bbys_registry as reg

WINDOWS=Path(os.environ.get('SystemRoot',r'C:\Windows'))

def sys_windows_build():
    import sys
    if sys.platform!='win32':return 0
    return sys.getwindowsversion().build

def run(args, timeout=120, accepted=(0,)):
    args=[str(a) for a in args]
    if not Path(args[0]).is_absolute():args[0]=str(WINDOWS/'System32'/args[0])
    cp=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                      creationflags=subprocess.CREATE_NO_WINDOW,timeout=timeout,shell=False)
    out=cp.stdout.decode('utf-8','replace').strip()
    if cp.returncode not in accepted:
        raise RuntimeError(f'{Path(args[0]).name}: код {cp.returncode}. '+cp.stderr.decode('utf-8','replace')[-800:])
    return out

def ps(script,timeout=90):
    import base64
    prefix="$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
    encoded=base64.b64encode((prefix+script).encode('utf-16-le')).decode('ascii')
    return run(['WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],timeout)

def quote(value):return "'"+str(value).replace("'","''")+"'"

INVENTORY=r'''
$r=@{errors=@{}}
try {$r.services=@(Get-CimInstance Win32_Service | Select-Object Name,State,StartMode)} catch {$r.errors.services=$_.Exception.Message}
try {$r.tasks=@(Get-ScheduledTask | Select-Object TaskPath,TaskName,@{n='Enabled';e={$_.Settings.Enabled}})} catch {$r.errors.tasks=$_.Exception.Message}
try {$r.optional=@(Get-WindowsOptionalFeature -Online | Select-Object FeatureName,@{n='State';e={[string]$_.State}})} catch {$r.errors.optional=$_.Exception.Message}
try {$r.capabilities=@(Get-WindowsCapability -Online | Select-Object Name,@{n='State';e={[string]$_.State}})} catch {$r.errors.capabilities=$_.Exception.Message}
try {$r.drives=@(Get-CimInstance Win32_Volume -Filter 'DriveType=3' | Select-Object DeviceID,DriveLetter,IndexingEnabled)} catch {$r.errors.drives=$_.Exception.Message}
try {$r.defender=Get-MpPreference | Select-Object DisableRealtimeMonitoring,DisableBehaviorMonitoring,DisableIOAVProtection,DisableScriptScanning} catch {$r.errors.defender=$_.Exception.Message}
$r | ConvertTo-Json -Depth 6 -Compress
'''

class WindowsBackend:
    def __init__(self,app_dir):
        self.app_dir=Path(app_dir)
        self.inventory=None
        self.cache={}

    def boot_marker(self):
        # Estimated epoch at OS boot. Unlike raw uptime, it can detect a reboot
        # even when the new session is older than the previous session was.
        import time
        return time.time()-ctypes.windll.kernel32.GetTickCount64()/1000.0

    def refresh(self):
        self.cache={}
        self.inventory=json.loads(ps(INVENTORY,120))

    def group(self,name):
        if self.inventory is None:self.refresh()
        if name in self.inventory.get('errors',{}):raise RuntimeError(self.inventory['errors'][name])
        return self.inventory.get(name)

    def expand(self,value):
        if not isinstance(value,str):return value
        if value=='${RAM_KB}':
            class Memory(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','avail','page','pageavail','virtual','virtualavail','extended')]
            m=Memory();m.length=ctypes.sizeof(m)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError()
            return min(m.total//1024,0xffffffff)
        return os.path.expandvars(value.replace('${APP}',str(self.app_dir)).replace('${WINDOWS}',str(WINDOWS)))

    def desired(self,op):
        if op['kind']=='registry':return {'exists':True,'type':reg.TYPES[op['type']],'data':self.expand(op['data'])}
        if op['kind']=='delete_value':return {'exists':False}
        if op['kind']=='delete_key':return None
        return self.expand(op.get('data'))

    def uwp_policy_status(self):
        """Effective *policy configuration*, not a claim about Win32 processes.

        Group Policy is supported on Windows 10/11 Pro/Enterprise/Education.
        Per-package Allow overrides the device-wide Force Deny setting.
        """
        edition=reg.read(r'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion','EditionID').get('data','')
        version=sys_windows_build()
        edition_key=str(edition).casefold()
        supported=(version>=15063 and any(edition_key.startswith(p) for p in
                   ('professional','enterprise','education','iotenterprise','server')))
        key=r'HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy'
        policy=reg.read(key,'LetAppsRunInBackground')
        user=reg.read(r'HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications','GlobalUserDisabled')
        exceptions=[]
        for name in ('LetAppsRunInBackground_ForceAllowTheseApps',
                     'LetAppsRunInBackground_UserInControlOfTheseApps'):
            value=reg.read(key,name)
            entries=value.get('data','')
            if isinstance(entries,list):entries=';'.join(str(x) for x in entries)
            if str(entries).strip(' ;\x00'):exceptions.append(name+': '+str(entries)[:320])
        # A device management policy can supersede local Group Policy.
        mdm_key=r'HKLM\SOFTWARE\Microsoft\PolicyManager\current\device\Privacy'
        mdm=reg.read(mdm_key,'LetAppsRunInBackground')
        if mdm.get('exists') and mdm.get('data')!=2:
            exceptions.append('MDM PolicyManager/Privacy/LetAppsRunInBackground='+str(mdm.get('data')))
        for name in ('LetAppsRunInBackground_ForceAllowTheseApps',
                     'LetAppsRunInBackground_UserInControlOfTheseApps'):
            value=reg.read(mdm_key,name)
            entries=value.get('data','')
            if isinstance(entries,list):entries=';'.join(str(x) for x in entries)
            if str(entries).strip(' ;\x00'):exceptions.append('MDM '+name+': '+str(entries)[:320])
        # Other user accounts have separate HKCU settings; don't imply coverage.
        effective=(supported and policy.get('data')==2 and policy.get('type')==reg.TYPES['REG_DWORD']
                   and user.get('data')==1 and not exceptions)
        return {'effective':effective,'edition':edition or 'не определена',
                'build':version,'supported':supported,
                'policy':policy,'current_user':user,'exceptions':exceptions,
                'scope':'UWP/packaged background tasks; текущая учётная запись; не Win32',
                'restart_required':'Перезапуск затронутых приложений или Windows'}

    def read(self,op):
        k=op['kind'];n=op.get('name','')
        if k=='uwp_policy_check':return self.uwp_policy_status()
        if k in ('registry','delete_value'):
            service=re.match(r'(HKLM\\SYSTEM\\CurrentControlSet\\Services\\[^\\]+)(?:\\|$)',reg.canonical(op['key']),re.I)
            if service and reg.tree(service[1]) is None:return 'N/A'
            return reg.read(op['key'],n)
        if k=='delete_key':return reg.tree(op['key'])
        if k=='service_start':
            s=reg.read('HKLM\\SYSTEM\\CurrentControlSet\\Services\\'+n,'Start')
            return {0:'boot',1:'system',2:'auto',3:'demand',4:'disabled'}.get(s.get('data'),s.get('data')) if s['exists'] else 'N/A'
        if k=='service_state':
            found=next((s for s in self.group('services') or [] if s['Name'].casefold()==n.casefold()),None)
            return found['State'].upper() if found else 'N/A'
        if k=='task':
            found=next((s for s in self.group('tasks') or [] if (s['TaskPath']+s['TaskName']).casefold()==n.casefold()),None)
            return bool(found['Enabled']) if found else 'N/A'
        if k in ('optional','capability'):
            group='optional' if k=='optional' else 'capabilities'; field='FeatureName' if k=='optional' else 'Name'
            found=next((s for s in self.group(group) or [] if s[field].casefold()==n.casefold()),None)
            state=found['State'] if found else 'N/A'
            return 'Disabled' if state=='DisabledWithPayloadRemoved' else state
        if k=='defender':
            value=self.group('defender')
            if not value or n not in value:raise RuntimeError('Состояние Defender недоступно')
            return value[n]
        if k=='indexing':
            drives=self.group('drives') or []
            if not drives:raise RuntimeError('Не найдены локальные тома для проверки индексирования')
            return {x['DeviceID']:bool(x['IndexingEnabled']) for x in drives}
        if k=='power_scheme':
            import uuid
            pointer=ctypes.c_void_p()
            lib=ctypes.WinDLL('PowrProf',use_last_error=True)
            lib.PowerGetActiveScheme.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
            lib.PowerGetActiveScheme.restype=ctypes.c_ulong
            rc=lib.PowerGetActiveScheme(None,ctypes.byref(pointer))
            if rc:raise OSError(rc,'Не удалось определить активную схему питания')
            try:return str(uuid.UUID(bytes_le=ctypes.string_at(pointer,16)))
            finally:
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.LocalFree.argtypes=[ctypes.c_void_p]
                kernel.LocalFree(pointer)
        if k=='power_ac':
            import uuid
            buffers=[ctypes.create_string_buffer(uuid.UUID(g).bytes_le) for g in (op.get('scheme','8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'),op['subgroup'],n)]
            value=ctypes.c_ulong();func=ctypes.WinDLL('PowrProf').PowerReadACValueIndex
            func.argtypes=[ctypes.c_void_p]*4+[ctypes.POINTER(ctypes.c_ulong)];func.restype=ctypes.c_ulong
            rc=func(None,*[ctypes.byref(b) for b in buffers],ctypes.byref(value))
            if rc:raise OSError(rc,'Индекс питания недоступен: '+n)
            return value.value
        if k=='bcd':
            if 'bcd' not in self.cache:self.cache['bcd']=run(['bcdedit.exe','/enum','{current}'])
            m=re.search(r'^\s*'+re.escape(n)+r'\s+(\S+)',self.cache['bcd'],re.M|re.I)
            return m.group(1).lower() if m else None
        if k=='fsutil':
            out=run(['fsutil.exe','behavior','query',n]);match=re.search(r'=\s*(\d+)',out)
            if not match:raise RuntimeError('Не удалось прочитать '+n)
            return int(match.group(1))
        if k=='admin_group':
            value=ps("$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; $g=Get-LocalGroup -SID 'S-1-5-32-544'; [bool](@(Get-LocalGroupMember -Group $g | Where-Object {$_.SID.Value -eq $u}).Count) | ConvertTo-Json -Compress")
            return json.loads(value)
        if k=='file_equal':
            import hashlib
            paths=[Path(self.expand(op[f])) for f in ('left','right')]
            return all(p.is_file() for p in paths) and hashlib.sha256(paths[0].read_bytes()).digest()==hashlib.sha256(paths[1].read_bytes()).digest()
        if k=='file_exists':return Path(self.expand(n)).is_file()
        if k=='path_item':
            state=reg.read(op['key'],'Path');parts=str(state.get('data','')).split(';')
            return any(os.path.normcase(os.path.expandvars(p).rstrip('\\'))==os.path.normcase(self.expand(n).rstrip('\\')) for p in parts)
        if k=='custom':raise RuntimeError('Внешний компонент требует отдельной проверки')
        if k=='command':return None
        raise RuntimeError('Неизвестная проверка: '+k)

    def expand_ops(self,ops):
        result=[]
        for op in ops:
            kind=op['kind']
            if kind=='task_pattern':
                result.extend({'kind':'task','name':t['TaskPath']+t['TaskName'],'data':False} for t in self.group('tasks') or [] if re.search(op['name'],t['TaskPath']+t['TaskName'],re.I))
            elif kind=='realtek':
                key=r'HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}'
                root,sub=reg.split(key)
                with winreg.OpenKey(root,sub) as h:
                    for i in range(winreg.QueryInfoKey(h)[0]):
                        child=winreg.EnumKey(h,i)
                        if not child.isdigit():continue
                        desc=reg.read(key+'\\'+child,'DriverDesc')
                        if 'realtek' not in str(desc.get('data','')).casefold():continue
                        for n,v in (('PowerSavingMode','0'),('EnableGreenEthernet','0'),('GigaLite','0'),('WolShutdownLinkSpeed','2')):
                            if reg.read(key+'\\'+child,n)['exists']:result.append({'kind':'registry','key':key+'\\'+child,'name':n,'type':'REG_SZ','data':v})
            elif kind=='firefox_run':
                for key in (r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run',r'HKLM\Software\Microsoft\Windows\CurrentVersion\Run'):
                    value=reg.tree(key)
                    for n,s in (value or {}).get('values',{}).items():
                        if re.match('Mozilla-Firefox-',n,re.I) and re.search(r'firefox\.exe',str(s['data']),re.I) and '-os-autostart' in str(s['data']):
                            result.append({'kind':'delete_value','key':key,'name':n})
            elif kind=='custom' and op.get('name')=='cmd_command_extension':
                base=self.app_dir/'source'/'Personalization'/'MahasheApp_CommandLine'
                if not base.is_dir():raise RuntimeError('Не найдена папка расширения консольных команд.')
                dirs=[base]+sorted({p.parent for p in base.rglob('*') if p.suffix.lower() in ('.exe','.cmd','.bat','.py','.ahk')})
                for folder in dict.fromkeys(dirs):
                    result.append({'kind':'path_item','name':str(folder),'key':r'HKCU\Environment','data':True})
            else:
                result.append(op)
                if kind=='registry' and isinstance(op.get('data'),str):
                    for match in re.finditer(r'\$\{APP\}[^"\r\n]*?\.(?:exe|bat|cmd|ps1|ico|dll)',op['data'],re.I):
                        result.append({'kind':'file_exists','name':match[0],'data':True,'check_only':True})
        return result

    def matches(self,op,current):
        if current=='N/A':return True
        if op['kind']=='uwp_policy_check':return isinstance(current,dict) and current.get('effective') is True
        if op['kind']=='indexing':return bool(current) and all(v==op['data'] for v in current.values())
        if op['kind']=='bcd' and op['data']=='yes':return str(current).casefold() in ('yes','да','true','1')
        return current==self.desired(op)

    def apply(self,op,value):
        k=op['kind'];n=op.get('name','');v=value
        if k in ('registry','delete_value'):reg.write(op['key'],n,v)
        elif k=='delete_key':reg.restore_tree(op['key'],v)
        elif k=='service_start':run(['sc.exe','config',n,'start=',v])
        elif k=='service_state':run(['sc.exe','start' if v=='RUNNING' else 'stop',n],accepted=(0,1056,1062))
        elif k=='task':run(['schtasks.exe','/Change','/TN',n,'/Enable' if v else '/Disable'])
        elif k=='optional':run(['dism.exe','/Online','/Enable-Feature' if str(v).startswith('Enabled') else '/Disable-Feature','/FeatureName:'+n,'/NoRestart'],1800,(0,3010))
        elif k=='capability':run(['dism.exe','/Online','/Add-Capability' if v=='Installed' else '/Remove-Capability','/CapabilityName:'+n],1800,(0,3010))
        elif k=='defender':ps('Set-MpPreference -'+n+' $'+str(bool(v)).lower())
        elif k=='indexing':
            states=v if isinstance(v,dict) else {s['DeviceID']:bool(v) for s in self.group('drives') or []}
            data=json.dumps(states)
            ps('$s='+quote(data)+" | ConvertFrom-Json; Get-CimInstance Win32_Volume -Filter 'DriveType=3' | ForEach-Object { $p=$s.PSObject.Properties[$_.DeviceID]; if($null -ne $p){$_ | Set-CimInstance -Property @{IndexingEnabled=[bool]$p.Value} | Out-Null} }")
        elif k=='power_scheme':run(['powercfg.exe','-setactive',v])
        elif k=='power_ac':
            run(['powercfg.exe','-setacvalueindex',op.get('scheme','8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'),op['subgroup'],n,str(v)])
            run(['powercfg.exe','-setactive',self.read({'kind':'power_scheme'})])
        elif k=='bcd':run(['bcdedit.exe','/deletevalue','{current}',n] if v is None else ['bcdedit.exe','/set','{current}',n,str(v)])
        elif k=='fsutil':run(['fsutil.exe','behavior','set',n,str(v)])
        elif k=='admin_group':
            ps("$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name; $g=Get-LocalGroup -SID 'S-1-5-32-544'; "+('Add' if v else 'Remove')+'-LocalGroupMember -Group $g -Member $u')
        elif k=='path_item':
            previous=reg.read(op['key'],'Path');parts=[p for p in str(previous.get('data','')).split(';') if p]
            target=self.expand(n)
            parts=[p for p in parts if os.path.normcase(os.path.expandvars(p).rstrip('\\'))!=os.path.normcase(target.rstrip('\\'))]
            if v:parts.append(target)
            reg.write(op['key'],'Path',{'exists':True,'type':previous.get('type',winreg.REG_EXPAND_SZ),'data':';'.join(parts)})
            broadcast_environment()
        elif k=='command':run([self.expand(x) for x in op['args']],timeout=600)
        else:raise RuntimeError('Автоматическое изменение не реализовано: '+k)
        self.cache={}

def broadcast_environment():
    result=ctypes.c_size_t()
    user32=ctypes.WinDLL('user32',use_last_error=True)
    func=user32.SendMessageTimeoutW
    func.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_size_t)]
    func.restype=ctypes.c_ssize_t
    return bool(func(0xffff,0x001a,0,'Environment',2,5000,ctypes.byref(result)))
