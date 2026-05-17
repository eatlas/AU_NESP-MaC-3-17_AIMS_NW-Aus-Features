@echo off
setlocal enabledelayedexpansion

REM This utility is used to create symbolic links in the in-3p folder to a shared
REM directory that is outside of OneDrive. This shared directory contains a copy
REM of downloaded large third party datasets, that are reused across multiple versions.
REM
REM Workflow:
REM   1. Manually move (or copy) dataset folders from in-3p to C:\data-3p
REM   2. Delete the original folders from in-3p
REM   3. Run this script to create symbolic links from in-3p to C:\data-3p
REM
REM This script only creates links where nothing exists in in-3p yet.
REM It will NOT delete or move existing folders automatically.
REM This script must be run in an elevated command prompt (Run as Administrator) 
REM to create symbolic links.
REM
REM Usage:
REM   U01-setup-symbolic-links.bat [version]
REM   e.g. U01-setup-symbolic-links.bat v1-1
REM   If no version is specified, defaults to v1-0.

REM ============================================================
REM Configuration
REM ============================================================
set "DATA_PATH=C:\data-3p"
set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=v1-0"

REM Get the directory this script is in
set "SCRIPT_DIR=%~dp0"
set "IN_3P=%SCRIPT_DIR%data\%VERSION%\in-3p"

echo.
echo ============================================================
echo  Symbolic Link Setup for in-3p datasets
echo  Version: %VERSION%
echo  Shared data: %DATA_PATH%
echo  Target:      %IN_3P%
echo ============================================================
echo.

REM Check we have admin privileges (required for mklink /D)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click the script and select "Run as administrator".
    exit /b 1
)

REM Ensure the shared data directory exists
if not exist "%DATA_PATH%" (
    echo Creating shared data directory: %DATA_PATH%
    mkdir "%DATA_PATH%"
)

REM Ensure the in-3p directory exists
if not exist "%IN_3P%" (
    echo Creating in-3p directory: %IN_3P%
    mkdir "%IN_3P%"
)

REM ============================================================
REM Define datasets from 01a-download-input-data.py and 01b-download-sentinel2.py
REM Update this list if datasets are added or removed from those scripts.
REM ============================================================
set DATASETS=AU_AIMS_Coastline_50k_2024 AU_AIMS_Shallow-mask AU_DCCEEW_Australia-Marine-Parks_2025 AU_GA_AMB2020 AU_NESP-D3_AHS_Reefs AusBathyTopo-250m_2024 CAPAD-2024 TS-GBR-Feat GA_GeoTopo250k_S3 MultiRes-Bathy-EEZ_2024 natural-earth-admin-0-countries-50m natural-earth-land-50m S2 World_WCMC_CoralReefs2021_v4_1

REM ============================================================
REM Process each dataset
REM ============================================================
for %%D in (%DATASETS%) do (
    call :process_dataset "%%D"
)

REM ============================================================
REM Check for unexpected folders in in-3p that are not in the dataset list
REM ============================================================
echo.
echo ------------------------------------------------------------
echo Checking for unexpected folders in in-3p ...
for /D %%F in ("%IN_3P%\*") do (
    set "FOUND=0"
    for %%D in (%DATASETS%) do (
        if "%%~nxF"=="%%D" set "FOUND=1"
    )
    if "!FOUND!"=="0" (
        echo   WARNING: %%~nxF is not in the expected dataset list. Possibly deprecated.
    )
)

echo.
echo Done.
exit /b 0

REM ============================================================
REM Subroutine: process_dataset
REM   %~1 = dataset folder name
REM ============================================================
:process_dataset
set "DS=%~1"
set "LINK=%IN_3P%\%DS%"
set "SOURCE=%DATA_PATH%\%DS%"

if exist "%LINK%" (
    echo   [SKIP]  %DS% - already exists in in-3p
    goto :eof
)

if not exist "%SOURCE%" (
    echo   [MISS]  %DS% - not in %DATA_PATH%. Download with 01a then move to %DATA_PATH%.
    goto :eof
)

echo   [LINK]  %DS% - creating symlink ...
mklink /D "%LINK%" "%SOURCE%" >nul
if !errorlevel! neq 0 (
    echo           ERROR: Failed to create symlink for %DS%.
) else (
    echo           Done.
)
goto :eof
