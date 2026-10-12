"""Build BBYS without changing the caller's console configuration."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'build-temp'
RELEASE=ROOT/'Project-Build-6_4_1'

def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    try:
        import PySide6
    except ImportError:
        print('Install build dependencies: python -m pip install -r requirements.txt')
        return 2
    if not (ROOT/'source').is_dir():
        print('ERROR: source/ is absent; the input archive lacks runtime resources. Cannot produce a working release.')
        return 3
    WORK.mkdir(parents=True,exist_ok=True);RELEASE.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed',
      '--name','BBYS','--uac-admin','--icon',str(ROOT/'BBYS_icon_pack'/'BBYS.ico'),
      '--version-file',str(ROOT/'bbys_version.txt'),
      '--add-data',str(ROOT/'BBYS_icon_pack'/'BBYS.ico')+';BBYS_icon_pack',
      '--add-data',str(ROOT/'bbys_features.json')+';.',
      '--workpath',str(WORK/'work'),'--specpath',str(WORK),'--distpath',str(RELEASE),
      '--paths',str(ROOT),str(ROOT/'BBYS.py')]
    result=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (WORK/'build.log').write_bytes(result.stdout)
    if result.returncode:
        print(result.stdout.decode('utf-8','replace')[-6000:]);return result.returncode
    def ignore(directory,names):
        return [n for n in names if n.casefold() in {'backup','backups','logs','state','temp','generated','__pycache__'}]
    shutil.copytree(ROOT/'source',RELEASE/'source',dirs_exist_ok=True,ignore=ignore)
    print('Built: '+str(RELEASE/'BBYS.exe'))
    print('Build log: '+str(WORK/'build.log'))
    return 0

if __name__=='__main__':raise SystemExit(main())
