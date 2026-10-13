@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "GRIB_STATUS=1"
set "GRIB_PAUSE=1"
set "GRIB_PUSHED=0"
set "GRIB_LOG="
set "GRIB_STAGE=arguments"
set "GRIB_RESULT=failure"
if "%~1"=="" goto location
if /i not "%~1"=="--no-pause" goto invalid_arguments
set "GRIB_PAUSE=0"
if not "%~2"=="" goto invalid_arguments

:location
set "GRIB_STAGE=project"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto location_failed
set "GRIB_PUSHED=1"
if not exist "requirements-web.txt" goto project_failed
if not exist "app.py" goto project_failed
if exist "data\install-logs\." goto open_log
mkdir "data\install-logs" >nul 2>&1

:open_log
>>"data\install-logs\install.log" echo [%DATE% %TIME%] stage=start status=running exit_code=0
if errorlevel 1 goto log_unavailable
set "GRIB_LOG=data\install-logs\install.log"
goto environment

:log_unavailable
echo Catatan tahap tidak dapat disimpan. Instalasi tetap dilanjutkan.

:environment
echo Persiapan Ruang GRIB. Python 3.11 64-bit diperlukan.
set "GRIB_STAGE=environment"
if exist ".venv" goto verify_environment
set "GRIB_STAGE=python_detection"
py -3.11 -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto create_launcher
"%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto create_local_python
python -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto create_path_python
goto python_missing

:create_launcher
set "GRIB_STAGE=create_environment"
echo Membuat .venv dengan Python launcher...
py -3.11 -m venv ".venv"
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto create_failed
goto verify_environment

:create_local_python
set "GRIB_STAGE=create_environment"
echo Membuat .venv dengan Python 3.11 lokal...
"%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -m venv ".venv"
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto create_failed
goto verify_environment

:create_path_python
set "GRIB_STAGE=create_environment"
echo Membuat .venv dengan Python 3.11 pada PATH...
python -m venv ".venv"
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto create_failed

:verify_environment
set "GRIB_STAGE=environment"
if not exist ".venv\Scripts\python.exe" goto environment_failed
".venv\Scripts\python.exe" -c "import pathlib,sys,struct; print('Python '+sys.version.split()[0]+' / '+str(struct.calcsize('P')*8)+'-bit'); sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 and sys.prefix!=sys.base_prefix and pathlib.Path(sys.prefix).resolve()==(pathlib.Path.cwd()/'.venv').resolve() else 1)"
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto environment_failed

:install_packages
set "GRIB_STAGE=packages"
echo Memasang paket yang dikunci dalam requirements-web.txt...
".venv\Scripts\python.exe" -m pip install -r "requirements-web.txt"
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto packages_failed
set "GRIB_STAGE=pip_check"
".venv\Scripts\python.exe" -m pip check
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto check_failed
set "GRIB_STAGE=native_imports"
".venv\Scripts\python.exe" -c "import streamlit,altair,cfgrib,eccodes,numpy,pandas,xarray,openpyxl; print('ecCodes native: '+str(eccodes.codes_get_api_version()))"
set "GRIB_STATUS=%ERRORLEVEL%"
if not "%GRIB_STATUS%"=="0" goto imports_failed
set "GRIB_RESULT=success"
set "GRIB_STAGE=complete"
echo.
echo Instalasi selesai. Klik dua kali start-web.cmd untuk membuka aplikasi.
goto finish

:invalid_arguments
set "GRIB_STATUS=2"
echo Argumen tidak dikenal. Gunakan install.cmd atau install.cmd --no-pause.
goto finish

:location_failed
echo Folder proyek tidak dapat dibuka. Ekstrak ZIP ke folder yang dapat diakses.
goto finish

:project_failed
echo File proyek belum lengkap: app.py dan requirements-web.txt harus tersedia.
echo Ekstrak ZIP development penuh, lalu jalankan install.cmd dari folder itu.
goto finish

:python_missing
set "GRIB_STATUS=1"
echo Python 3.11 64-bit yang dapat dijalankan belum ditemukan.
echo Buka https://www.python.org/downloads/release/python-3119/
echo Pilih Windows installer 64-bit biasa, bukan embeddable package.
echo Centang Add python.exe to PATH dan biarkan Python launcher dipasang.
echo Setelah pemasangan selesai, jalankan install.cmd lagi.
goto finish

:environment_failed
if "%GRIB_STATUS%"=="0" set "GRIB_STATUS=1"
echo .venv yang ada belum lengkap atau bukan virtualenv proyek dengan Python 3.11 64-bit.
echo Folder lama tetap dipertahankan. Minta pendamping memeriksanya sebelum melanjutkan.
goto finish

:create_failed
echo Pembuatan .venv gagal. Periksa izin folder dan pesan di atas.
echo Jika .venv menjadi parsial, installer tidak menghapus atau menggantinya.
goto finish

:packages_failed
echo Pemasangan paket gagal. Periksa koneksi, proxy, atau izin sesuai pesan di atas.
echo Setelah penyebabnya diperbaiki, jalankan install.cmd lagi.
goto finish

:check_failed
echo Pemeriksaan dependensi gagal. Simpan pesan di atas dan minta bantuan pendamping.
goto finish

:imports_failed
echo Pemeriksaan paket atau library ecCodes gagal. Simpan pesan di atas dan minta bantuan.

:finish
if defined GRIB_LOG >>"%GRIB_LOG%" echo [%DATE% %TIME%] stage=%GRIB_STAGE% status=%GRIB_RESULT% exit_code=%GRIB_STATUS%
if defined GRIB_LOG echo Catatan tahap: data\install-logs\install.log
if "%GRIB_PAUSE%"=="1" pause
if "%GRIB_PUSHED%"=="1" popd
endlocal & exit /b %GRIB_STATUS%
