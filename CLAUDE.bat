@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "UV=%USERPROFILE%\.local\bin\uv.exe"
set "VENV=%CD%\.venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%UV%" (
  echo ERROR: uv was not found.
  pause
  exit /b 1
)

if not exist "%PY%" "%UV%" venv "%VENV%" --python 3.13
"%UV%" pip install --python "%PY%" -r requirements-vision.txt --quiet
if errorlevel 1 (
  echo ERROR: dependency installation failed.
  pause
  exit /b 1
)

"%PY%" -u -B launch_golem.py %*
exit /b %errorlevel%
