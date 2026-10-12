"""Remove only registered GIGABYTE Dynamic Lighting packages."""
import ctypes
from pathlib import Path
import re
import winreg
from bbys_system import run

def split_command(command):
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.CommandLineToArgvW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
    count=ctypes.c_int();ptr=shell.CommandLineToArgvW(command,ctypes.byref(count))
    if not ptr:raise ctypes.WinError()
    try:return [ptr[i] for i in range(count.value)]
    finally:
        kernel=ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree(ptr)

def lighting_packages():
    packages=[];seen=set()
    path=r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    for root in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:h=winreg.OpenKey(root,path,0,winreg.KEY_READ|view)
            except FileNotFoundError:continue
            with h:
                for i in range(winreg.QueryInfoKey(h)[0]):
                    sub=winreg.EnumKey(h,i)
                    with winreg.OpenKey(h,sub) as app:
                        def val(n):
                            try:return str(winreg.QueryValueEx(app,n)[0])
                            except FileNotFoundError:return ''
                        title=val('DisplayName');publisher=val('Publisher')
                        if not re.fullmatch(r'GIGABYTE\s+Dynamic\s+Light(?:ing)?(?:\s+(?:Module|Library|Lib))?(?:\s+v?[\d.]+)?',title,re.I):continue
                        if publisher and 'gigabyte' not in publisher.casefold():continue
                        command=val('QuietUninstallString') or val('UninstallString')
                        ident=(sub,command)
                        if ident in seen:continue
                        seen.add(ident);packages.append({'name':title,'id':sub,'command':command})
    return packages

def uninstall_lighting():
    packages=lighting_packages()
    if not packages:return 'GIGABYTE Dynamic Lighting module не установлен.'
    for app in packages:
        args=split_command(app['command'])
        if not args:raise RuntimeError('Не задан деинсталлятор: '+app['name'])
        if Path(args[0]).name.lower() in ('msiexec','msiexec.exe'):
            match=re.search(r'\{[0-9a-f-]{36}\}',app['command'],re.I)
            if not match:raise RuntimeError('Не найден MSI ProductCode: '+app['name'])
            args=['msiexec.exe','/x',match.group(),'/qn','/norestart']
        elif not Path(args[0]).is_absolute() or not Path(args[0]).is_file() or Path(args[0]).suffix.lower()!='.exe':
            raise RuntimeError('Некорректный путь деинсталлятора: '+app['name'])
        elif Path(args[0]).name.lower() in ('cmd.exe','powershell.exe','pwsh.exe','wscript.exe','cscript.exe'):
            raise RuntimeError('Командный деинсталлятор требует ручной проверки: '+app['name'])
        run(args,1800,(0,1605,1614,1641,3010))
    if lighting_packages():raise RuntimeError('Запись модуля ещё присутствует. Возможно, деинсталлятор ожидает действия или перезагрузки.')
    return 'GIGABYTE Dynamic Lighting module удалён; запись установки отсутствует.'
