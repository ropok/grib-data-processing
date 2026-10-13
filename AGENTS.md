# Aturan Model Agent

Aturan ini berlaku untuk seluruh repositori.

## Planning dan pengambilan keputusan

- Gunakan **GPT 6 Astra** (`gpt-6-astra`) dengan reasoning effort **medium**.
- Peran ini hanya untuk analisis, planning, dan pengambilan keputusan.
- Boleh membaca kode, data, dan dokumentasi untuk menyusun rencana, tetapi tidak boleh melakukan implementasi, mengubah kode/notebook, atau menjalankan perintah yang memodifikasi proyek.
- Hasil planning harus memuat tujuan, ruang lingkup, keputusan teknis beserta alasannya, langkah implementasi, dan kriteria verifikasi.

## Implementasi

- Gunakan **GPT 6.1 Sol** (`gpt-6.1-sol`) dengan reasoning effort **high**.
- Implementasi hanya boleh dimulai setelah rencana dari GPT 6 Astra tersedia.
- Kerjakan perubahan, pengujian, dan perbaikan sesuai rencana tersebut.
- Keputusan teknis yang mengubah ruang lingkup, arsitektur, atau pendekatan harus dikembalikan ke GPT 6 Astra untuk memperbarui planning sebelum implementasi dilanjutkan.

## Handoff antarperan

- Urutan kerja: GPT 6 Astra (medium) membuat planning dan keputusan, kemudian GPT 6.1 Sol (high) melakukan implementasi.
- Sertakan rencana dan keputusan teknis dalam konteks handoff agar implementer tidak perlu menebak.
- Jangan mengganti model atau effort secara diam-diam. Jika model yang diperlukan tidak tersedia, laporkan keterbatasan tersebut.
- Aturan ini adalah instruksi workflow; pemilihan model dan effort harus dilakukan melalui pengaturan sesi atau konfigurasi agent yang tersedia. File ini sendiri tidak mengganti model sesi secara otomatis.

## Cara memakai proyek melalui AI untuk pengguna nonteknis

Pengguna cukup menjelaskan tujuan dan lokasi file. AI harus mengerjakan langkah
teknis yang diperlukan, lalu menyampaikan lokasi hasil dan bukti pemeriksaan
dengan bahasa sederhana. Panduan perintah lengkap ada di `README.md`.

### Saat menerima permintaan

1. Baca instruksi ini dan `README.md`. Periksa kondisi Git dan file lokal tanpa
   menghapus atau menimpa pekerjaan pengguna. Gunakan path file yang disebut
   pengguna; jika tidak disebut, periksa file `.grib` dalam `data/`. Jika ada
   beberapa kandidat dan tujuan tidak jelas, minta pengguna memilih file.
2. Ikuti urutan model di atas: GPT 6 Astra (medium) menyiapkan tujuan, ruang
   lingkup, keputusan, langkah kerja, dan verifikasi; GPT 6.1 Sol (high)
   menjalankan rencana. Sampaikan model/effort yang dipakai dan keterbatasan jika
   konfigurasi itu tidak tersedia. Jangan menganggap tulisan ini otomatis
   mengganti model.
3. Gunakan Python 3.11 dan environment `.venv` dalam proyek. Jika belum ada,
   buat environment dan pasang `requirements.txt`. Jalankan perintah memakai
   `.venv/Scripts/python.exe`; pengguna tidak perlu mengaktifkan environment
   atau menyalin perintah satu per satu.

### Saat mengonversi data

- Jalankan `grib_to_csv.py` untuk satu file yang dipilih. Secara default hasil
  CSV dan Excel ada di folder `output_<nama_file>` di samping input. Gunakan
  `--output-dir` jika pengguna menentukan folder hasil. File keluaran dengan
  nama sama akan ditulis ulang; simpan hasil lama jika pengguna meminta
  perbandingan atau pelestarian versi.
- Jika pembacaan GRIB memerlukan filter, periksa kunci pesan GRIB dan gunakan
  `--data-type`/`--number-of-points` yang sesuai. Jangan menebak filter atau
  menggabungkan kelompok data berbeda secara diam-diam. Untuk perubahan
  pendekatan, kembalikan keputusan ke GPT 6 Astra sebelum implementasi.
- Jelaskan bahwa hasil mengambil titik latitude/longitude terakhir. Jalur
  yearly menggunakan jam `time`; jalur monthly menggunakan tanggal referensi
  dan jam durasi `step`, yang bisa lebih dari 23. Jangan mengubahnya menjadi
  rata-rata, konversi satuan, pembulatan, atau `valid_time` tanpa permintaan dan
  rencana baru.
- Periksa bahwa CSV dan XLSX tersedia serta laporkan jumlah baris, variabel,
  dan lokasi file. Untuk membuktikan kesamaan dengan notebook, jalankan
  `tests/test_notebook_parity.py --sample "<path GRIB yearly>"`; bandingkan
  DataFrame persis, byte CSV setelah hanya menormalisasi CRLF notebook menjadi
  LF, serta isi worksheet XLSX persis. CSV script harus selalu memakai LF dan
  header Excel mengikuti konstanta style referensi lengkap: font tebal tanpa
  nama/ukuran eksplisit, alignment tengah/atas, border tipis empat sisi, fill
  kosong, format General, protection terkunci/tidak tersembunyi. Nyatakan bahwa
  jalur monthly diuji sintetis bila belum ada sampel monthly asli.
- Jika pengguna memberi file hasil referensi, periksa juga byte CSV asli tanpa
  normalisasi, nilai/jenis setiap sel Excel, serta semua properti style header.
  Laporkan tingkat kesamaan yang benar; jangan menyebut XLSX identik byte jika
  yang dibandingkan hanya isi dan format sel. Pertahankan file referensi asli.

### Saat pengguna meminta perubahan kode

- Setelah rencana tersedia, gunakan branch fitur `codex/<nama-fitur>` dari
  `development` sesuai permintaan pengguna. Bila `development` lokal belum ada,
  buat dari `origin/development` setelah memastikan referensi itu tersedia.
  Lindungi perubahan lokal sebelum berpindah branch; jangan reset atau hapus
  file pengguna. Jika sudah ada branch kerja yang diminta pengguna, lanjutkan
  branch tersebut.
- Pertahankan notebook asli sebagai pembanding. Setelah perubahan converter,
  jalankan pengujian parity pada sampel yang tersedia dan pemeriksaan dependensi
  `pip check`. Laporkan kegagalan dan perbaiki dalam ruang lingkup rencana.
- Perbarui dokumentasi setelah kode selesai. Jangan commit, push, atau membuat
  PR kecuali diminta. Akhiri dengan hasil, lokasi file, bukti verifikasi, dan
  keterbatasan nyata; jangan berhenti hanya dengan memberi daftar perintah.

### Saat menggunakan antarmuka browser lokal

- Gunakan `requirements-web.txt` dalam `.venv` yang sama; jangan mengganti versi
  inti converter. Jalankan `start-web.cmd` atau Streamlit pada `127.0.0.1`.
  Panduan antarmuka ada di `docs/browser-interface.md`; tidak perlu deployment
  web atau API key untuk memakai aplikasi ini.
- Arahkan pengguna memilih Unggah berkas, Unggah folder, atau Folder lokal.
  Folder lokal adalah alamat di komputer aplikasi. Preview/proses harus dipicu
  tombol pengguna, dan perubahan input/filter harus membatalkan hasil lama.
- Pertahankan sumber; keluaran web hanya pada penyimpanan sementara aplikasi
  dan unduhan sesi. Untuk batch, teruskan berkas lainnya saat satu file gagal
  dan laporkan status per berkas. Jangan menebak filter GRIB.
- Grafik memakai waktu/step asli, satu variabel, dan satu referensi untuk monthly.
  Jaga gap nilai kosong, pakai titik untuk waktu duplikat/tidak berurutan, serta
  jangan menebak satuan, zona waktu, atau ambang interpretasi. Grafik tidak
  mengubah data ekspor. Rentang besar harus dipersempit, bukan didownsample diam-diam.
- Setelah perubahan antarmuka, jalankan `tests/test_web_workflow.py` dan parity
  notebook dengan sampel lokal, serta `pip check`. Beri bukti verifikasi dan
  alamat browser lokal; jangan commit/push/PR/merge tanpa permintaan baru.

### Contoh prompt yang bisa langsung dipakai

> Tolong ubah file "data/PM 10 DAN PM 2,5 MENTAH.grib" menjadi CSV dan Excel.
> Siapkan environment jika diperlukan, jalankan prosesnya, dan tunjukkan lokasi
> hasil serta jumlah barisnya. Ikuti aturan model di AGENTS.md.

> Tolong konversi file "data/nama-file.grib" dan simpan hasil di "data/hasil".
> Jika perlu filter GRIB, periksa filter yang cocok. Jelaskan titik lokasi dan
> arti kolom waktunya dengan bahasa sederhana.

> Tolong buktikan hasil script Python sama dengan notebook asli pada file
> sampel dalam data. Jalankan pengujiannya dan jelaskan apa yang dibandingkan,
> mana yang memakai data asli, serta lokasi laporan pengujiannya.

> Tolong tambahkan kemampuan [jelaskan kebutuhan]. Buat rencana dahulu dengan
> GPT 6 Astra medium, lalu implementasikan dengan GPT 6.1 Sol high pada branch
> codex/[nama-fitur]. Pertahankan file lokal saya, jalankan pengujian yang relevan,
> dan perbarui panduan setelah kode selesai. Jangan commit atau push dahulu.

> Tolong jalankan antarmuka Ruang GRIB di browser lokal. Saya ingin memilih
> folder data, melihat cuplikan tabel, mengunduh CSV/Excel, dan menampilkan grafik
> satu variabel. Gunakan .venv dan requirements-web.txt, pertahankan sumber,
> ikuti aturan model di atas, dan tunjukkan alamat aplikasi serta hasil verifikasi.
