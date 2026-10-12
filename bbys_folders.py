"""Known-folder paths; transactionally set every supported alias."""
import ctypes
import os
from pathlib import Path
import winreg
import bbys_registry as reg

BASE=r'HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer'
ALIASES={
 'Desktop':['Desktop','{754AC886-DF64-4CBA-86B5-F7FBF4FBCEF5}'],
 'Personal':['Personal','{F42EE2D3-909F-4907-8871-4C22FC0BF756}'],
 '{374DE290-123F-4565-9164-39C4925E467B}':['{374DE290-123F-4565-9164-39C4925E467B}','{7D83EE9B-2244-4E70-B1F5-5393042AF1E4}'],
 'My Music':['My Music','{A0C69A99-21C8-4671-8703-7934162FCF1D}'],
 'My Pictures':['My Pictures','{0DDD015D-B06C-45D5-8C4C-F59713854639}'],
 'My Video':['My Video','{35286A68-3C57-41A1-BBB1-0EAE73D76C95}']}

def switch(values):
    staged=[]
    for name,value in values.items():
        if name not in ALIASES:raise ValueError('Неизвестная системная папка.')
        value=os.path.normpath(os.path.expandvars(value.strip().strip('"')))
        if not os.path.isabs(value) or value==Path(value).anchor:raise ValueError('Укажите отдельную папку с полным путём.')
        for alias in ALIASES[name]:
            for suffix,typ in (('User Shell Folders',winreg.REG_EXPAND_SZ),('Shell Folders',winreg.REG_SZ)):
                key=BASE+'\\'+suffix;before=reg.read(key,alias)
                if os.path.normcase(os.path.expandvars(str(before.get('data',''))))!=os.path.normcase(value):
                    staged.append((key,alias,before,{'exists':True,'type':typ,'data':value}))
    for value in {item[3]['data'] for item in staged}:Path(value).mkdir(parents=True,exist_ok=True)
    touched=[]
    try:
        for key,name,before,after in staged:
            if reg.read(key,name)!=before:raise RuntimeError('Путь папки изменён другой программой.')
            touched.append((key,name,before));reg.write(key,name,after)
            if reg.read(key,name)!=after:raise RuntimeError('Не прошла проверка пути '+name)
    except Exception as exc:
        errors=[]
        for key,name,before in reversed(touched):
            try:reg.write(key,name,before)
            except Exception as failure:errors.append(str(failure))
        if errors:raise RuntimeError(str(exc)+'; ошибка отката: '+'; '.join(errors)) from exc
        raise
    ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)
    return 'Расположения папок сохранены. Для обновления всех приложений выйдите из учётной записи. Существующие файлы не перемещались.'
