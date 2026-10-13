# Ruang GRIB: antarmuka browser lokal

Ruang GRIB memudahkan konversi melalui browser pada komputer Windows sendiri.
Anda bisa mengunggah berkas, mengunggah folder, atau memilih folder lokal,
memeriksa 20 baris pertama, memproses beberapa sumber, dan mengunduh CSV/Excel.
Script CLI yang lama tetap tersedia.

[Panduan lengkap PDF](panduan-pengguna.pdf) memuat ilustrasi memulai aplikasi,
memilih sumber, melihat cuplikan, serta mengunduh dan membaca grafik.

## Persiapan dan mulai

Gunakan Python 3.11. Dari folder proyek, siapkan environment jika belum ada,
lalu pasang dependensi web:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe -m pip check
```

Jika `.venv` sudah ada, gunakan kembali; tidak perlu membuat atau mengaktifkannya
ulang. Dependensi inti tetap berasal dari `requirements.txt` yang dikunci.

Klik dua kali `start-web.cmd`. Launcher masuk ke foldernya sendiri, memeriksa
environment/dependensi, lalu membuka antarmuka. Jika belum lengkap, jendela
menampilkan perintah pemasangan; tidak memasang paket diam-diam setiap kali.

Alamat bawaan: **http://127.0.0.1:8501**. Biarkan jendela terminal terbuka selama
memakai aplikasi; tekan **Ctrl+C** untuk menghentikannya. Jika port 8501 sudah
dipakai, lihat alamat aktual yang dicetak Streamlit pada terminal.

## Pilih sumber

| Pilihan | Cara pakai |
|---|---|
| Unggah berkas | Pilih satu atau beberapa file melalui pemilih berkas. |
| Unggah folder | Pilih folder melalui pemilih browser; berkas GRIB di subfolder ikut diunggah. |
| Folder lokal | Tempel alamat folder di komputer yang menjalankan aplikasi, klik Tampilkan berkas, lalu pilih file. Sertakan subfolder jika diperlukan. |

Ekstensi: `.grib`, `.grb`, `.grib2`, `.grb2`, termasuk huruf besar. Isi tetap
diperiksa decoder GRIB, sehingga mengganti akhiran file lain tidak membuatnya
menjadi GRIB. Batas unggahan bawaan **200 MB per berkas**; pilih **Folder lokal**
untuk sumber lebih besar. Folder lokal membaca dari komputer aplikasi, bukan
path milik server lain atau browser di perangkat lain.

Alamat Windows dari **Copy as path** boleh ditempel dengan tanda kutip. Sumber
dibaca tanpa perubahan dan tanpa membuat index `.idx` di sampingnya. Nama
unggahan tidak dipakai langsung sebagai path tulis. Hasil sementara memakai
folder milik aplikasi; file dengan nama sama dari folder berbeda tetap memiliki
hasil dan folder ZIP yang berbeda.

## Temukan dan pilih kelompok nyata

Klik **Periksa kelompok GRIB** setelah memilih sumber. ecCodes membaca header
setiap pesan; tabel berisi source/group ID, dataType, numberOfPoints, parameter,
jumlah pesan, dan `filter_by_keys`. filterKey berarti pasangan nama kunci/nilai,
bukan properti baru. Kombinasi yang tidak ada tidak ditampilkan.

**Semua kelompok dipilih secara default** pada **Kelompok yang dipilih**; pilih
subset bila perlu. Preview/proses langsung juga menemukan dan memakai semua.
Hapus semua pilihan untuk menonaktifkan tombol. Geometri, level, jenis step,
dan cakupan parameter yang tidak kompatibel dipisahkan; tiap pesan masuk tepat
satu kelompok. Pembacaan strict memakai salinan pesan asli, bukan filter luas.
`filter_by_keys` menjelaskan identitas header yang ditemukan.

Yearly/monthly ditentukan per kelompok; time skalar boleh menjadi satu waktu.
Dimensi unsupported dan duplikasi ambigu dilaporkan; kelompok lain diteruskan.
Discovery input terpotong ditandai tidak lengkap. ZIP mempunyai subfolder per
sumber/kelompok; nama output menyertakan dataType, numberOfPoints, dan group ID.

## Periksa, proses, lalu unduh

1. Pilih berkas pada **Berkas yang dipilih**, lalu periksa/pilih kelompoknya.
2. Klik **Lihat cuplikan**. Pilih hasil yang ingin diperiksa; tabel menampilkan
   20 baris pertama, jumlah baris/variabel/nilai kosong, serta koordinat terakhir.
3. Klik **Proses berkas terpilih** untuk menyiapkan hasil ekspor. Kelompok diproses
   satu per satu; bila ada kegagalan, kelompok lainnya tetap diteruskan. Detail
   masalah tersedia pada expander di bawah pesan ringkas.
4. Unduh **CSV**, **Excel**, atau **semua hasil (ZIP)** yang berhasil.

Cuplikan yang masih cocok dengan sumber/filter dapat digunakan kembali saat
memproses. Pilihan, filter, atau file lokal yang berubah membatalkan hasil lama.
Mengubah variabel grafik atau mengunduh tidak mendekode GRIB lagi. Hasil disimpan
dalam sesi; simpan unduhan sebelum menutup atau memuat ulang sesi browser.

**Filter lanjutan** opsional: isi `dataType` dan/atau `numberOfPoints` hanya bila
Anda mengetahui kunci yang tepat. Kosong berarti semua kelompok; isian
mempersempit discovery. Aplikasi
tidak menebak filter, menggabungkan kelompok pesan, atau mengubah susunan dimensi
yang tidak didukung. Jika gagal, sertakan pesan teknis saat meminta bantuan.

## Makna tabel dan rekomendasi grafik

Tabel memakai titik latitude/longitude terakhir, mempertahankan urutan dan
presisi converter, serta mengikuti semantik waktu notebook. Cuplikan memakai
notasi ilmiah agar angka sangat kecil terlihat; file unduhan tetap memakai
ekspor asli: CSV LF dan header Excel sesuai referensi yang diuji.

Aktifkan **Lihat grafik**, pilih satu variabel, lalu atur rentang baris bila perlu.

- **Yearly**: sumbu waktu memakai timestamp referensi asli, termasuk jamnya.
- **Monthly single**: pilih satu timestamp referensi; sumbu X memakai durasi
  `step` asli dalam jam. Misalnya 90 menit tampil sebagai 1,5 jam dan step 27
  jam tetap 27. Ini tidak mengubah kolom `hour` ekspor yang mengikuti notebook
  dengan jam bulat dan tanggal referensi.
- Grafik garis membantu melihat tren dan lonjakan. Garis terputus pada nilai
  kosong; timestamp/step duplikat atau tidak berurutan memakai grafik titik agar
  urutan tidak memberi kesan salah.
- Satuan ditampilkan dari metadata jika tersedia; zona waktu tidak diasumsikan.
  Tidak ada ambang kualitas udara atau interpretasi kesehatan yang ditebak.
- Semua titik pada rentang dipakai. Bila lebih dari 5.000 titik, persempit
  rentang; aplikasi tidak melakukan downsampling tersembunyi.

## Contoh meminta bantuan Codex

> Tolong jalankan Ruang GRIB di folder proyek ini. Gunakan .venv dan
> requirements-web.txt, baca AGENTS.md/README, lalu buka antarmuka lokal.
> Saya ingin memilih folder data, memeriksa cuplikan, mengunduh CSV/Excel,
> dan melihat grafik satu variabel. Pertahankan data asli dan jelaskan hasil
> pengujiannya. Ikuti model planning/implementasi pada AGENTS.md.

## Verifikasi pengelola

```powershell
.\.venv\Scripts\python.exe tests\test_web_workflow.py --sample "data\PM 10 DAN PM 2,5 MENTAH.grib"
.\.venv\Scripts\python.exe tests\test_notebook_parity.py --sample "data\PM 10 DAN PM 2,5 MENTAH.grib"
```

Pengujian mencakup AppTest unggahan/folder/proses/grafik/perubahan filter,
input tidak valid, partial errors, nama yang tidak aman, nama duplikat dalam ZIP,
perubahan file lokal, serta kesamaan download dengan CLI. Metadata/plot monthly
diuji sintetis dan melalui GRIB buatan ecCodes; sampel GRIB pengguna tetap
yearly. Jalankan juga `tests/test_grib_groups.py` dengan `--sample` dan path
sampel untuk partition, CLI default semua, subset, dan state antarmuka kelompok.
