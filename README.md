## 📃 `README.md`

# 🤖 Tagent – Your Personal AI Developer Agent

**Tagent** adalah asisten AI cerdas yang berjalan di terminal (Termux/Linux) dan dapat melakukan hampir semua tugas pengembangan perangkat lunak secara otomatis.  
Dari mengelola proyek, menulis kode, menjalankan server, push ke GitHub, hingga memonitor error dan memperbaikinya sendiri — semuanya dari satu chat interaktif.

---

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg?style=for-the-badge&logo=python" alt="Version">
  <img src="https://img.shields.io/badge/Made%20with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Termux%20%7C%20Linux-blueviolet?style=for-the-badge&logo=android" alt="Platform">
</p>

---

## ✨ Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| 🧠 **Multi‑Provider AI** | Dukung OpenAI, OpenRouter, Groq, Ollama (lokal), dan custom endpoint. |
| 🔃 **Auto Update** | Memeriksa dan memperbarui dirinya sendiri dari repo GitHub. |
| 🚀 **Auto Run / Stop** | Menjalankan proyek di background dengan `tmux`, lengkap dengan log. |
| 🐛 **Auto Fix** | Memonitor log, mendeteksi error, lalu menganalisis dan memperbaiki kode otomatis. |
| 📋 **Log Panel** | Menampilkan baris terakhir log proyek langsung di terminal. |
| 🛑 **Anti‑Pengulangan** | Mencegah pemanggilan tool yang sama berulang kali tanpa henti. |
| ⏱ **Thinking Timer** | Animasi proses berpikir model secara real‑time (detik.milidetik). |
| ❌ **Cancel (Ctrl+C)** | Membatalkan proses yang sedang berjalan kapan saja. |
| 🌐 **GitHub Integration** | Membuat repo, push, clone — semuanya lewat `gh` CLI. |
| ⚡ **Perintah Global `tagent`** | Setelah setup, cukup ketik `tagent` di terminal dari mana saja. |

---

## 📦 Instalasi

### Prasyarat
- **Termux** atau **Linux**
- **Python 3.8+** dan `pip`
- **Git** dan **GitHub CLI (`gh`)** (untuk fitur GitHub)
- **tmux** (untuk auto run)

```bash
# 1. Clone repository
git clone https://github.com/Vicienna/ai-agent.git
cd ai-agent

# 2. Install dependensi Python
pip install -r requirements.txt
```

### Setup Awal
Jalankan agent pertama kali:
```bash
python agent.py
```
Kamu akan dipandu melalui wizard untuk memilih provider AI, model, dan (opsional) GitHub token.  
Di akhir wizard, kamu bisa mengaktifkan perintah global `tagent` agar bisa dipanggil dari mana saja.

---

## 🚀 Penggunaan

```bash
# Jika sudah mengaktifkan perintah global
tagent

# Atau langsung dari folder proyek
python agent.py
```

Setelah masuk, cukup ketik perintah seperti:
```
▸ Buat proyek Node.js sederhana
▸ Jalankan proyek sp-api
▸ Upload proyek ini ke GitHub dengan nama spaceapi
▸ Ganti model ke gemini-2.0-flash-001
```

Tagent akan memahami maksud Anda, merencanakan langkah, dan mengeksekusinya sambil menunjukkan proses berpikirnya.

---

## 🧩 Konfigurasi Provider

Tagent mendukung banyak provider. Pilih saat setup atau ganti langsung dari chat dengan `change_provider`.

| Provider | Base URL | API Key |
|----------|----------|---------|
| OpenAI | `https://api.openai.com/v1` | [OpenAI API Keys](https://platform.openai.com/api-keys) |
| OpenRouter | `https://openrouter.ai/api/v1` | [OpenRouter Keys](https://openrouter.ai/keys) |
| Groq | `https://api.groq.com/openai/v1` | [Groq Cloud](https://console.groq.com/keys) |
| Ollama (Local) | `http://localhost:11434/v1` | *tidak diperlukan* |
| Custom | sesuaikan | sesuaikan |

**Model rekomendasi yang telah teruji** (mendukung function calling):
- `google/gemini-2.0-flash-001` (gratis, cepat)
- `openai/gpt-4o`
- `anthropic/claude-3.5-sonnet`
- `llama-3.1-70b-versatile` (via Groq)
- `nemotron-3-super:cloud` (via Ollama lokal)

---

## 🎬 Demo Singkat

```
$ tagent

╭─ Welcome ──────────────────────────────────╮
│                                                    │
│       🤖  T A G E N T  🤖                          │
│                                                    │
│       Creator : Vicienna                           │
│       Source  : github.com/Vicienna/ai-agent       │
│       IG: ceena.dev  GitHub: Vicienna              │
│       Discord: hallo.dev                           │
│                                                    │
╰────────────────────────────────────────────╯
╭────────────────────────────────────────────╮
│ Provider: Ollama (Local) | Model:                  │
│ nemotron-3-super:cloud | GitHub: ✅                │
╰────────────────────────────────────────────╯

▸ Buat web server Python sederhana

🧠 Thinking... ⏱ 2.3s

🔧 write_file
📤 server.py ditulis.

🔧 auto_run
📤 Proyek python_server dijalankan. Log: .../logs/python_server.log

🤖 Tagent: Web server berhasil dibuat dan dijalankan di port 8080.
```

---

## 🛠️ Struktur Proyek

```
ai-agent/
├── agent.py               # Skrip utama Tagent
├── .env                   # Konfigurasi (API key, provider, model)
├── agent_memory.json      # Memori tugas (auto-fix queue)
├── requirements.txt       # Dependensi Python
├── logs/                  # Log proyek yang dijalankan
└── README.md
```

---

## 🤝 Kontak & Sosial

- **GitHub** : [Vicienna](https://github.com/Vicienna)
- **Instagram** : [@ceena.dev](https://instagram.com/ceena.dev)
- **Discord** : [hallo.dev](https://discord.gg/) *(undangan tautan khusus)*

Jangan ragu untuk berkontribusi atau melaporkan masalah di [issues](https://github.com/Vicienna/ai-agent/issues).

---

## 📄 Lisensi

MIT – bebas digunakan, dimodifikasi, dan disebarluaskan.  
© 2026 Tagado - by Vicienna

---

<p align="center">
  Made with ❤️ by Vicienna
</p>
