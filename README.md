## 📃 `README.md`

# 🤖 AI Agent Ultimate

Agen AI terminal dengan dukungan **multi‑provider** (OpenAI, OpenRouter, Custom), integrasi **GitHub** via `gh` CLI, **auto‑update**, **auto‑run** proyek di background (Tmux), serta **auto‑fix error & debugging**. Cocok untuk **Ubuntu**, **Termux**, dan lingkungan Linux lainnya.

![AI Agent Ultimate](https://img.shields.io/badge/version-1.0.0-blue) ![Python](https://img.shields.io/badge/python-3.8%2B-green) ![License](https://img.shields.io/badge/license-MIT-brightgreen)

---

## 🌟 Fitur Utama

- 🔌 **Multi‑API** – Pilih OpenAI, OpenRouter (akses model Google, Meta, dll.), atau endpoint custom Anda sendiri.
- 🧙 **Setup Wizard** – Konfigurasi interaktif saat pertama dijalankan (API key, model, GitHub, direktori kerja).
- 📁 **Manajemen File** – Baca, tulis, dan edit file langsung dari percakapan.
- 🐧 **Shell Command** – Jalankan perintah shell (`git`, `npm`, `pip`, dll.) dengan aman.
- 🐙 **GitHub Terintegrasi** – Buat repo, push perubahan, clone repo; semua lewat `gh` CLI.
- ⏹️ **Fitur Cancel** – `Ctrl+C` untuk membatalkan AI yang sedang berpikir atau tool yang berjalan.
- 🔄 **Auto‑Retry Koneksi** – Jika koneksi terputus (terutama di Termux), agen otomatis mencoba ulang.
- 🧹 **Clear Screen** – Tampilan selalu bersih setiap kali agen dijalankan.
- 🔃 **Auto Update** – Saat dijalankan, agen mengecek perubahan di repositori GitHub utama. Jika ada versi baru, otomatis mengunduh dan me‑restart dirinya sendiri.
- 🚀 **Auto Run** – Jalankan proyek Anda di session Tmux terpisah, log disimpan rapi. Proyek sebelumnya otomatis dihentikan saat proyek baru dijalankan.
- 🐛 **Auto Fix Error & Debugging** – Monitor log proyek yang berjalan. Begitu terdeteksi *traceback* atau *error*, langsung kirim ke AI, perbaiki kode, dan *restart* proyek – semua otomatis tanpa campur tangan Anda.
- 💾 **Ringan** – Hanya butuh `requests`, `rich`, `gitpython`, `python-dotenv`; tanpa kompilasi Rust atau library berat.

---

## 📋 Persyaratan

- **Python** 3.8 atau lebih baru
- **Git** – untuk operasi version control
- **GitHub CLI** (`gh`) – untuk integrasi GitHub; login dengan `gh auth login`
- **Tmux** – untuk fitur auto‑run dan monitoring proyek
- **Termux** (opsional) – jika menggunakan Android, pastikan paket-paket di bawah terpasang.

---

## 🖥️ Instalasi & Setup

### Di Ubuntu / Debian

```bash
# 1. Install dependensi sistem
sudo apt update
sudo apt install python3 python3-pip git gh tmux -y

# 2. Clone repositori atau simpan script
git clone https://github.com/Vicienna/ai-agent.git
cd ai-agent

# 3. Install dependensi Python
pip install requests rich python-dotenv gitpython

# 4. Login GitHub (jika belum)
gh auth login

# 5. Jalankan agen
python agent_ultimate.py
```

### Di Termux (Android)

```bash
# 1. Update & install paket
pkg update && pkg upgrade
pkg install python git gh tmux -y

# 2. Install dependensi Python
pip install requests rich python-dotenv gitpython

# 3. Clone repositori (atau download script)
git clone https://github.com/Vicienna/ai-agent.git
cd ai-agent

# 4. Login GitHub
gh auth login

# 5. Jalankan
python agent_ultimate.py
```

---

## ⚙️ Konfigurasi

Saat pertama kali dijalankan, **Setup Wizard** akan muncul dan memandu Anda mengisi:

1. **Penyedia API** – Pilih antara OpenAI, OpenRouter, atau Custom.
2. **API Key** – Dapatkan dari link yang disediakan, masukkan dengan aman (tampilan bintang `*`).
3. **Model AI** – Daftar model populer langsung tersedia, termasuk `poolside/laguna-m.1:free` (gratis).
4. **GitHub** – Pastikan `gh` sudah login.
5. **Direktori Kerja** – Bisa diatur sesuai keinginan (default: direktori saat ini).

Semua pengaturan disimpan di file `.env` (jangan di‑commit). Untuk mengulang setup, cukup hapus file `.env` lalu jalankan ulang agen.

---

## 📖 Penggunaan

Setelah agen berjalan, cukup ketik perintah dalam bahasa Indonesia:

```
▸ Buatkan REST API Express untuk bot Discord, lengkap dengan endpoint /ping dan /servers, push ke repo discord-api.
```

Agen akan:
1. Membuat folder `discord-api`
2. `npm init -y && npm install express`
3. Menulis `index.js` dan file lainnya
4. Membuat repo GitHub `discord-api`
5. Push semua perubahan

Untuk **menjalankan proyek**:

```
▸ Jalankan proyek discord-api dengan npm start
```

Agen akan menggunakan `auto_run` → membuat session Tmux, menjalankan perintah, dan menyimpan log di `logs/`. Jika proyek sebelumnya berjalan, ia akan dihentikan lebih dulu.

Untuk **memantau dan memperbaiki error otomatis**:

Saat proyek berjalan, agen secara otomatis memonitor file log. Begitu ada *traceback* atau *error*, agen akan langsung menganalisis, mengedit file yang bermasalah, dan me‑restart proyek – semuanya tanpa Anda harus mengetik lagi.

### Perintah Khusus

| Perintah | Keterangan |
|----------|------------|
| `exit` / `quit` / `keluar` | Keluar dari agen |
| `Ctrl+C` saat AI berpikir | Batalkan permintaan terakhir |
| `Ctrl+C` saat tool berjalan | Batalkan tool (agen melanjutkan ke langkah berikutnya) |

---

## 🚀 Fitur Auto Update

Setiap kali agen dijalankan, ia membandingkan hash MD5 file `agent_ultimate.py` lokal dengan yang tersedia di:

```
https://raw.githubusercontent.com/Vicienna/ai-agent/main/agent_ultimate.py
```

Jika berbeda, agen akan mengunduh versi terbaru dan secara otomatis me‑restart dirinya. Pastikan direktori tempat script berada memiliki hak tulis.

---

## 🧪 Fitur Auto Run & Monitor

Agen menggunakan **Tmux** untuk menjalankan proyek di *background*:

- Session Tmux dibuat dengan nama proyek yang Anda berikan.
- Semua output (stdout & stderr) di‑pipe ke `logs/<nama_proyek>.log`.
- Thread monitor membaca log secara berkala; jika menemukan indikasi error, segera memasukkan ke antrian perbaikan.
- AI akan menerima laporan error, mencari penyebabnya, mengedit file, lalu me‑restart proyek.

Untuk melihat log secara langsung, Anda bisa masuk ke session Tmux:

```bash
tmux attach -t <nama_proyek>
```

---

## 📁 Struktur Proyek

```
ai-agent/
├── agent_ultimate.py   # Script utama
├── .env                # Konfigurasi (auto‑generated, jangan di‑commit)
├── logs/               # Folder log proyek
└── README.md           # Dokumentasi ini
```

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|--------|--------|
| `401 User not found` | Pastikan API key sesuai dengan provider yang dipilih. Untuk OpenRouter, key diawali `sk-or-v1-`. Untuk OpenAI, diawali `sk-`. |
| Koneksi terputus (`ConnectionResetError`) | Agen sudah dilengkapi auto‑retry 3 kali. Jika masih gagal, periksa koneksi internet atau ganti provider. |
| GitHub tidak terhubung | Jalankan `gh auth login` di terminal, atau set environment variable `GITHUB_TOKEN`. |
| `tmux` tidak ditemukan | Install dengan `sudo apt install tmux` (Ubuntu) atau `pkg install tmux` (Termux). |
| Prompt tidak muncul di Termux | Pastikan menggunakan versi Python 3.8+ dan library `rich` terbaru. Bisa juga coba `export TERM=xterm-256color`. |
| Auto‑update gagal | Pastikan direktori script dapat ditulis. Jika tidak, hapus file `.env` dan setup ulang. |

---

## 🤝 Kontribusi

Kami sangat terbuka untuk kontribusi! Silakan buka *issue* atau *pull request* di repositori [https://github.com/Vicienna/ai-agent](https://github.com/Vicienna/ai-agent).

---

## 📄 Lisensi

Dirilis di bawah lisensi **MIT**. Lihat file `LICENSE` untuk detailnya.

---

**Dibuat dengan ❤️ untuk produktivitas maksimal di terminal. Siap coding? Jalankan agen dan ucapkan perintah pertama Anda!** 🚀
