@echo off
rem Double-click launcher for the local SEO Analysis workbench.
rem Usage: SEO-Workbench.bat [port]      default port 8765
setlocal EnableExtensions
title SEO Analysis Workbench

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8765"

call "%~dp0scripts\_find-python.bat"
if not defined SEO_PY goto :nopython

rem Share the project-local workspace the .cmd launcher creates, when it exists.
set "SEO_CONFIG="
if exist "%~dp0.seo-workbench\config.toml" set SEO_CONFIG=--config-file "%~dp0.seo-workbench\config.toml"

set "URL=http://127.0.0.1:%PORT%/"
echo ============================================================
echo   SEO Analysis Workbench
echo ============================================================
echo   Address      %URL%
echo   Interpreter  %SEO_PY_LABEL%
echo.
echo   Leave this window open while you work.
echo   Press Ctrl+C to stop the workbench.
echo ============================================================
echo.

start "SEO Analysis browser" /min cmd /c "timeout /t 2 /nobreak >nul & start %URL%"

%SEO_PY% %SEO_CONFIG% -m seo_analysis serve --port %PORT%
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
  echo Workbench stopped.
) else (
  echo Workbench exited with code %CODE%.
  echo If port %PORT% is already in use, try:  "%~nx0" 8899
)
echo.
pause
exit /b %CODE%

:nopython
echo ============================================================
echo   No Python interpreter could import seo_analysis
echo ============================================================
echo.
echo   From the repository folder, create the environment once:
echo.
echo       py -3.12 -m venv .venv
echo       .venv\Scripts\python -m pip install -e .
echo.
echo   Or point this launcher at an interpreter that already has it:
echo.
echo       set SEO_ANALYSIS_PYTHON=C:\path\to\python.exe
echo.
pause
exit /b 1
