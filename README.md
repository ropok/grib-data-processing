# grib-data-processing

Konversi satu file GRIB menjadi CSV dan Excel dengan `grib_to_csv.py`. Script
mempertahankan hasil pengolahan satu file pada `GribToCsv.ipynb`; notebook asli
tetap tersedia sebagai referensi.

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
  PM 10 DAN PM 2,5 MENTAH.csv
  PM 10 DAN PM 2,5 MENTAH.xlsx
```

File hasil dengan nama yang sama akan ditulis ulang. Untuk memilih folder lain:

```powershell
.\.venv\Scripts\python.exe grib_to_csv.py "data\PM 10 DAN PM 2,5 MENTAH.grib" --output-dir "data\hasil"
```

GRIB yang berisi beberapa kelompok pesan dapat memerlukan filter sesuai kunci
GRIB-nya. `dataType` dan `numberOfPoints` bisa diberikan sendiri atau bersama:

```powershell
.\.venv\Scripts\python.exe grib_to_csv.py "data\PM 10 DAN PM 2,5 MENTAH.grib" --data-type an --number-of-points 1639
```

Contoh ini cocok dengan file sampel. File lain mungkin memakai `fc`, `em`, atau
`es`, dan jumlah titik berbeda. Nama hasil menyertakan filter, misalnya
`PM 10 DAN PM 2,5 MENTAH_an_1639.csv`. Folder default tetap memakai nama file
input tanpa suffix filter. Lihat seluruh opsi dengan `--help`.

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
- Semua variabel harus memiliki salah satu susunan dimensi di atas. Dimensi
  skalar, tambahan seperti `number`/`level`, atau susunan campuran ditolak dengan
  pesan yang menjelaskan dimensi ditemukan.
- Konversi kelompok file dan sel eksperimen notebook tidak termasuk script ini.
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
