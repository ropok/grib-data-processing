# Panduan pengguna

`panduan-pengguna.pdf` adalah panduan visual berbahasa Indonesia untuk pengguna
Windows nonprogrammer, mulai dari unduhan Python/proyek hingga CLI, Ruang GRIB
di browser lokal, dan bantuan AI. Sumber mandirinya adalah `panduan-pengguna.tex`; seluruh diagram
dibuat dengan TeX/TikZ, tanpa file gambar tambahan.

Jalur pemula menggunakan klik dua kali `install.cmd` lalu `start-web.cmd`;
PowerShell/CLI adalah pilihan tambahan. Python 3.11 64-bit dipasang manual
melalui installer resmi. PDF tetap 16 halaman dan diperbarui pada file yang sama.

Pengguna converter cukup membaca PDF. LaTeX hanya diperlukan oleh pengelola
yang ingin membangun ulang atau mengubah panduan.

## Membangun ulang

Buka `panduan-pengguna.tex` di editor LaTeX untuk melihat sumber dan preview.
PDF distribusi dibangun dari sumber tersebut menggunakan Tectonic 0.17.0
portable dari [rilis resminya](https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.17.0).
Gunakan compiler yang tersedia, tanpa perlu mengonfigurasi ulang MiKTeX pengguna.

Contoh PowerShell, dari root proyek, setelah Tectonic diunduh terpisah:

```powershell
# Ganti path ini dengan lokasi executable Tectonic Anda.
$tectonic = "C:\alat\tectonic.exe"
New-Item -ItemType Directory -Path data\docs-build\pdf -Force | Out-Null
& $tectonic --keep-logs --outdir data\docs-build\pdf docs\panduan-pengguna.tex
Copy-Item data\docs-build\pdf\panduan-pengguna.pdf docs\panduan-pengguna.pdf
```

Build pertama memerlukan internet untuk mengunduh paket TeX. Sumber dan PDF
akhir disimpan dalam `docs`; log, runtime portable, serta render PNG verifikasi
lokal berada dalam `data/docs-build` yang diabaikan Git.

Setelah perubahan, pastikan PDF berisi 16 halaman A4, render dan periksa semua
halaman, lalu cocokkan perintah, label tombol, tautan dan nomor referensi halaman
hasil ekstraksi teks dengan sumber. Footer memakai referensi halaman terakhir;
build harus selesai melakukan rerun agar semua referensi terisi. Jangan
menghasilkan PDF kedua secara terpisah menggunakan sistem layout lain.
