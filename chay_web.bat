@echo off
setlocal EnableExtensions DisableDelayedExpansion
title M49 - Khoi dong
cd /d "%~dp0"

if not defined M49_BACKEND_PORT set "M49_BACKEND_PORT=8000"
if not defined M49_FRONTEND_PORT set "M49_FRONTEND_PORT=5173"

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

rem Clear defaults so a failed port selection cannot reuse stale ports.
set "M49_BACKEND_PORT="
set "M49_FRONTEND_PORT="
for /f "tokens=1,2 delims=," %%A in ('powershell.exe -NoProfile -Command "$backend = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0); $frontend = $null; try { $backend.Start(); $frontend = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0); $frontend.Start(); Write-Output ($backend.LocalEndpoint.Port.ToString() + [char]44 + $frontend.LocalEndpoint.Port.ToString()) } finally { $backend.Stop(); if ($frontend) { $frontend.Stop() } }"') do (
    set "M49_BACKEND_PORT=%%A"
    set "M49_FRONTEND_PORT=%%B"
)
if not defined M49_BACKEND_PORT (
    echo [LOI] Khong the chon cong trong. Kiem tra PowerShell va thu lai.
    goto failed
)
if not defined M49_FRONTEND_PORT (
    echo [LOI] Khong the chon cong trong. Kiem tra PowerShell va thu lai.
    goto failed
)
set "CORS_ORIGINS=http://127.0.0.1:%M49_FRONTEND_PORT%"

start "M49 Backend" "%ComSpec%" /d /c ""%~f0" backend"
start "M49 Frontend" "%ComSpec%" /d /c ""%~f0" frontend"
echo Dang cho backend va frontend san sang...
powershell.exe -NoProfile -Command "$backend = $env:M49_BACKEND_PORT; $frontend = $env:M49_FRONTEND_PORT; $ready = $false; for ($i = 0; $i -lt 30; $i++) { try { $h = Invoke-RestMethod ('http://127.0.0.1:'+$backend+'/api/health') -TimeoutSec 1; $f = Invoke-WebRequest ('http://127.0.0.1:'+$frontend+'/') -UseBasicParsing -TimeoutSec 1; if ($h.status -eq 'ok' -and $f.StatusCode -eq 200) { $ready = $true; break } } catch {}; Start-Sleep -Seconds 1 }; if (-not $ready) { Write-Host '[LOI] Server chua san sang. Xem loi trong hai cua so M49.'; exit 1 }; Start-Process ('http://127.0.0.1:'+$frontend+'/')"
if errorlevel 1 goto failed
echo Da mo http://127.0.0.1:%M49_FRONTEND_PORT%/
echo Backend: 127.0.0.1:%M49_BACKEND_PORT% ^| Frontend: 127.0.0.1:%M49_FRONTEND_PORT%
echo Giu hai cua so M49 Backend va M49 Frontend trong khi su dung.
echo De dung: nhan Ctrl+C trong tung cua so, roi dong cua so.
exit /b 0

:backend
title M49 Backend - Python 3.14 - Port %M49_BACKEND_PORT%
cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port %M49_BACKEND_PORT%
echo Backend da dung. Xem thong bao ben tren neu co loi.
pause
exit /b

:frontend
title M49 Frontend - Port %M49_FRONTEND_PORT%
cd /d "%~dp0frontend"
node "node_modules\vite\bin\vite.js" --host 127.0.0.1 --port %M49_FRONTEND_PORT% --strictPort
echo Frontend da dung. Xem thong bao ben tren neu co loi.
pause
exit /b

:failed
if /i "%~1"=="--check" exit /b 1
pause
exit /b 1
