@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "GRIB_STATUS=1"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto location_failed
if not exist ".venv\Scripts\python.exe" goto missing_packages
".venv\Scripts\python.exe" -c "import pathlib,sys,struct; sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 and sys.prefix!=sys.base_prefix and pathlib.Path(sys.prefix).resolve()==(pathlib.Path.cwd()/'.venv').resolve() else 1)" >nul 2>&1
if errorlevel 1 goto missing_packages
".venv\Scripts\python.exe" -c "import streamlit, altair, cfgrib, eccodes, numpy, pandas, xarray, openpyxl" >nul 2>&1
if errorlevel 1 goto missing_packages
echo Buka http://127.0.0.1:8501 untuk menggunakan Ruang GRIB.
echo Tutup aplikasi dengan Ctrl+C pada jendela ini.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.headless false --browser.gatherUsageStats false
set "GRIB_STATUS=%ERRORLEVEL%"
goto finish
:missing_packages
echo Environment atau paket belum lengkap. Klik dua kali install.cmd dahulu.
goto finish
:location_failed
echo Folder proyek tidak dapat dibuka. Ekstrak ZIP ke folder yang dapat diakses.
pause
endlocal & exit /b 1
:finish
pause
popd
endlocal & exit /b %GRIB_STATUS%
