@echo off
rem Command-line front door for the SEO Analysis tools.
rem Usage: seo.bat <command> [options]      e.g.  seo.bat audit https://example.org
setlocal EnableExtensions
title SEO Analysis CLI

call "%~dp0scripts\_find-python.bat"
if not defined SEO_PY goto :nopython

if "%~1"=="" goto :help
if /i "%~1"=="help" goto :help
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help

%SEO_PY% -m seo_analysis %*
exit /b %ERRORLEVEL%

:help
echo ============================================================
echo   SEO Analysis - common commands
echo ============================================================
echo.
echo   Audit a website (crawl + findings)
echo       seo.bat audit https://example.org
echo       seo.bat audit https://example.org --max-pages 100 --json
echo.
echo   Reference a sitemap or a URL list instead
echo       seo.bat audit --sitemap https://example.org/sitemap.xml
echo       seo.bat audit --urls-file seeds.csv --link-crawl
echo.
echo   Read results of a finished run
echo       seo.bat history list
echo       seo.bat check --run ^<run-id^>
echo       seo.bat compare --before ^<id^> --after ^<id^>
echo.
echo   Import exports and build reports
echo       seo.bat import-data rankings.csv --kind serp --provider "Account export" --observed 2026-11-21
echo       seo.bat workbook --crawl ^<run-id^> --dataset ^<dataset-id^>
echo.
echo   Local build checks
echo       seo.bat site-qa ./build
echo.
echo   Everything else
echo       seo.bat tools list
echo       seo.bat --help
echo.
echo   Start the browser workbench by double-clicking "SEO-Workbench.bat".
echo ============================================================
echo.
pause
exit /b 0

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
pause
exit /b 1
