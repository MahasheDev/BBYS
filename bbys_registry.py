"""Typed registry operations shared by applying, checking and reverting settings."""
import json
import re
import winreg

ROOTS = {'HKCU': winreg.HKEY_CURRENT_USER, 'HKLM': winreg.HKEY_LOCAL_MACHINE, 'HKCR': winreg.HKEY_CLASSES_ROOT}
TYPES = {name: getattr(winreg, name) for name in ('REG_SZ','REG_EXPAND_SZ','REG_DWORD','REG_QWORD','REG_BINARY','REG_MULTI_SZ')}

def canonical(path):
    path = re.sub(r'[\\/]+', lambda _: '\\', str(path)).rstrip('\\')
    for long, short in (('HKEY_CURRENT_USER','HKCU'),('HKEY_LOCAL_MACHINE','HKLM'),('HKEY_CLASSES_ROOT','HKCR')):
        path = re.sub('^'+long,short,path,flags=re.I)
    return path

def split(path):
    head, sep, tail = canonical(path).partition('\\')
    if not sep or head.upper() not in ROOTS:
        raise ValueError('Некорректный путь реестра: '+str(path))
    return ROOTS[head.upper()], tail

def token(op):
    kind = op['kind']
    if kind in ('registry','delete_value'):
        return 'reg:'+canonical(op['key']).casefold()+'|'+str(op.get('name') or '').casefold()
    if kind == 'delete_key': return 'key:'+canonical(op['key']).casefold()
    if kind=='path_item':return kind+':'+canonical(op['key']).casefold()+'|'+str(op['name']).casefold()
    return kind+':'+str(op.get('name','')).casefold()

def read(path,name=''):
    root,key=split(path)
    try:
        with winreg.OpenKey(root,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as handle:
            data,typ=winreg.QueryValueEx(handle,name)
        return {'exists':True,'type':typ,'data':list(data) if isinstance(data,bytes) else data}
    except FileNotFoundError: return {'exists':False}

def write(path,name,state):
    root,key=split(path)
    if not state.get('exists'):
        try:
            with winreg.OpenKey(root,key,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as h:
                winreg.DeleteValue(h,name)
        except FileNotFoundError: pass
        return
    typ=state['type']; typ=TYPES.get(typ,typ)
    data=state['data']
    if typ==winreg.REG_BINARY: data=bytes(data)
    with winreg.CreateKeyEx(root,key,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as h:
        winreg.SetValueEx(h,name,0,typ,data)

def tree(path):
    root,key=split(path)
    try: h=winreg.OpenKey(root,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:return None
    result={'values':{},'children':{}}
    with h:
        for i in range(winreg.QueryInfoKey(h)[1]):
            n,d,t=winreg.EnumValue(h,i)
            result['values'][n]={'exists':True,'data':list(d) if isinstance(d,bytes) else d,'type':t}
        for i in range(winreg.QueryInfoKey(h)[0]):
            n=winreg.EnumKey(h,i); result['children'][n]=tree(canonical(path)+'\\'+n)
    return result

def restore_tree(path,value):
    root,key=split(path)
    current=tree(path)
    if current is not None:
        for name in current['children']: restore_tree(canonical(path)+'\\'+name,None)
        winreg.DeleteKeyEx(root,key,winreg.KEY_WOW64_64KEY,0)
    if value is None:return
    with winreg.CreateKeyEx(root,key,0,winreg.KEY_WRITE|winreg.KEY_WOW64_64KEY):pass
    for name,state in value['values'].items():write(path,name,state)
    for name,child in value['children'].items():restore_tree(canonical(path)+'\\'+name,child)

def parse_reg(text):
    """Parse REG exports, including default values, continuations and typed hex."""
    key=None; result=[]
    text=re.sub(r'\\\r?\n\s*','',text)
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith(';') or line.startswith('Windows Registry'):continue
        if line.startswith('['):
            key=canonical(line[1:-1].lstrip('-'))
            if line.startswith('[-'):result.append({'kind':'delete_key','key':key}); key=None
            continue
        if key is None:continue
        match=re.match(r'(@|"(?:\\.|[^"\\])*")\s*=\s*(.*)',line)
        if not match:raise ValueError('Не распознан REG: '+line)
        n,v=match.groups(); name='' if n=='@' else json.loads(n)
        op={'kind':'registry','key':key,'name':name}
        if v=='-':op['kind']='delete_value'
        elif v.startswith('"'):
            # Comments outside the quoted string are ignored by raw_decode.
            op.update(type='REG_SZ',data=json.JSONDecoder().raw_decode(v)[0])
        elif v.lower().startswith('dword:'):op.update(type='REG_DWORD',data=int(v[6:].split(';')[0],16))
        elif v.lower().startswith('hex'):
            label,data=v.split(':',1); rawbytes=bytes.fromhex(data.split(';')[0].replace(',','').replace(' ',''))
            if label=='hex':op.update(type='REG_BINARY',data=list(rawbytes))
            elif label=='hex(2)':op.update(type='REG_EXPAND_SZ',data=rawbytes.decode('utf-16-le').rstrip('\0'))
            elif label=='hex(7)':op.update(type='REG_MULTI_SZ',data=rawbytes.decode('utf-16-le').rstrip('\0').split('\0'))
            elif label=='hex(b)':op.update(type='REG_QWORD',data=int.from_bytes(rawbytes,'little'))
            else:raise ValueError('Неизвестный тип REG: '+label)
        else:raise ValueError('Неизвестное значение REG: '+v)
        result.append(op)
    return result
