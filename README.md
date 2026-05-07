## 📃 `README.md`

# 🤖 AI Agent Ultimate

Agen AI terminal dengan dukungan **multi‑provider** (OpenAI, OpenRouter, Custom), integrasi **GitHub** via `gh` CLI, dan kemampuan membuat proyek pemrograman lengkap secara otomatis. Cocok untuk Ubuntu, Termux, dan lingkungan Linux lainnya.

![Agent Screenshot](https://via.placeholder.com/800x400?text=AI+Agent+Ultimate)

## 🌟 Fitur Utama

- 🔌 **Multi‑API**: Pilih OpenAI, OpenRouter (bisa akses model Google, Meta, dll.), atau endpoint custom.
- 🛠️ **Setup Wizard**: Konfigurasi interaktif saat pertama dijalankan (API key, model, GitHub).
- 📁 **Manajemen File**: Baca, tulis, edit file langsung dari percakapan.
- 🐧 **Shell Command**: Jalankan perintah shell (`git`, `npm`, `pip`, dll.) dengan konfirmasi.
- 🐙 **GitHub Terintegrasi**:
  - Buat repository baru
  - Push perubahan
  - Clone repository
  - Semua lewat `gh` CLI (tidak perlu token manual)
- ⏹️ **Fitur Cancel**: Tekan `Ctrl+C` untuk membatalkan AI yang sedang berpikir atau tool yang sedang berjalan.
- 🔄 **Auto‑Retry**: Jika koneksi terputus (misal di Termux), agen otomatis mencoba ulang hingga 3 kali.
- 🧹 **Clear Screen**: Tampilan selalu bersih setiap kali agen dijalankan.
- 📦 **Ringan**: Hanya membutuhkan `requests`, `rich`, `gitpython`, `python-dotenv` – tanpa kompilasi Rust atau library berat.

## 📋 Persyaratan

- **Python** 3.8 atau lebih baru
- **Git** (`pkg install git` di Termux)
- **GitHub CLI** (`gh`) – install dengan `pkg install gh` lalu login: `gh auth login`
- (Opsional) **Node.js**, **npm**, dll. sesuai proyek yang ingin dibuat

## 🚀 Instalasi

```bash
# 1. Clone repositori ini atau simpan script agent_ultimate.py
git clone https://github.com/Vicienna/ai-agent
cd ai-agent

# 2. Install dependensi
pip install requests rich python-dotenv gitpython

# 3. Jalankan
python agent_ultimate.py
```

Saat pertama dijalankan, **Setup Wizard** akan muncul dan memandu Anda mengisi:
- Penyedia API (OpenAI / OpenRouter / Custom)
- API key (dengan link langsung)
- Model AI
- Koneksi GitHub
- Direktori kerja (opsional)

Semua pengaturan disimpan di file `.env` (tidak akan ditampilkan ke publik).

## ⚙️ Konfigurasi

File `.env` berisi:

```
API_KEY=sk-or-v1-...
API_PROVIDER=OpenRouter (akses Google, Meta, dll.)
API_BASE_URL=https://openrouter.ai/api/v1
MODEL=meta-llama/llama-3.1-70b-instruct
GITHUB_TOKEN=... (opsional jika sudah pakai gh)
WORK_DIR=... (opsional)
```

Untuk mengulangi setup, cukup hapus file `.env` lalu jalankan ulang agen.

## 📖 Penggunaan

Setelah masuk ke antarmuka agen, cukup ketik instruksi seperti biasa:

```
▸ Buatkan REST API Express untuk Discord bot, lengkap dengan endpoint /ping, /servers, lalu push ke repo GitHub bernama discord-api.
```

Agen akan:
1. Membuat folder proyek (`discord-api`)
2. Menjalankan `npm init -y` dan `npm install express`
3. Menulis file `index.js`, `package.json`, dll.
4. Membuat repository GitHub `discord-api`
5. Mengatur remote origin
6. Commit dan push seluruh perubahan

Untuk mengembangkan proyek yang sudah ada, cukup arahkan agen ke direktori proyek dan berikan instruksi edit:

```
▸ Masuk ke folder discord-api
▸ Tambahkan endpoint /moderation untuk ban user
```

Agen akan membaca file, mengeditnya, lalu commit & push.

### Perintah Khusus

| Perintah | Keterangan |
|----------|------------|
| `exit` / `quit` / `keluar` | Keluar dari agen |
| `Ctrl+C` saat AI berpikir | Batalkan permintaan terakhir |
| `Ctrl+C` saat tool berjalan | Batalkan tool (agen melanjutkan ke langkah berikutnya) |

## 🎯 Model AI yang Didukung

### OpenAI
- gpt-4o
- gpt-4-turbo
- gpt-3.5-turbo
- Custom

### OpenRouter (mencakup)
- meta-llama/llama-3.1-70b-instruct
- meta-llama/llama-3.1-8b-instruct
- google/gemini-2.0-flash-001
- anthropic/claude-3.5-sonnet
- openai/gpt-4o
- Custom

### Custom
Masukkan ID model dan base URL sendiri (Mistral, Groq, DeepSeek, dll.) – semua endpoint yang kompatibel dengan API OpenAI dapat digunakan.

## 🔧 Troubleshooting

### Koneksi Terputus (`ConnectionResetError`)
Agen sudah dilengkapi auto-retry hingga 3 kali dengan jeda eksponensial. Jika masih gagal, periksa koneksi internet atau coba ganti penyedia API.

### API Key Salah (`401 User not found`)
- Pastikan API key sesuai dengan provider yang dipilih.
- Untuk OpenRouter, key diawali `sk-or-v1-...`.
- Untuk OpenAI, key diawali `sk-...`.

### GitHub Tidak Terhubung
- Jalankan `gh auth login` di terminal.
- Atau set environment variable `GITHUB_TOKEN` dengan personal access token.

### Storage Penuh di Termux
- Bersihkan cache: `pip cache purge && pkg clean`
- Gunakan script ini karena tidak memerlukan kompilasi (tidak butuh Rust/`jiter`/`PyGithub`).

## 📁 Struktur Proyek

```
ai-agent-ultimate/
├── agent_ultimate.py   # Script utama
├── .env                # Konfigurasi (auto-generated, jangan di-commit)
└── README.md           # Dokumentasi ini
```

## 🧪 Contoh Skenario Lengkap

1. **Buat proyek baru**
   ```
   ▸ Buatkan REST API Python FastAPI dengan endpoint /status dan /users, push ke repo fastapi-users
   ```
2. **Update proyek yang sudah ada**
   ```
   ▸ Masuk ke folder fastapi-users
   ▸ Tambahkan validasi email di endpoint /users
   ▸ Push perubahannya
   ```
3. **Clone dan kerjakan proyek dari GitHub**
   ```
   ▸ Clone repo https://github.com/teman/laravel-blog
   ▸ Ganti koneksi database di .env jadi pgsql
   ▸ Push perubahan
   ```

## 🙏 Kredit

Dibuat dengan ❤️ untuk produktivitas maksimal di terminal.  
Menggunakan [Rich](https://github.com/Textualize/rich) untuk UI terminal yang indah, dan [gh CLI](https://cli.github.com/) untuk integrasi GitHub tanpa token.

---

**Siap untuk coding? Jalankan agen dan ucapkan perintah pertama Anda!** 🚀
