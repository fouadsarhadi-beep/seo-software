@echo off
setlocal EnableExtensions DisableDelayedExpansion

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    set "SEO_WORKBENCH_SCRIPTS=%~dp0.venv\Scripts"
) else if exist "%~dp0..\.venv\Scripts\pythonw.exe" (
    set "SEO_WORKBENCH_SCRIPTS=%~dp0..\.venv\Scripts"
) else (
    echo Set up the Python virtual environment using the Windows instructions in README.md.
    echo This launcher looks for .venv in the project folder and its parent.
    pause
    exit /b 1
)

set "PYTHONPATH=%~dp0src"
"%SEO_WORKBENCH_SCRIPTS%\python.exe" -P -c "import tkinter, seo_analysis.desktop"
if errorlevel 1 (
    echo Check the Python setup and install the project in this environment.
    echo Environment: "%SEO_WORKBENCH_SCRIPTS%"
    echo See the Windows instructions in README.md.
    pause
    exit /b 1
)

start "" "%SEO_WORKBENCH_SCRIPTS%\pythonw.exe" -P -m seo_analysis.desktop %*
