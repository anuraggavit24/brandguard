@echo off
setlocal
title BrandGuard
cd /d "%~dp0"

echo ==================================================
echo   BrandGuard - starting
echo ==================================================
echo.

rem ---- 1. find Python ------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python was not found. Install Python 3.11 or newer from python.org
  echo and tick "Add Python to PATH" in the installer, then run this again.
  pause
  exit /b 1
)

rem ---- 2. create the virtual environment on first run ----------------------
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating the environment. This takes a minute.
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the environment.
    pause
    exit /b 1
  )
)

rem ---- 3. install packages when needed -------------------------------------
if not exist ".venv\deps_installed.txt" (
  echo Installing packages. This only happens once.
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Package install failed. Check your internet connection and run again.
    pause
    exit /b 1
  )
  echo done> ".venv\deps_installed.txt"
)

rem ---- 4. ffmpeg check -----------------------------------------------------
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo WARNING: ffmpeg was not found, so audio cannot be read from videos.
  echo Install it with:  winget install Gyan.FFmpeg
  echo then close this window and run this file again.
  echo.
  pause
)

rem ---- 5. speech key: use saved one, otherwise ask once --------------------
if not defined GROQ_API_KEY (
  if exist "groq_key.txt" set /p GROQ_API_KEY=<"groq_key.txt"
)
if not defined GROQ_API_KEY (
  echo.
  echo Paste your Groq API key and press Enter.
  echo It is saved only on this computer in groq_key.txt and is never uploaded.
  set /p GROQ_API_KEY=Key:
  if defined GROQ_API_KEY echo %GROQ_API_KEY%> "groq_key.txt"
)
if not defined GROQ_API_KEY (
  echo No key entered. The site will open, but speech review will not work.
)

rem ---- 6. settings for the local build -------------------------------------
set "LINKS_ENABLED=1"
set "PORT=8000"

rem ---- 7. open the browser a few seconds after the server starts -----------
start "" /b cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:%PORT%"

echo.
echo BrandGuard is running at http://localhost:%PORT%
echo Keep this window open while you use it. Close it to stop BrandGuard.
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port %PORT%

echo.
echo BrandGuard stopped.
pause
