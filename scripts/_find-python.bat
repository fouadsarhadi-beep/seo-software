@echo off
rem Locate a Python interpreter that can import seo_analysis and export it as SEO_PY.
rem Shared by "SEO-Workbench.bat" and "seo.bat". Override with SEO_ANALYSIS_PYTHON.
setlocal EnableExtensions
set "SEO_PY="
set "SEO_PY_LABEL="

if defined SEO_ANALYSIS_PYTHON call :probe "%SEO_ANALYSIS_PYTHON%" "SEO_ANALYSIS_PYTHON"
if defined SEO_PY goto :export

call :probe "%~dp0..\.venv\Scripts\python.exe" "repository .venv"
if defined SEO_PY goto :export

call :probe "%~dp0..\..\.venv\Scripts\python.exe" "workspace .venv"
if defined SEO_PY goto :export

call :probe "%~dp0.venv\Scripts\python.exe" "repository .venv"
if defined SEO_PY goto :export

py -3.12 -c "import seo_analysis" >nul 2>&1
if not errorlevel 1 (
  set "SEO_PY=py -3.12"
  set "SEO_PY_LABEL=Windows Python launcher 3.12"
)
if defined SEO_PY goto :export

python -c "import seo_analysis" >nul 2>&1
if not errorlevel 1 (
  set "SEO_PY=python"
  set "SEO_PY_LABEL=python on PATH"
)

:export
endlocal & set "SEO_PY=%SEO_PY%" & set "SEO_PY_LABEL=%SEO_PY_LABEL%"
exit /b 0

:probe
rem %1 = interpreter path, %2 = label shown to the operator
if "%~1"=="" exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import seo_analysis" >nul 2>&1
if errorlevel 1 exit /b 0
set "SEO_PY="%~1""
set "SEO_PY_LABEL=%~2"
exit /b 0
