# grib-data-processing

Konversi GRIB menjadi CSV dan Excel melalui browser lokal atau `grib_to_csv.py`. Script
mempertahankan hasil pengolahan satu file pada `GribToCsv.ipynb`; notebook asli
tetap tersedia sebagai referensi.

**[Panduan lengkap PDF](docs/panduan-pengguna.pdf)** menjelaskan langkah visual
dari nol, termasuk CLI, Ruang GRIB, dan bantuan AI. [Petunjuk antarmuka browser](docs/browser-interface.md)
serta [sumber LaTeX/petunjuk rebuild](docs/README.md) juga tersedia.

## Quickstart: jalankan Ruang GRIB

1. Pasang **Python 3.11** ([installer Windows 64-bit 3.11.9](https://www.python.org/downloads/release/python-3119/)).
2. Unduh [ZIP branch development](https://github.com/ropok/grib-data-processing/archive/refs/heads/development.zip)
   dan ekstrak. Gunakan **development**, bukan main, untuk fitur browser ini.
   Buka folder yang langsung berisi `app.py`, `requirements-web.txt`, dan
   `start-web.cmd`. File GRIB diperoleh terpisah; letakkan dalam `data` jika ingin.
3. Buka PowerShell dari folder proyek. **Buat `.venv` hanya jika belum ada**:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.11 -m venv .venv }
```

Pasang paket web (sudah menyertakan paket inti) dan periksa pemasangannya:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe -m pip check
```

4. Klik dua kali `start-web.cmd`, atau jalankan dari PowerShell:

```powershell
.\start-web.cmd
```

5. Buka **http://127.0.0.1:8501** jika browser belum terbuka. Biarkan terminal
   tetap terbuka. Pilih berkas/folder → **Periksa kelompok GRIB** (default semua)
   → **Lihat cuplikan** → **Proses berkas terpilih**
   → unduh **CSV/Excel/ZIP**. Simpan unduhan sebelum menutup sesi; tekan Ctrl+C
   di terminal untuk menghentikan aplikasi.

Opsional, konversi satu file lewat CLI:

```powershell
.\.venv\Scripts\python.exe grib_to_csv.py "data\PM 10 DAN PM 2,5 MENTAH.grib"
```

## Antarmuka browser lokal

Ruang GRIB berjalan pada komputer sendiri, memakai converter dan dependensi
inti yang sama. Tiga sumber tersedia: **Unggah berkas**, **Unggah folder**,
dan **Folder lokal**. Batas unggahan 200 MB per berkas; pilih folder lokal untuk
file lebih besar. Panduan rinci: [antarmuka browser](docs/browser-interface.md).

Pilih sumber dan berkas, lalu klik **Lihat cuplikan** atau **Proses berkas terpilih**.
Hasil CSV/Excel tersedia per berkas dan dalam ZIP. Pembacaan tidak berjalan
otomatis saat Anda memilih data; kegagalan satu berkas tidak menghentikan berkas
lain. Sumber tidak ditimpa, dan hasil web tidak ditulis ke folder input.

Discovery membaca header ecCodes dan hanya menampilkan kombinasi nyata.
**Kelompok yang dipilih** berisi semua pada awalnya; pilih subset bila perlu.
dataType, numberOfPoints, geometri/level/step dan cakupan parameter menentukan
partisi; tiap pesan masuk tepat satu kelompok. `filter_by_keys` adalah identitas
header, sedangkan pembacaan strict memakai salinan pesan asli kelompok.
Yearly/monthly ditentukan per kelompok. Dimensi unsupported, pesan duplikat
ambigu, dan discovery tidak lengkap dilaporkan; kelompok lain tetap diproses.

Grafik bersifat opsional: yearly memakai waktu referensi asli; monthly memilih
satu waktu referensi dan memakai durasi step asli, termasuk pecahan jam dan
durasi di atas 24 jam. Garis terputus pada nilai kosong; waktu berulang atau
tidak berurutan memakai grafik titik. Grafik tidak mengubah tabel unduhan.

Verifikasi antarmuka dan backend:

```powershell
.\.venv\Scripts\python.exe tests\test_web_workflow.py --sample "data\PM 10 DAN PM 2,5 MENTAH.grib"
.\.venv\Scripts\python.exe tests\test_grib_groups.py --sample "data\PM 10 DAN PM 2,5 MENTAH.grib"
```

## Persiapan di Windows (PowerShell)

Gunakan Python 3.11. Jalankan dari folder proyek:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Jika launcher `py` tidak tersedia, gunakan path Python 3.11 yang terpasang:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv .venv
```

Tidak perlu mengaktifkan virtual environment. Semua perintah berikut langsung
memakai Python di `.venv`. Dependensi utama dikunci pada versi yang telah diuji;
wheel `eccodes` yang diuji di Windows sudah menyediakan library GRIB sehingga
perintah Linux `apt-get` dari notebook tidak diperlukan.

## Menjalankan konversi

Contoh file lokal dalam `data` (data mentah tidak disertakan dalam Git):

```powershell
.\.venv\Scripts\python.exe grib_to_csv.py "data\PM 10 DAN PM 2,5 MENTAH.grib"
```

Hasil default berada di samping file input, dalam folder `output_<nama_file>`:

```text
data/output_PM 10 DAN PM 2,5 MENTAH/
  ...__dataType-an__numberOfPoints-1639__group-ID.csv
  ...__dataType-an__numberOfPoints-1639__group-ID.xlsx
```

File hasil dengan nama yang sama akan ditulis ulang. Untuk memilih folder lain:

```powershell
.\.venv\Scripts\python.exe grib_to_csv.py "data\PM 10 DAN PM 2,5 MENTAH.grib" --output-dir "data\hasil"
```

CLI secara default memproses **semua kelompok nyata**. Periksa ID/kunci dengan
`--list-groups`; pilih subset lewat `--group ID` (boleh diulang). `--all-groups`
adalah alias eksplisit default. `dataType`/`numberOfPoints` mempersempit discovery:

```powershell
.\.venv\Scripts\python.exe grib_to_csv.py "data\PM 10 DAN PM 2,5 MENTAH.grib" --data-type an --number-of-points 1639
```

Contoh ini cocok dengan file sampel. File lain mungkin memakai `fc`, `em`, atau
`es`, dan jumlah titik berbeda. Nama hasil menyertakan filter, misalnya
`nama__dataType-an__numberOfPoints-1639__group-ID.csv`; pembeda level/step
ditambahkan bila perlu. Folder default tetap memakai nama input. CLI menyimpan
kelompok berhasil dan exit nonzero bila ada kegagalan/discovery tidak lengkap.
`--legacy-single` memilih perilaku/nama CLI lama. API `read_grib`/`convert_grib`
beserta signature/tuple tetap kompatibel. Lihat opsi lengkap dengan `--help`.

## Makna hasil dan batasan

- Kolom: `year`, `month`, `day`, `hour`, lalu variabel GRIB sesuai urutan notebook.
- Script mengambil **titik latitude terakhir dan longitude terakhir** untuk
  setiap waktu; tidak melakukan rata-rata spasial. Sampel menggunakan
  latitude −7.5 dan longitude 111.0.
- Variabel berdimensi `(time, latitude, longitude)` mengikuti jalur yearly:
  tanggal dan jam berasal dari waktu referensi `time`.
- Variabel berdimensi `(time, step, latitude, longitude)` mengikuti jalur monthly
  single: tanggal berasal dari `time`, sedangkan `hour` adalah durasi `step`
  dalam jam bulat. Nilai ini bisa lebih dari 23; bukan jam `valid_time`.
  Pecahan jam dipotong mengikuti notebook.
- Urutan baris, nilai kosong, presisi, satuan, dan pembentukan dtype mengikuti
  notebook. CSV/Excel tidak menyertakan indeks DataFrame.
- CSV selalu memakai akhir baris LF (`\n`), termasuk di Windows, sesuai file
  referensi. Header Excel mengikuti referensi: tebal tanpa nama/ukuran font
  eksplisit, rata tengah horizontal dan atas vertikal, garis tipis di empat
  sisi, fill kosong, format `General`, serta proteksi sel terkunci/tidak tersembunyi.
- API legacy menuntut salah satu susunan dimensi di atas untuk semua variabel. Dimensi
  skalar, tambahan seperti `number`/`level`, atau susunan campuran ditolak dengan
  pesan yang menjelaskan dimensi ditemukan.
- Mode kelompok mempromosikan `time` skalar menjadi satu waktu; API legacy
  tetap strict. `step` skalar memakai yearly; ensemble/member berdimensi dan
  grid unsupported tidak ditransformasikan diam-diam.
- Sel eksperimen notebook tidak dijalankan otomatis oleh script ini.
  Index sidecar `.idx` tidak dibuat; dataset ditutup setelah dibaca.

## Verifikasi kesamaan dengan notebook

```powershell
.\.venv\Scripts\python.exe tests\test_notebook_parity.py --sample "data\PM 10 DAN PM 2,5 MENTAH.grib"
```

Pengujian membaca sumber dari notebook asli, menjalankan sel helper/import,
pemrosesan yearly atau monthly single, dan ekspor. Adaptasi hanya mencakup path
lokal, filter input, dan menonaktifkan index sidecar. Sel Colab, instalasi,
pemrosesan kelompok, serta eksperimen tidak dijalankan.

Yang dibandingkan: DataFrame dengan nilai/dtype/indeks/urutan kolom dan baris
secara persis, byte CSV setelah hanya menormalisasi CRLF keluaran notebook
menjadi LF, serta nama worksheet/dimensi/nilai dan jenis sel XLSX secara persis.
Sumber notebook tidak diubah. Pengujian juga memastikan CSV script hanya memakai
LF dan seluruh properti header Excel sesuai konstanta referensi, tanpa memerlukan
file dalam Downloads. Byte arsip XLSX tidak dibandingkan karena metadata waktu
ekspor dapat berbeda.

Hasil verifikasi pada sampel: 3.168 baris, variabel `pm2p5` dan `pm10` float32,
dimensi waktu 3.168 × latitude 11 × longitude 149. Jalur yearly diuji dengan
GRIB asli, CLI, serta filter. Jalur monthly diuji memakai dataset sintetis karena
sampel lokal hanya memiliki dimensi yearly; dataset sintetis juga menguji NaN,
promosi dtype, pergantian tahun, dan `step` di atas 24 jam.

Artefak notebook/script/CLI dan laporan JSON berada di `data/parity/`.
Perbandingan terpisah dengan file referensi pengguna di Downloads membuktikan
CSV sampel identik byte demi byte, seluruh 19.014 nilai/jenis sel Excel sama,
dan keenam header memiliki font, alignment, border, fill, number format, serta
protection yang sama. Bukti lokalnya ada di `data/parity/reference_report.json`.
Tanpa `--sample`, pengujian sintetis tetap berjalan dan dua pengujian GRIB asli
dilewati. Jangan menganggapnya bukti untuk file GRIB asli.
