@echo off
setlocal EnableExtensions DisableDelayedExpansion
title M49 - Khoi dong
cd /d "%~dp0"

if /i "%~1"=="backend" goto backend
if /i "%~1"=="frontend" goto frontend

echo Dang kiem tra moi truong M49...
if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co moi truong .venv Python 3.14. Xem README.md.
    goto failed
)
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3, 14), 'Can Python 3.14'; import uvicorn, fastapi, sqlmodel, psycopg, PIL, python_multipart"
if errorlevel 1 (
    echo [LOI] Python hoac thu vien backend chua dung. Xem README.md de cai dat.
    goto failed
)
where node >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua tim thay Node.js. Hay cai Node.js 22 va mo lai file nay.
    goto failed
)
node -e "if (Number(process.versions.node.split('.')[0]) < 22) { console.error('Can Node.js 22 tro len'); process.exit(1); }"
if errorlevel 1 goto failed
if not exist "frontend\node_modules\vite\bin\vite.js" (
    echo [LOI] Chua cai thu vien frontend. Chay trong thu muc frontend:
    echo npx --yes pnpm@10.11.0 install --frozen-lockfile
    goto failed
)
if /i "%~1"=="--check" (
    echo [OK] Moi truong san sang. Chua khoi dong server.
    exit /b 0
)

powershell.exe -NoProfile -Command "$busy = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 8000,5173 }); if ($busy.Count) { Write-Host '[LOI] Cong 8000 hoac 5173 dang duoc su dung. Dong server cu truoc khi chay lai.'; exit 1 }"
if errorlevel 1 goto failed

start "M49 Backend" "%ComSpec%" /d /c ""%~f0" backend"
start "M49 Frontend" "%ComSpec%" /d /c ""%~f0" frontend"
echo Dang cho backend va frontend san sang...
powershell.exe -NoProfile -Command "$ready = $false; for ($i = 0; $i -lt 30; $i++) { try { $h = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 1; $f = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 1; if ($h.status -eq 'ok' -and $f.StatusCode -eq 200) { $ready = $true; break } } catch {}; Start-Sleep -Seconds 1 }; if (-not $ready) { Write-Host '[LOI] Server chua san sang. Xem loi trong hai cua so M49.'; exit 1 }; Start-Process 'http://127.0.0.1:5173/'"
if errorlevel 1 goto failed
echo Da mo http://127.0.0.1:5173/
echo Giu hai cua so M49 Backend va M49 Frontend trong khi su dung.
echo De dung: nhan Ctrl+C trong tung cua so, roi dong cua so.
exit /b 0

:backend
title M49 Backend - Python 3.14 - Port 8000
cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
echo Backend da dung. Xem thong bao ben tren neu co loi.
pause
exit /b

:frontend
title M49 Frontend - Port 5173
cd /d "%~dp0frontend"
node "node_modules\vite\bin\vite.js" --host 127.0.0.1 --port 5173 --strictPort
echo Frontend da dung. Xem thong bao ben tren neu co loi.
pause
exit /b

:failed
if /i "%~1"=="--check" exit /b 1
pause
exit /b 1
