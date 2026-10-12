@echo off
setlocal
set "NameApp=BBYS"
set "ProjectFavicon=%~dp0BBYS_icon_pack\BBYS.ico"
if not defined BBYS_PYTHON set "BBYS_PYTHON=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not exist "%BBYS_PYTHON%" (
  echo Python not found. Set BBYS_PYTHON to python.exe.
  exit /b 1
)
"%BBYS_PYTHON%" "%~dp0build_bbys.py"
exit /b %errorlevel%
