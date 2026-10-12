"""BBYS Windows engine. Derived from the effective WinTweaker 6_4 implementation; no legacy UI."""

import base64, ctypes, datetime, math, os, json, queue, re, shutil, subprocess, urllib.request, sys, threading, time
from pathlib import Path
import winreg
from PIL import Image, ImageDraw, ImageOps, ImageTk

REMOVE_PREINSTALLED_APPS_PS_RU = ('# Title:        Remove default Software on Windows 10\n'
 '# Description:  This script is semi-automatically removing the\n'
 '#               default Applications installed on Windows.\n'
 '# Created:      2020-07-17 - Vinalti\n'
 '# Last Update:  2023-07-12 - Vinalti\n'
 '# Author:       Vinalti\n'
 '# Contributors: - ...\n'
 '\n'
 '\n'
 '### PopUp Documentation: ###\n'
 '# Button Types\n'
 '#     0   OK button. \n'
 '#     1   OK and Cancel buttons. \n'
 '#     2   Abort, Retry, and Ignore buttons. \n'
 '#     3   Yes, No, and Cancel buttons. \n'
 '#     4   Yes and No buttons. \n'
 '#     5   Retry and Cancel buttons.    \n'
 '# Icon Types \n'
 '#     16  "Stop Mark" icon. \n'
 '#     32  "Question Mark" icon. \n'
 '#     48  "Exclamation Mark" icon. \n'
 '#     64  "Information Mark" icon. \n'
 '# \n'
 '# Possible values for IntButton the return value:\n'
 '#    1  OK button \n'
 '#    2  Cancel button and Red cross\n'
 '#    3  Abort button \n'
 '#    4  Retry button \n'
 '#    5  Ignore button \n'
 '#    6  Yes button \n'
 '#    7  No button\n'
 '### ### ###\n'
 '\n'
 'function log($msg = "") {\n'
 '    # Output message to stdout (can be edited for logging to a file)\n'
 '    Write-Output $msg;\n'
 '}\n'
 '\n'
 'function promptContinue($message, $icon=32){ log $message; return }\n'
 '\n'
 'function infoPopup($message, $timeout=1, $icon=64){ log $message; return 1 }\n'
 '\n'
 '\n'
 'function RemoveSoftware($name, $displayName=$name){\n'
 '    # Ask user if they wants to remove the application(s) matching a name if it is\n'
 '    # installed and removable. $displayName is shown to the user. $name is used to\n'
 '    # match the application(s) to remove.\n'
 '    $t = Get-AppxPackage *$name*\n'
 '    $nonRemovable =  $t|Where-Object{$_.NonRemovable -eq $True}\n'
 '    $t =  $t|Where-Object{$_.NonRemovable -eq $False}\n'
 '    $r = 0\n'
 '    $n = $t.length\n'
 '    if ($nonRemovable.length -gt 0){\n'
 "        $nr_name = ($nonRemovable.Name -join ', ')\n"
 '        log "[NoRM] - Packages $nr_name cannot be удалено."\n'
 '        if ($n -eq 0 ){\n'
 '            return ($nonRemovable.length * -1)\n'
 '        }\n'
 '    }\n'
 '    if ( $n -eq 1 ){ \n'
 '        ## PROMPT TO REMOVE ONE PACKAGE ##\n'
 '        $pkg = $t.name\n'
 '        log "[one ] - Package $pkg installed."\n'
 '        $r = 6\n'
 '\n'
 '    } elseif ($n -gt 1){        \n'
 '        ## PROMPT TO REMOVE MANY PACKAGES ##\n'
 '        log "[many] - $n package for *$name*."\n'
 '        $list = ($t.name -join ", ")\n'
 '        $r = 6\n'
 '    } else {\n'
 '        log "[none] - Package $name не установлено."\n'
 '        return\n'
 '    }\n'
 '\n'
 '    if (($r -eq 6)){\n'
 '        # REMOVE PACKAGE IF USER ACCEPTED ##\n'
 '        $t | Remove-AppxPackage\n'
 '        if ($? -eq $False){\n'
 '            # If an error happened during deinstallation warn user\n'
 '            log "[ERR ] Package $displayName not удалено."\n'
 '            log "Не удалось удалить $displayName."\n'
 '            return 0\n'
 '        }\n'
 '        log "[DEL ] Package $displayName удалено."\n'
 '        # $wshell.Popup("$displayName удалено.", 1, "Удаление приложения", 64)\n'
 '        infoPopup("$displayName удалено.")\n'
 '        return $n\n'
 '    }\n'
 '    log "[skip] Пропуск $displayName..."\n'
 '    return\n'
 '}\n'
 '\n'
 '### TO BE REMOVED ###\n'
 'promptContinue("Начать удаление приложений, которые обычно можно удалить.")\n'
 '\n'
 'RemoveSoftware "CandyCrushSaga" "CandyCrush" # CandyCrushSaga\n'
 'RemoveSoftware "wallet" "Microsoft Pay"  # Microsoft Wallet (Microsoft Pay)\n'
 'RemoveSoftware "skypeapp"       # App Get Skype\n'
 'RemoveSoftware "officehub"      # App Get Office\n'
 'RemoveSoftware "getstarted"     # Get Started or Tips\n'
 'RemoveSoftware "solitaire"      # Microsoft Solitaire Collection\n'
 'RemoveSoftware "bing"           # Money, News, Sports and Weather apps together\n'
 '###  Single bing softwares (Skipped if bing is selected above) ###\n'
 'RemoveSoftware "bingfinance"    # Money\n'
 'RemoveSoftware "bingweather"    # Weather\n'
 'RemoveSoftware "bingnews"       # News\n'
 'RemoveSoftware "bingsports"     # Sports\n'
 '## \n'
 'RemoveSoftware "onenote"        # OneNote\n'
 'RemoveSoftware "sway"           # Sway\n'
 'RemoveSoftware "oneconnect"     # Paid Wi-Fi & Cellular\n'
 'RemoveSoftware "cortana"        # Cortana used to be Non-Removable but is removable on some version of '
 'Windows\n'
 'RemoveSoftware "Microsoft.549981C3F5F10" "Cortana" # Alias for cortana on some version of Windows\n'
 '# Windows 11 most preinstalled apps\n'
 'RemoveSoftware "tiktok"\n'
 'RemoveSoftware "twitter"\n'
 'RemoveSoftware "instagram"\n'
 'RemoveSoftware "BubbleWitchSaga"\n'
 'RemoveSoftware "MarchOfEmpires"\n'
 'RemoveSoftware "Disney"\n'
 'RemoveSoftware "spotify"\n'
 'RemoveSoftware "hulu"\n'
 'RemoveSoftware "photoshop"\n'
 'RemoveSoftware "picsart"\n'
 'RemoveSoftware "Facebook"\n'
 '\n'
 '### RECOMMENDED FOR REMOVAL ###\n'
 'promptContinue("Продолжить удаление приложений, рекомендованных к удалению.")\n'
 '\n'
 'RemoveSoftware "phone"          # Phone and Phone Companion apps together\n'
 'RemoveSoftware "feedback" "Feedback Hub" # Feedback Hub\n'
 'RemoveSoftware "xbox"           # All Xbox Apps\n'
 'RemoveSoftware "communicationsapps"  # Calendar and Mail apps together\n'
 'RemoveSoftware "todos"\n'
 'RemoveSoftware "maps"           # Maps\n'
 'RemoveSoftware "messaging"      # Messaging and Skype Video apps together\n'
 'RemoveSoftware "onedrive"       # OneDrive Connect\n'
 'RemoveSoftware "mspaint"        # Paint 3D\n'
 'RemoveSoftware "people"         # People\n'
 'RemoveSoftware "sticky"         # Sticky Notes\n'
 'RemoveSoftware "3dbuilder"      # 3D Builder\n'
 'RemoveSoftware "3d"             # View 3D\n'
 'RemoveSoftware "soundrecorder"  # Voice Recorder\n'
 'RemoveSoftware "holographic"    # Windows Holographic\n'
 'RemoveSoftware "mixedReality" "Mixed Reality Portal" \n'
 'RemoveSoftware "Dolby"\n'
 'RemoveSoftware "Teams"\n'
 '# Windows 11 Specific\n'
 'RemoveSoftware "Clipchamp" "Clipchamp Video Editor"\n'
 'RemoveSoftware "GetHelp" # GetHelp Application\n'
 'RemoveSoftware "GamingApp" # GetHelp Application\n'
 '\n'
 '# Dell Laptop Specific\n'
 'RemoveSoftware "partnerpromo"  "Dell PromoApp"\n'
 'RemoveSoftware "dell*connect"  "Dell Connect Apps"\n'
 'RemoveSoftware "dellCustomer"  "Dell Customer Connect"\n'
 'RemoveSoftware "dellMobile"    "Dell Mobile Connect"\n'
 'RemoveSoftware "myDell"        "My Dell"\n'
 '\n'
 '### UNRECOMMENDED REMOVAL ###\n'
 'promptContinue("Продолжить удаление приложений, которые не рекомендуется удалять.")\n'
 '\n'
 'RemoveSoftware "calculator"     # Calculator\n'
 'RemoveSoftware "camera"         # Camera\n'
 'RemoveSoftware "alarms"         # Alarms & Clock\n'
 'RemoveSoftware "appconnector"   # App Connector\n'
 'infoPopup("Готово", 0)\n')

EDGE_REMOVAL_PS = ("$ErrorActionPreference = 'SilentlyContinue'\n"
 '$alsoRemoveWebView = 1\n'
 "$host.UI.RawUI.WindowTitle = 'Edge Removal'\n"
 "$removeWin32 = @('Microsoft Edge','Microsoft Edge Update')\n"
 "$removeAppx = @('MicrosoftEdge')\n"
 'if ($alsoRemoveWebView -eq 1) {\n'
 "    $removeWin32 += 'Microsoft EdgeWebView'\n"
 "    $removeAppx += 'Win32WebViewHost'\n"
 '}\n'
 'try {\n'
 "    $type = [Uri].Module.GetType('System.Diagnostics.Process')\n"
 "    $method = $type.GetMethods(42) | Where-Object { $_.Name -eq 'SetPrivilege' } | Select-Object -First 1\n"
 "    'SeSecurityPrivilege','SeTakeOwnershipPrivilege','SeBackupPrivilege','SeRestorePrivilege' | "
 'ForEach-Object { $null = $method.Invoke($null, @($_, 2)) }\n'
 '} catch {}\n'
 "foreach ($p in 'HKLM\\SOFTWARE\\Policies','HKLM\\SOFTWARE','HKLM\\SOFTWARE\\WOW6432Node') {\n"
 '    cmd /c "reg add `"$p\\Microsoft\\EdgeUpdate`" /f /v InstallDefault /d 0 /t reg_dword >nul 2>nul"\n'
 '    cmd /c "reg add `"$p\\Microsoft\\EdgeUpdate`" /f /v Install{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062} /d 0 '
 '/t reg_dword >nul 2>nul"\n'
 '    cmd /c "reg add `"$p\\Microsoft\\EdgeUpdate`" /f /v Install{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5} /d 1 '
 '/t reg_dword >nul 2>nul"\n'
 '    cmd /c "reg add `"$p\\Microsoft\\EdgeUpdate`" /f /v DoNotUpdateToEdgeWithChromium /d 1 /t reg_dword '
 '>nul 2>nul"\n'
 '}\n'
 "$edgeUpdate = 'Microsoft\\EdgeUpdate\\Clients\\{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}'\n"
 "foreach ($p in 'HKLM\\SOFTWARE','HKLM\\SOFTWARE\\Wow6432Node') {\n"
 '    cmd /c "reg add `"$p\\$edgeUpdate\\Commands\\on-logon-autolaunch`" /f /v CommandLine /d systray.exe '
 '>nul 2>nul"\n'
 '    cmd /c "reg add `"$p\\$edgeUpdate\\Commands\\on-logon-startup-boost`" /f /v CommandLine /d systray.exe '
 '>nul 2>nul"\n'
 '    cmd /c "reg add `"$p\\$edgeUpdate\\Commands\\on-os-upgrade`" /f /v CommandLine /d systray.exe >nul '
 '2>nul"\n'
 '}\n'
 "foreach ($hk in 'HKCU','HKLM') {\n"
 "    foreach ($wow in '','\\Wow6432Node') {\n"
 '        foreach ($i in $removeWin32) {\n'
 '            cmd /c "reg delete `"$hk\\SOFTWARE$wow\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\$i`" /f '
 '/v NoRemove >nul 2>nul"\n'
 '            cmd /c "reg add `"$hk\\SOFTWARE$wow\\Microsoft\\EdgeUpdateDev`" /f /v AllowUninstall /d 1 /t '
 'reg_dword >nul 2>nul"\n'
 '        }\n'
 '    }\n'
 '}\n'
 '$setup = @()\n'
 "foreach ($folderName in 'LocalApplicationData','ProgramFilesX86','ProgramFiles') {\n"
 '    $folder = [Environment]::GetFolderPath($folderName)\n'
 '    if ($folder) {\n'
 "        $root = Join-Path $folder 'Microsoft'\n"
 '        if (Test-Path $root) {\n'
 '            $setup += Get-ChildItem -LiteralPath $root -Filter setup.exe -Recurse -ErrorAction '
 "SilentlyContinue | Where-Object { $_.FullName -match '\\\\Microsoft\\\\Edge' }\n"
 '        }\n'
 '    }\n'
 '}\n'
 "foreach ($p in 'MicrosoftEdgeUpdate','chredge','msedge','edge','msedgewebview2','Widgets') {\n"
 '    Stop-Process -Name $p -Force -ErrorAction SilentlyContinue\n'
 '}\n'
 '$provisioned = Get-AppxProvisionedPackage -Online\n'
 '$appxPackage = Get-AppxPackage -AllUsers\n'
 "$store = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Appx\\AppxAllUserStore'\n"
 "$storeReg = $store.Replace(':','')\n"
 "$users = @('S-1-5-18')\n"
 'if (Test-Path $store) {\n'
 "    $users += (Get-ChildItem $store | Where-Object { $_.PSChildName -like '*S-1-5-21*' }).PSChildName\n"
 '}\n'
 'foreach ($choice in $removeAppx) {\n'
 '    if ([string]::IsNullOrWhiteSpace($choice)) { continue }\n'
 '    foreach ($appx in ($provisioned | Where-Object { $_.PackageName -like "*$choice*" })) {\n'
 '        $family = ($appxPackage | Where-Object { $_.Name -eq $appx.DisplayName } | Select-Object -First '
 '1).PackageFamilyName\n'
 '        if ($family) { cmd /c "reg add `"$storeReg\\Deprovisioned\\$family`" /f >nul 2>nul" }\n'
 '        cmd /c "dism /online /remove-provisionedappxpackage /packagename:$($appx.PackageName) >nul 2>nul"\n'
 '    }\n'
 '    foreach ($appx in ($appxPackage | Where-Object { $_.PackageFullName -like "*$choice*" })) {\n'
 '        $family = $appx.PackageFamilyName\n'
 '        $full = $appx.PackageFullName\n'
 '        $inbox = (Get-ItemProperty "$store\\InboxApplications\\*$($appx.Name)*" -Name Path -ErrorAction '
 'SilentlyContinue).PSChildName\n'
 '        foreach ($app in $inbox) { cmd /c "reg delete `"$storeReg\\InboxApplications\\$app`" /f >nul '
 '2>nul" }\n'
 '        cmd /c "reg add `"$storeReg\\Deprovisioned\\$family`" /f >nul 2>nul"\n'
 '        foreach ($sid in $users) { cmd /c "reg add `"$storeReg\\EndOfLife\\$sid\\$full`" /f >nul 2>nul" }\n'
 '        cmd /c "dism /online /set-nonremovableapppolicy /packagefamily:$family /nonremovable:0 >nul '
 '2>nul"\n'
 '        Remove-AppxPackage -Package $full -AllUsers -ErrorAction SilentlyContinue\n'
 '        foreach ($sid in $users) { cmd /c "reg delete `"$storeReg\\EndOfLife\\$sid\\$full`" /f >nul 2>nul" '
 '}\n'
 '    }\n'
 '}\n'
 "foreach ($p in 'MicrosoftEdgeUpdate','chredge','msedge','edge','msedgewebview2','Widgets') {\n"
 '    Stop-Process -Name $p -Force -ErrorAction SilentlyContinue\n'
 '}\n'
 "$purge = '--uninstall --force-uninstall --system-level'\n"
 'if ($alsoRemoveWebView -eq 1) {\n'
 '    foreach ($s in $setup) { try { Start-Process -FilePath $s.FullName -ArgumentList "--msedgewebview '
 '$purge" -Wait -WindowStyle Hidden } catch {} }\n'
 '}\n'
 'foreach ($s in $setup) {\n'
 '    try { Start-Process -FilePath $s.FullName -ArgumentList "--msedge $purge" -Wait -WindowStyle Hidden } '
 'catch {}\n'
 '}\n'
 'foreach ($i in $removeAppx) {\n'
 '    Get-ChildItem "$store\\EndOfLife" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name '
 '-like "*$i*" } | ForEach-Object { cmd /c "reg delete `"$($_.Name)`" /f >nul 2>nul" }\n'
 '    Get-ChildItem "$store\\Deleted\\EndOfLife" -Recurse -ErrorAction SilentlyContinue | Where-Object { '
 '$_.Name -like "*$i*" } | ForEach-Object { cmd /c "reg delete `"$($_.Name)`" /f >nul 2>nul" }\n'
 '}\n'
 "$appdata = [Environment]::GetFolderPath('ApplicationData')\n"
 "$desktop = [Environment]::GetFolderPath('Desktop')\n"
 "$publicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')\n"
 "$startMenuPrograms = [Environment]::GetFolderPath('CommonPrograms')\n"
 '$shortcuts = @(\n'
 '    "$appdata\\Microsoft\\Internet Explorer\\Quick Launch\\User Pinned\\TaskBar\\Tombstones\\Microsoft '
 'Edge.lnk",\n'
 '    "$appdata\\Microsoft\\Internet Explorer\\Quick Launch\\User Pinned\\TaskBar\\Microsoft Edge.lnk",\n'
 '    "$appdata\\Microsoft\\Internet Explorer\\Quick Launch\\Microsoft Edge.lnk",\n'
 '    "$desktop\\Microsoft Edge.lnk",\n'
 '    "$publicDesktop\\Microsoft Edge.lnk",\n'
 '    "$startMenuPrograms\\Microsoft Edge.lnk"\n'
 ')\n'
 'foreach ($shortcut in $shortcuts) { Remove-Item -LiteralPath $shortcut -Force -ErrorAction '
 'SilentlyContinue }\n'
 '$edgeDirs = @()\n'
 'foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LocalAppData)) {\n'
 '    if ($base) {\n'
 "        $edgeDirs += Join-Path $base 'Microsoft\\Edge'\n"
 "        $edgeDirs += Join-Path $base 'Microsoft\\EdgeCore'\n"
 "        $edgeDirs += Join-Path $base 'Microsoft\\EdgeUpdate'\n"
 "        $edgeDirs += Join-Path $base 'Microsoft\\EdgeWebView'\n"
 '    }\n'
 '}\n'
 "$edgeDirs += Join-Path $env:ProgramData 'Microsoft\\EdgeUpdate'\n"
 'foreach ($dir in $edgeDirs | Select-Object -Unique) {\n'
 '    if (Test-Path $dir) { Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue }\n'
 '}\n')

CREATE_RESTORE_POINT_PS = ('try {\n'
 '    Enable-ComputerRestore -Drive "$env:SystemDrive\\" -ErrorAction SilentlyContinue\n'
 '    Checkpoint-Computer -Description "MahasheWinTweak" -RestorePointType "MODIFY_SETTINGS" -ErrorAction '
 'SilentlyContinue\n'
 '} catch {}\n')

APP_TITLE = 'BBYS'

APP_VERSION = '6.4'


QUICK_CLEANUP_PS = ('$paths = @($env:TEMP, "$env:SystemRoot\\Temp")\n'
 'foreach ($p in $paths) {\n'
 '    if (Test-Path $p) {\n'
 '        Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue | ForEach-Object {\n'
 '            try { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop } catch {}\n'
 '        }\n'
 '    }\n'
 '}\n'
 'try { Clear-RecycleBin -Force -ErrorAction SilentlyContinue } catch {}\n')

def _impl_0__v635_run_remove_preinstalled_apps(self):
    rc = self.run_powershell('Remove preinstalled apps embedded script', REMOVE_PREINSTALLED_APPS_PS_RU, visible=False)
    if rc != 0:
        raise RuntimeError(f'Сценарий удаления предустановленных приложений завершился с кодом {rc}')

def _impl_1_run_powershell(self, description, script, visible=False, timeout=None):
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return self.run(description, [self.exe('WindowsPowerShell\\v1.0\\powershell.exe'), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded], visible=visible, timeout=self.command_timeout('powershell.exe', timeout))

def _impl_2_command_timeout(self, args, timeout=None):
    if timeout is not None:
        return timeout
    if isinstance(args, str):
        line = args.lower()
    else:
        line = ' '.join([str(x) for x in args]).lower()
    if 'dism.exe' in line or 'winget.exe' in line or 'add-appxpackage' in line:
        return 1800
    if 'powershell.exe' in line:
        return 900
    if 'robocopy.exe' in line:
        return 300
    if 'schtasks.exe' in line or 'sc.exe' in line or 'reg.exe' in line or ('taskkill.exe' in line) or ('bcdedit.exe' in line):
        return 45
    if 'ipconfig.exe' in line or 'netsh.exe' in line or 'powercfg.exe' in line:
        return 120
    return 180

def _impl_3_exe(self, name):
    path = self.system32 / name
    return str(path if path.exists() else name)

def _impl_4_run(self, description, args, shell=False, cwd=None, success_codes=None, timeout=None, visible=False, wait=True):
    if success_codes is None:
        success_codes = {0}
    if not self.is_windows():
        self.write_log(f'SKIP: {description}. Требуется Windows.')
        return 1
    if not wait:
        return self.launch_detached(description, args, cwd=cwd, visible=visible)
    effective_timeout = self.command_timeout(args, timeout)
    self.write_log(f'RUN: {description}')
    try:
        creationflags = 0 if visible else getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        startupinfo = None
        if not visible and hasattr(subprocess, 'STARTUPINFO'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, 'STARTF_USESHOWWINDOW', 1)
            startupinfo.wShowWindow = 0
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, shell=shell, cwd=str(cwd or self.app_dir), text=True, encoding='utf-8', errors='replace', creationflags=creationflags, startupinfo=startupinfo)
        try:
            output, _ = process.communicate(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                output, _ = process.communicate(timeout=5)
            except Exception:
                output = ''
            if output:
                for line in output.splitlines():
                    cleaned = line.rstrip()
                    if cleaned:
                        self.write_log(cleaned)
            self.write_log(f'TIMEOUT {effective_timeout}s: {description}')
            return 124
        if output:
            for line in output.splitlines():
                cleaned = line.rstrip()
                if cleaned:
                    self.write_log(cleaned)
        rc = process.returncode
        if rc in success_codes:
            self.write_log(f'OK: {description}')
        else:
            self.write_log(f'FAIL {rc}: {description}')
        return rc
    except FileNotFoundError:
        self.write_log(f'NOT FOUND: {description}')
        return 2
    except Exception as exc:
        self.write_log(f'ERROR: {description}: {exc}')
        return 1

def _impl_5_write_log(self, text):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    line = f'[{timestamp}] {text}'
    try:
        with self.current_log.open('a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass
    if self.callback:
        self.callback(line)

def _impl_6_launch_detached(self, description, args, cwd=None, visible=True):
    if not self.is_windows():
        self.write_log(f'SKIP: {description}. Требуется Windows.')
        return 1
    self.write_log(f'LAUNCH: {description}')
    try:
        flags = 0 if visible else getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        try:
            flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        except Exception:
            pass
        startupinfo = None
        if not visible and hasattr(subprocess, 'STARTUPINFO'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, 'STARTF_USESHOWWINDOW', 1)
            startupinfo.wShowWindow = 0
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(cwd or self.app_dir), creationflags=flags, startupinfo=startupinfo)
        self.write_log(f'OK: {description}')
        return 0
    except FileNotFoundError:
        self.write_log(f'NOT FOUND: {description}')
        return 2
    except Exception as exc:
        self.write_log(f'ERROR: {description}: {exc}')
        return 1

def _impl_7_is_windows(self):
    return os.name == 'nt'

def _impl_8__bbys_restore_standard_path(self):
    required = [os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32'), os.environ.get('SystemRoot', 'C:\\Windows'), os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'Wbem'), os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'WindowsPowerShell', 'v1.0'), os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'OpenSSH')]
    machine = os.environ.get('PATH', '')
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment', 0, winreg.KEY_READ | getattr(winreg, 'KEY_WOW64_64KEY', 0)) as k:
            machine = winreg.QueryValueEx(k, 'Path')[0]
    except Exception:
        pass
    parts = [p for p in str(machine).split(';') if p.strip()]
    for p in required:
        if not any((x.rstrip('\\').lower() == p.rstrip('\\').lower() for x in parts)):
            parts.append(p)
    self.reg_add('HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment', 'Path', 'REG_EXPAND_SZ', ';'.join(parts))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ) as k:
            user = winreg.QueryValueEx(k, 'Path')[0]
    except Exception:
        user = ''
    uparts = [p for p in str(user).split(';') if p.strip()]
    wa = os.path.join(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')), 'Microsoft', 'WindowsApps')
    if not any((x.rstrip('\\').lower() == wa.rstrip('\\').lower() for x in uparts)):
        uparts.append(wa)
    self.reg_add('HKCU\\Environment', 'Path', 'REG_EXPAND_SZ', ';'.join(uparts))
    reg_path = Path(os.environ.get('SystemRoot', 'C:\\Windows')) / 'System32' / 'reg.exe'
    if not reg_path.is_file():
        raise RuntimeError(f'reg.exe не найден: {reg_path}')
    self.write_log(f'PATH восстановлен; reg.exe найден: {reg_path}')

def _impl_9__bbys_reg_add_once(self, key, value=None, typ=None, data=None):
    if getattr(self, '_bbys_optimization_active', False) and value is not None:
        norm_key = str(key).replace('HKEY_LOCAL_MACHINE', 'HKLM').replace('HKEY_CURRENT_USER', 'HKCU').replace('HKEY_CLASSES_ROOT', 'HKCR').lower()
        token = (norm_key, str(value).lower())
        cache = getattr(self, '_bbys_optimization_written_registry', None)
        if cache is None:
            cache = set()
            self._bbys_optimization_written_registry = cache
        if token in cache:
            self.write_log(f'Пропуск дубликата Optimization: {key}\\{value}')
            return 0
        cache.add(token)
    return _BBYS_REG_ADD_BASE(self, key, value, typ, data)

def _impl_10__v635_reg_add(self, key, value=None, typ=None, data=None):
    rc = _V635_REG_ADD(self, key, value, typ, data)
    if rc != 0:
        raise RuntimeError(f"Не удалось записать реестр: {key}\\{value or '(по умолчанию)'} (код {rc})")
    return rc

def _impl_11_reg_add(self, key, value=None, typ=None, data=None):
    args = [self.exe('reg.exe'), 'add', key, '/f']
    if value is not None:
        args.extend(['/v', str(value)])
    if typ is not None:
        args.extend(['/t', str(typ)])
    if data is not None:
        args.extend(['/d', str(data)])
    return self.run(f"Registry add {key} {(value if value else '')}", args)

def _impl_12__v635_enable_edge_disable(self):
    self.write_log('Отключение и удаление Microsoft Edge')
    self.snapshot('disable_edge', ['HKLM\\SOFTWARE\\Policies\\Microsoft\\EdgeUpdate', 'HKLM\\SOFTWARE\\Microsoft\\EdgeUpdate', 'HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate'], [], [Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'Microsoft' / 'Edge', Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')) / 'Microsoft' / 'Edge'])
    rc = self.run_powershell('Edge removal', EDGE_REMOVAL_PS)
    if rc != 0:
        raise RuntimeError(f'Удаление Edge завершилось с кодом {rc}')

def _impl_13_snapshot(self, feature_id, registry_keys=None, services=None, files=None):
    registry_keys = registry_keys or []
    services = services or []
    files = files or []
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    target = self.backup_dir / f'{feature_id}_{stamp}'
    target.mkdir(parents=True, exist_ok=True)
    data = {'feature_id': feature_id, 'created': stamp, 'registry': [], 'services': [], 'files': []}
    # The caller explicitly opts into file backup for Utilman; no automatic system restore point.
    for key in registry_keys:
        safe = re.sub('[^A-Za-z0-9_.-]+', '_', key)
        export_path = target / f'{safe}.reg'
        existed = self.reg_key_exists(key)
        if existed:
            self.reg_export(key, export_path)
        data['registry'].append({'key': key, 'existed': existed, 'file': str(export_path)})
    for service in services:
        data['services'].append({'name': service, 'start_type': self.service_start_type(service), 'state': self.service_state(service)})
    for file_path in files:
        p = Path(file_path)
        item = {'path': str(p), 'existed': p.exists(), 'backup': None, 'is_dir': p.is_dir()}
        try:
            if p.exists():
                dst = target / 'files' / re.sub('[^A-Za-z0-9_.-]+', '_', str(p))
                dst.parent.mkdir(parents=True, exist_ok=True)
                if p.is_dir():
                    shutil.copytree(str(p), str(dst), dirs_exist_ok=True)
                else:
                    shutil.copy2(str(p), str(dst))
                item['backup'] = str(dst)
        except Exception as exc:
            raise RuntimeError(f'Не удалось сохранить исходный файл {p}: {exc}') from exc
        data['files'].append(item)
    self.state_file(feature_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    self.write_log(f'Снимок состояния сохранен: {self.state_file(feature_id)}')
    return data

def _impl_14_state_file(self, feature_id):
    return self.state_dir / f'{feature_id}.json'

def _impl_15_service_state(self, service):
    if not self.is_windows():
        return None
    try:
        process = subprocess.run([self.exe('sc.exe'), 'query', service], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode != 0:
            return None
        if 'RUNNING' in process.stdout:
            return 'running'
        if 'STOPPED' in process.stdout:
            return 'stopped'
        return 'other'
    except Exception:
        return None

def _impl_16__v595_service_start_type(self, service):
    value = None
    try:
        value = _ORIGINAL_V595_SERVICE_START_TYPE(self, service)
    except Exception:
        value = None
    if value is not None:
        return value
    return self.parse_service_start_from_registry(service)

def _impl_17_service_start_type(self, service):
    if not self.is_windows():
        return None
    try:
        process = subprocess.run([self.exe('sc.exe'), 'qc', service], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode != 0:
            return None
        match = re.search('START_TYPE\\s*:\\s*(\\d+)', process.stdout)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def _impl_18__v595_parse_service_start_from_registry(self, service):
    for key in [f'HKLM\\SYSTEM\\CurrentControlSet\\Services\\{service}', f'HKLM\\SYSTEM\\ControlSet001\\Services\\{service}', f'HKLM\\SYSTEM\\ControlSet002\\Services\\{service}']:
        out = self.reg_query(key, 'Start')
        if not out:
            continue
        low = out.lower()
        m = re.search('0x([0-9a-f]+)', low)
        if m:
            try:
                return int(m.group(1), 16)
            except Exception:
                pass
        m = re.search('reg_dword\\s+(\\d+)', low)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return None

def _impl_19_reg_query(self, key, value=None):
    if not self.is_windows():
        return None
    args = [self.exe('reg.exe'), 'query', key]
    if value is not None:
        args.extend(['/v', str(value)])
    try:
        process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return process.stdout if process.returncode == 0 else None
    except Exception:
        return None

def _impl_20__v635_reg_export(self, key, path):
    rc = _V635_REG_EXPORT(self, key, path)
    if rc != 0 or not Path(path).is_file():
        raise RuntimeError(f'Не удалось создать резервную копию реестра: {key} (код {rc})')
    return rc

def _impl_21_reg_export(self, key, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return self.run(f'Registry export {key}', [self.exe('reg.exe'), 'export', key, str(path), '/y'], success_codes={0, 1})

def _impl_22_reg_key_exists(self, key):
    return self.reg_query(key) is not None

def _impl_23_check_utilman_cmd(self):
    return self.hash_file(self.system32 / 'Utilman.exe') is not None and self.hash_file(self.system32 / 'Utilman.exe') == self.hash_file(self.system32 / 'cmd.exe')

def _impl_24_hash_file(self, path):
    import hashlib
    path = Path(path)
    if not path.exists():
        return None
    h = hashlib.sha256()
    try:
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def _impl_25__v635_run_win11_debloat(self):
    command = '& ([scriptblock]::Create((irm "https://debloat.raphi.re/")))'
    rc = self.run('Win11 Debloat', [self.exe('WindowsPowerShell\\v1.0\\powershell.exe'), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command], visible=False, success_codes={0, 1}, timeout=1800)
    if rc == 124:
        raise TimeoutError('Win11 Debloat превысил тайм-аут 30 минут.')
    if rc not in {0, 1}:
        raise RuntimeError(f'Win11 Debloat завершился с кодом {rc}')

def _impl_26___init__(self, callback):
    self.callback = callback
    self.app_dir = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    self.source_dir = self.app_dir / 'source'
    self.appsource_dir = self.source_dir / 'appsource'
    self.temp_dir = self.appsource_dir / 'temp'
    self.log_dir = self.appsource_dir / 'Logs'
    self.backup_dir = self.appsource_dir / 'Backup'
    self.state_dir = self.appsource_dir / 'state'
    self.generated_dir = self.appsource_dir / 'generated'
    for path in [self.source_dir, self.appsource_dir, self.temp_dir, self.log_dir, self.backup_dir, self.state_dir, self.generated_dir]:
        path.mkdir(parents=True, exist_ok=True)
    self.current_log = self.log_dir / f"BBYS_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    self.system_root = Path(os.environ.get('SystemRoot', 'C:\\Windows'))
    self.system32 = self.system_root / 'System32'
    self.write_default_source_files()
    self.write_log(f'Запуск {APP_TITLE} {APP_VERSION}')
    self.write_log(f'Папка приложения: {self.app_dir}')
    self.write_log(f'Папка source: {self.source_dir}')
    self.write_log(f'Папка appsource: {self.appsource_dir}')
    self.write_log(f'Лог: {self.current_log}')

def _impl_27_write_default_source_files(self):
    folders = [self.source_dir / 'ExplorerBlur', self.source_dir / 'Windows Defender', self.source_dir / 'Personalization', self.source_dir / 'Personalization' / 'ContextMenu', self.source_dir / 'Personalization' / 'ContextMenu' / '_Source', self.source_dir / 'Personalization' / 'recycle-bin-themes', self.source_dir / 'Personalization' / 'recycle-bin-themes' / 'themes', self.source_dir / 'Personalization' / 'recycle-bin-themes' / 'assets', self.source_dir / 'Utility']
    for path in folders:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

def _impl_28_migrate_legacy_app_dirs(self):
    mapping = {'temp': self.temp_dir, 'Logs': self.log_dir, 'Backup': self.backup_dir, 'state': self.state_dir, 'generated': self.generated_dir}
    for name, target in mapping.items():
        legacy = self.source_dir / name
        if not legacy.exists() or legacy.resolve() == target.resolve():
            continue
        try:
            for item in legacy.iterdir():
                destination = target / item.name
                if item.is_dir():
                    if not destination.exists():
                        shutil.copytree(str(item), str(destination))
                elif item.is_file() and (not destination.exists()):
                    shutil.copy2(str(item), str(destination))
        except Exception:
            pass

def _impl_29__v635_run_defender_tool(self):
    path = self.source_dir / 'Windows Defender' / 'DefenderRemover.exe'
    rc = self.shell_execute('Windows Defender utility', path, '', 'runas')
    if rc != 0:
        raise RuntimeError(f'Не удалось запустить DefenderRemover.exe (код ShellExecute {rc})')

def _impl_30_shell_execute(self, description, path, params='', verb='runas'):
    if not self.is_windows():
        self.write_log(f'SKIP: {description}. Требуется Windows.')
        return 1
    path = str(path)
    if not Path(path).exists():
        self.write_log(f'NOT FOUND: {path}')
        return 2
    try:
        self.write_log(f'RUN: {description}')
        result = ctypes.windll.shell32.ShellExecuteW(None, verb, path, params, str(Path(path).parent), 1)
        rc = 0 if int(result) > 32 else int(result)
        self.write_log(f'OK: {description}' if rc == 0 else f'FAIL {rc}: {description}')
        return rc
    except Exception as exc:
        self.write_log(f'ERROR: {description}: {exc}')
        return 1

def _impl_31_disable_utilman_cmd(self):
    self.restore_snapshot('utilman_cmd')

def _impl_32__v635_restore_snapshot(self, feature_id):
    path = self.state_file(feature_id)
    if not path.exists():
        self.write_log(f'Снимок состояния для {feature_id} не найден, применяется fallback-откат')
        return False
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError(f'Снимок {feature_id} повреждён и не может быть прочитан: {exc}') from exc
    errors = []
    for item in data.get('registry', []):
        key = item.get('key')
        try:
            if item.get('existed'):
                backup_name = item.get('file')
                backup = Path(backup_name) if backup_name else None
                if not backup or not backup.is_file():
                    raise FileNotFoundError(f'нет REG-файла для существовавшего раздела {key}')
                self.reg_import(backup)
            elif key:
                self.reg_delete(key)
        except Exception as exc:
            errors.append(f'реестр {key}: {exc}')
    for item in data.get('services', []):
        service = item.get('name')
        start_type = item.get('start_type')
        state = item.get('state')
        mapping = {2: 'auto', 3: 'demand', 4: 'disabled'}
        try:
            if service and start_type in mapping:
                self.sc_config(service, mapping[start_type])
                if state == 'running':
                    self.sc_start(service)
                elif state == 'stopped':
                    self.sc_stop(service)
        except Exception as exc:
            errors.append(f'служба {service}: {exc}')
    for item in data.get('files', []):
        target = Path(item.get('path'))
        backup = Path(item.get('backup')) if item.get('backup') else None
        try:
            if item.get('existed'):
                if not backup or not backup.exists():
                    raise FileNotFoundError(f'резервная копия для {target} отсутствует')
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(str(target))
                    else:
                        target.unlink()
                if item.get('is_dir'):
                    shutil.copytree(str(backup), str(target), dirs_exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(backup), str(target))
            elif target.exists():
                if target.is_dir():
                    shutil.rmtree(str(target))
                else:
                    target.unlink()
        except Exception as exc:
            errors.append(f'файл {target}: {exc}')
    if errors:
        message = '; '.join(errors[:8])
        self.write_log(f'Ошибки восстановления {feature_id}: {message}')
        raise RuntimeError(f'Восстановление {feature_id} выполнено не полностью: {message}')
    self.write_log(f'Снимок состояния восстановлен: {feature_id}')
    return True

def _impl_33__v635_sc_stop(self, service):
    rc = _V635_SC_STOP(self, service)
    if rc not in {0, 1060, 1062}:
        raise RuntimeError(f'Не удалось остановить службу {service} (код {rc})')
    return rc

def _impl_34_sc_stop(self, service):
    return self.run(f'Service {service} stop', [self.exe('sc.exe'), 'stop', service], success_codes={0, 1060, 1062})

def _impl_35__v635_sc_start(self, service):
    rc = _V635_SC_START(self, service)
    if rc not in {0, 1056, 1060}:
        raise RuntimeError(f'Не удалось запустить службу {service} (код {rc})')
    return rc

def _impl_36_sc_start(self, service):
    return self.run(f'Service {service} start', [self.exe('sc.exe'), 'start', service], success_codes={0, 1056, 1060})

def _impl_37_reg_delete(self, key, value=None):
    args = [self.exe('reg.exe'), 'delete', key, '/f']
    if value is not None:
        args.extend(['/v', str(value)])
    return self.run(f"Registry delete {key} {(value if value else '')}", args, success_codes={0, 1})

def _impl_38__v635_sc_config(self, service, start_type):
    rc = _V635_SC_CONFIG(self, service, start_type)
    if rc not in {0, 1060}:
        raise RuntimeError(f'Не удалось изменить тип запуска службы {service} (код {rc})')
    return rc

def _impl_39_sc_config(self, service, start_type):
    return self.run(f'Service {service} start={start_type}', [self.exe('sc.exe'), 'config', service, 'start=', start_type], success_codes={0, 1060})

def _impl_40__v635_reg_import(self, path):
    rc = _V635_REG_IMPORT(self, path)
    if rc != 0:
        raise RuntimeError(f'Не удалось импортировать резервную копию реестра: {path} (код {rc})')
    return rc

def _impl_41_reg_import(self, path):
    return self.run(f'Registry import {Path(path).name}', [self.exe('reg.exe'), 'import', str(path)])

def _impl_42__v635_run_remove_windows_ai_script(self):
    command = '& ([scriptblock]::Create((irm "https://raw.githubusercontent.com/zoicware/RemoveWindowsAI/main/RemoveWindowsAi.ps1")))'
    rc = self.run('Disable Windows 11 AI remote RemoveWindowsAi.ps1', [self.exe('WindowsPowerShell\\v1.0\\powershell.exe'), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command], visible=False, success_codes={0, 1}, timeout=1800)
    if rc == 124:
        raise TimeoutError('Отключение Windows 11 AI превысило тайм-аут 30 минут.')
    if rc not in {0, 1}:
        raise RuntimeError(f'RemoveWindowsAi.ps1 завершился с кодом {rc}')

def _impl_43_enable_utilman_cmd(self):
    raise RuntimeError('Подмена системных компонентов экрана входа не поддерживается BBYS. Для восстановления используйте штатные инструменты Windows.')


def _impl_44_reset_cache_and_network(self):
    self.write_log('Сброс кеша и сети')
    self.run('Flush DNS', [self.exe('ipconfig.exe'), '/flushdns'], success_codes={0, 1})
    self.run('Release IP', [self.exe('ipconfig.exe'), '/release'], success_codes={0, 1})
    self.run('Renew IP', [self.exe('ipconfig.exe'), '/renew'], success_codes={0, 1})
    self.run('Winsock reset', [self.exe('netsh.exe'), 'winsock', 'reset'], success_codes={0, 1})
    self.run('IP stack reset', [self.exe('netsh.exe'), 'int', 'ip', 'reset'], success_codes={0, 1})
    self.run('ARP cache reset', [self.exe('arp.exe'), '-d', '*'], success_codes={0, 1})
    self.quick_cleanup()
    self.run('Windows Store cache reset', ['wsreset.exe'], success_codes={0, 1})

def _impl_45_quick_cleanup(self):
    self.run_powershell('Quick cleanup', QUICK_CLEANUP_PS)

_BBYS_REG_ADD_BASE = _impl_10__v635_reg_add

_V635_REG_ADD = _impl_11_reg_add

_ORIGINAL_V595_SERVICE_START_TYPE = _impl_17_service_start_type

_V635_REG_EXPORT = _impl_21_reg_export

_V635_SC_STOP = _impl_34_sc_stop

_V635_SC_START = _impl_36_sc_start

_V635_SC_CONFIG = _impl_39_sc_config

_V635_REG_IMPORT = _impl_41_reg_import

class WindowsTweaksEngine:
    run_powershell = _impl_1_run_powershell
    run = _impl_4_run
    exe = _impl_3_exe
    command_timeout = _impl_2_command_timeout
    write_log = _impl_5_write_log
    is_windows = _impl_7_is_windows
    launch_detached = _impl_6_launch_detached
    reg_add = _impl_9__bbys_reg_add_once
    snapshot = _impl_13_snapshot
    reg_key_exists = _impl_22_reg_key_exists
    reg_export = _impl_20__v635_reg_export
    state_file = _impl_14_state_file
    service_start_type = _impl_16__v595_service_start_type
    service_state = _impl_15_service_state
    parse_service_start_from_registry = _impl_18__v595_parse_service_start_from_registry
    reg_query = _impl_19_reg_query
    hash_file = _impl_24_hash_file
    migrate_legacy_app_dirs = _impl_28_migrate_legacy_app_dirs
    write_default_source_files = _impl_27_write_default_source_files
    shell_execute = _impl_30_shell_execute
    restore_snapshot = _impl_32__v635_restore_snapshot
    reg_import = _impl_40__v635_reg_import
    sc_config = _impl_38__v635_sc_config
    reg_delete = _impl_37_reg_delete
    sc_start = _impl_35__v635_sc_start
    sc_stop = _impl_33__v635_sc_stop
    quick_cleanup = _impl_45_quick_cleanup
    __init__ = _impl_26___init__
    check_utilman_cmd = _impl_23_check_utilman_cmd
    disable_utilman_cmd = _impl_31_disable_utilman_cmd
    enable_edge_disable = _impl_12__v635_enable_edge_disable
    enable_utilman_cmd = _impl_43_enable_utilman_cmd
    reset_cache_and_network = _impl_44_reset_cache_and_network
    restore_standard_path = _impl_8__bbys_restore_standard_path
    run_defender_tool = _impl_29__v635_run_defender_tool
    run_remove_preinstalled_apps = _impl_0__v635_run_remove_preinstalled_apps
    run_remove_windows_ai_script = _impl_42__v635_run_remove_windows_ai_script
    run_win11_debloat = _impl_25__v635_run_win11_debloat

APP_TITLE = "BBYS"
APP_VERSION = "6.4.1"
