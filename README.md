## 📄 `README.md`

# 🤖 AI Agent Ultimate

AI Agent yang berjalan di terminal dengan dukungan **multi‑penyedia API** (OpenAI, OpenRouter, Google, Custom) dan integrasi **GitHub**. Dapat membuat proyek dari nol, mengelola file, menjalankan perintah shell, serta melakukan push/pull otomatis ke GitHub. Dilengkapi dengan **Setup Wizard** interaktif sehingga pengguna tinggal jalankan, pilih penyedia, masukkan API key, dan langsung siap digunakan.

---

## ✨ Fitur Unggulan

- 🧠 **Multi‑API**: Bisa pakai OpenAI, OpenRouter (akses puluhan model seperti Llama, Gemini, Claude), atau endpoint kustom apa pun.
- 🔧 **Tools Lengkap**: Membaca, menulis, mengedit file; membuat folder proyek; menjalankan perintah shell (`npm init`, `git init`, dll.).
- 🐙 **GitHub Terintegrasi**: Buat repo, clone, push, pull, commit otomatis.
- 🧭 **Setup Wizard**: Saat pertama kali dijalankan, akan memandu memilih penyedia, memasukkan API key, memilih model, dan menghubungkan GitHub. Semua konfigurasi disimpan di file `.env`.
- 🎨 **UI Keren**: Warna‑warni panel, syntax highlighting, dan output tool yang jelas berkat pustaka `rich`.
- 📱 **Multi‑Platform**: Bisa dijalankan di Ubuntu, Debian, Termux (Android), Windows (WSL), dan macOS.

---

## 📦 Persyaratan

- Python 3.8 atau lebih baru
- Git (opsional, untuk fitur repositori lokal)
- Node.js (opsional, untuk proyek Node.js)
- `gh` CLI (opsional, jika tidak pakai Personal Access Token)
- Koneksi internet

---

## 🚀 Panduan Instalasi & Setup

### 1. Clone Repo atau Unduh Kode

```bash
git clone https://github.com/Vicienna/ai-agent.git
cd ai-agent-ultimate
```

Atau cukup unduh file `agent_ultimate.py` dan simpan di folder yang kamu inginkan.

### 2. Instal Dependensi

#### Di Ubuntu / Debian / WSL

```bash
sudo apt update && sudo apt install python3 python3-pip git gh nodejs npm -y
pip install openai rich gitpython PyGithub python-dotenv
```

#### Di Termux (Android)

```bash
pkg update && pkg upgrade
pkg install python git gh nodejs-lts
pip install openai rich gitpython PyGithub python-dotenv
```

*Catatan: Jika ada masalah dengan `pip` di Termux, jalankan `pip install --extra-index-url https://termux-user-repository.github.io/pypi/ nama-paket` untuk paket tertentu.*

#### Di macOS

```bash
brew install python git gh node
pip3 install openai rich gitpython PyGithub python-dotenv
```

### 3. Siapkan API Key

Kamu akan memerlukan API key dari penyedia AI pilihanmu:

- **OpenRouter** (rekomendasi – bisa akses banyak model): [openrouter.ai/keys](https://openrouter.ai/keys)
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Google Gemini** (via OpenRouter dengan ID `google/gemini-2.0-flash-001`)
- **Custom**: penyedia lain yang kompatibel dengan API OpenAI (mis. Mistral, Groq, dll.)

**Catatan**: jangan bagikan API key‑mu. Simpan aman.

### 4. Jalankan Agent

```bash
python agent_ultimate.py
```

### 5. Ikuti Setup Wizard

Saat pertama kali dijalankan, agent akan menampilkan **Setup Wizard**:

1. **Pilih Penyedia API**  
   - `1` untuk OpenAI  
   - `2` untuk OpenRouter  
   - `3` untuk Custom (masukkan base URL sendiri)  

2. **Masukkan API Key** – wizard akan menampilkan link untuk mendapatkan key dan kamu tinggal paste.

3. **Pilih Model**  
   - Untuk OpenRouter: Llama 3.1 70B, Gemini 2.0 Flash, Claude 3.5 Sonnet, dll.  
   - Untuk OpenAI: gpt-4o, gpt-4-turbo, dll.  
   - Atau ketik manual ID model.

4. **Hubungkan GitHub (Opsional)**  
   - Pilih mau pakai Personal Access Token atau `gh` CLI.  
   - Jika pakai token, masukkan token‑nya. Agent akan memvalidasi.

5. **Tentukan Direktori Kerja (Opsional)** – biarkan kosong untuk direktori saat ini.

Setelah wizard selesai, semua pengaturan disimpan di file `.env`. Agent langsung siap digunakan.

---

## 💬 Cara Menggunakan

Setelah masuk ke mode chat, kamu bisa memberikan instruksi dengan bahasa natural (Indonesia atau Inggris). Contoh:

```
▸ Buatkan REST API Express untuk Discord bot, dengan endpoint /ping dan /guilds.
   Simpan di folder discord-bot, inisialisasi npm, dan push ke repo GitHub.
```

Agent akan otomatis:

- Membuat folder proyek
- Menjalankan `npm init -y` dan `npm install express`
- Menulis file `index.js`, `package.json` (jika perlu)
- Membuat repo GitHub
- Menghubungkan git remote
- Commit dan push perubahan

Lanjutkan pengembangan dengan perintah seperti:

```
▸ Tambahkan endpoint /commands yang mengembalikan daftar perintah bot.
```

Agent akan membaca file yang ada, mengeditnya, lalu commit & push.

**Perintah singkat lain yang bisa digunakan:**

| Perintah | Fungsi |
|----------|--------|
| `exit` / `quit` / `keluar` | Keluar dari agent |
| `ls` / `list` | Lihat isi direktori kerja |
| `ke folder <nama>` | Pindah direktori kerja |
| `baca <file>` | Tampilkan isi file |

---

## 🔁 Mengulang Setup

Jika kamu ingin mengganti penyedia, model, atau konfigurasi lainnya:

1. Hapus file `.env` yang ada di folder yang sama dengan script.
2. Jalankan ulang `python agent_ultimate.py`.
3. Wizard akan muncul kembali.

---

## 🛠️ Troubleshooting

### `gh` tidak bisa login di Termux
- Gunakan opsi **Paste an authentication token** saat `gh auth login`.

### Error `pip` di Termux
- Coba gunakan indeks tambahan:  
  ```bash
  pip install nama-paket --extra-index-url https://termux-user-repository.github.io/pypi/
  ```

### Model tidak ditemukan (OpenRouter)
- Pastikan ID model benar, contohnya `meta-llama/llama-3.1-70b-instruct`. Cek listing model di [openrouter.ai/models](https://openrouter.ai/models).

### Token GitHub tidak valid
- Pastikan token miliki scope (biasanya `repo` dan `workflow`). Atau gunakan `gh auth login` untuk kemudahan.

---

## 📝 Lisensi

MIT – silakan gunakan dan modifikasi sesuai kebutuhan.

---

**Selamat ngoding bareng AI!** 🚀
