@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Environment proyek belum tersedia.
  echo Jalankan dari folder ini:
  echo   py -3.11 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements-web.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import streamlit, altair, cfgrib, eccodes, pandas, xarray, openpyxl" >nul 2>&1
if errorlevel 1 (
  echo Paket antarmuka belum lengkap. Jalankan:
  echo   .venv\Scripts\python.exe -m pip install -r requirements-web.txt
  pause
  exit /b 1
)
echo Buka http://127.0.0.1:8501 untuk menggunakan Ruang GRIB.
echo Tutup aplikasi dengan Ctrl+C pada jendela ini.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.headless false --browser.gatherUsageStats false
pause
