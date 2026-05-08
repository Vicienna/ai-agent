#!/usr/bin/env python3
"""
AI Agent Ultimate – Auto Update + Auto Run + Auto Fix + Log Panel + Change Provider
Multi-Provider, GitHub via gh CLI, Tmux session manager, anti-pengulangan.
"""

import os, sys, subprocess, json, time, hashlib, queue, threading
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter, Retry
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt
import git
from dotenv import load_dotenv, set_key

# ---------- password input dengan bintang ----------
def password_prompt(prompt_text="Password: "):
    import termios, tty
    console.print(prompt_text, end="")
    password = []
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\n', '\r'):
                break
            elif ch == '\x7f':
                if password:
                    password.pop()
                    sys.stdout.write('\b \b')
            else:
                password.append(ch)
                sys.stdout.write('*')
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    console.print()
    return ''.join(password)

console = Console()
ENV_FILE = Path(__file__).parent / ".env"
CWD = Path.cwd()
active_project = None   # menyimpan nama proyek yang sedang berjalan
tool_call_counter = {}  # untuk deteksi pengulangan tool

# ----------------------- AUTO UPDATE -----------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Vicienna/ai-agent/main/agent_ultimate.py"
SCRIPT_PATH = Path(__file__).resolve()

def check_and_update():
    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=10)
        if resp.status_code != 200:
            console.print("[yellow]⚠ Gagal cek update: HTTP {}[/]".format(resp.status_code))
            return False
        remote_content = resp.text
        local_content = SCRIPT_PATH.read_text()
        if hashlib.md5(remote_content.encode()).hexdigest() != hashlib.md5(local_content.encode()).hexdigest():
            console.print("[bold cyan]🔃 Update tersedia! Memperbarui...[/]")
            SCRIPT_PATH.write_text(remote_content)
            console.print("[bold green]✅ Script sudah diperbarui. Restart...[/]")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            console.print("[dim]✓ Script sudah yang terbaru.[/]")
            return True
    except Exception as e:
        console.print(f"[yellow]⚠ Gagal cek update: {e}[/]")
    return True

# ----------------------- SETUP WIZARD -----------------------
def run_setup():
    console.print(Panel.fit("[bold cyan]🛠️  Setup Wizard[/]", border_style="bright_blue"))
    providers = {
        "1": {"name": "OpenAI", "base": "https://api.openai.com/v1", "key_link": "https://platform.openai.com/api-keys"},
        "2": {"name": "OpenRouter", "base": "https://openrouter.ai/api/v1", "key_link": "https://openrouter.ai/keys"},
        "3": {"name": "Custom", "base": "", "key_link": ""}
    }
    for k, v in providers.items():
        console.print(f"  {k}. {v['name']}")
    choice = Prompt.ask("Pilih provider", choices=list(providers.keys()), default="2")
    provider = providers[choice]
    console.print(f"\n[bold]API Key {provider['name']}[/]")
    if provider["key_link"]:
        console.print(f"🔗 Dapatkan: {provider['key_link']}")
    api_key = password_prompt("Masukkan API key: ")
    set_key(ENV_FILE, "API_KEY", api_key)
    set_key(ENV_FILE, "API_PROVIDER", provider["name"])
    if choice == "3":
        console.print("Contoh base URL: https://api.groq.com/v1 (tanpa /chat/completions)")
        base_url = Prompt.ask("Masukkan base URL").strip().rstrip('/')
        set_key(ENV_FILE, "API_BASE_URL", base_url)
    else:
        set_key(ENV_FILE, "API_BASE_URL", provider["base"])
    if choice == "1":
        models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "Custom"]
    elif choice == "2":
        models = [
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-2.0-flash-001",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "poolside/laguna-m.1:free",
            "Custom"
        ]
    else:
        models = ["Custom"]
    for i, m in enumerate(models, 1):
        console.print(f"  {i}. {m}")
    model_choice = Prompt.ask("Pilih model", choices=[str(i) for i in range(1, len(models)+1)], default="1")
    if models[int(model_choice)-1] == "Custom":
        model = Prompt.ask("ID model")
    else:
        model = models[int(model_choice)-1]
    set_key(ENV_FILE, "MODEL", model)
    try:
        subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        console.print("[green]✓ gh CLI login.[/]")
    except:
        console.print("[yellow]⚠ Jalankan 'gh auth login'[/]")
    d = Prompt.ask("Direktori kerja (kosongkan = sekarang)")
    if d.strip():
        set_key(ENV_FILE, "WORK_DIR", d)
    console.print("[green]✅ Setup selesai![/]")

# ----------------------- LOAD CONFIG -----------------------
def load_config():
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    if not os.getenv("API_KEY"):
        run_setup()
        load_dotenv(ENV_FILE, override=True)
    work_dir = os.getenv("WORK_DIR")
    if work_dir:
        os.chdir(Path(work_dir).expanduser().resolve())
    global CWD
    CWD = Path.cwd()

# ----------------------- API CLIENT -----------------------
def normalize_api_url(base):
    """Pastikan URL mengarah ke /chat/completions tanpa duplikasi."""
    base = base.rstrip('/')
    if base.endswith('/chat/completions'):
        return base
    else:
        return f"{base}/chat/completions"

def chat_completion(messages, tools=None, max_retries=3):
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("API_BASE_URL")
    provider = os.getenv("API_PROVIDER", "")
    model = os.getenv("MODEL")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if "OpenRouter" in provider:
        headers["HTTP-Referer"] = "http://localhost"
        headers["X-Title"] = "AI-Agent"
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    session = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=1,
                    status_forcelist=[429, 502, 503, 504],
                    allowed_methods=["POST"],
                    respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    url = normalize_api_url(base_url)
    for attempt in range(max_retries):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 10
                console.print(f"[yellow]⏳ Rate limit 429. Menunggu {wait} detik...[/]")
                time.sleep(wait)
                continue  # coba lagi
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
            return resp.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            if attempt < max_retries - 1:
                console.print(f"[yellow]⚠ Koneksi gagal, coba lagi ({attempt+2}/{max_retries})...[/]")
                time.sleep(2 ** attempt)
            else:
                return {"error": f"Koneksi gagal setelah {max_retries}x: {e}"}
    return {"error": "Gagal"}

# ----------------------- TOOLS: GITHUB -----------------------
def check_github():
    try:
        subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        return True
    except:
        return False

def ensure_git_identity():
    """Mengatur user.email dan user.name lokal jika belum ada."""
    try:
        repo = git.Repo(CWD)
        reader = repo.config_reader()
        if not reader.has_option("user", "email") or not reader.has_option("user", "name"):
            res = subprocess.run(["gh", "api", "user"], capture_output=True, text=True)
            if res.returncode == 0:
                user_data = json.loads(res.stdout)
                email = user_data.get("email", "user@example.com")
                name = user_data.get("name", user_data.get("login", "User"))
            else:
                email = "user@example.com"
                name = "AI Agent User"
            writer = repo.config_writer()
            writer.set_value("user", "email", email)
            writer.set_value("user", "name", name)
            writer.release()
            console.print(f"[dim]Git identity diset: {name} <{email}>[/]")
    except Exception as e:
        console.print(f"[yellow]⚠ Gagal mengatur identitas Git: {e}[/]")

def github_create_repo(name, private=False, description=""):
    ensure_git_identity()
    cmd = ["gh", "repo", "create", name, "--push"]
    if private: cmd.append("--private")
    else: cmd.append("--public")
    if description: cmd.extend(["-d", description])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=CWD)
        output = res.stdout.strip() or f"Repo {name} dibuat."
        # perbaiki remote origin setelah create
        subprocess.run(["git", "remote", "remove", "origin"], capture_output=True, cwd=CWD)
        subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{os.getenv('GITHUB_USER', '')}/{name}.git"], capture_output=True, cwd=CWD)
        return output
    except Exception as e:
        return f"ERROR: {e}"

def github_push(commit_msg="Update from AI Agent"):
    try:
        ensure_git_identity()
        repo = git.Repo(CWD)
        if repo.is_dirty(untracked_files=True):
            repo.git.add(A=True)
            repo.index.commit(commit_msg)
            subprocess.run(["git", "push", "-u", "origin", "HEAD"], check=True, capture_output=True, cwd=CWD)
            return f"✅ Pushed: {commit_msg}"
        return "Tidak ada perubahan."
    except Exception as e:
        return f"ERROR: {e}"

def github_clone(repo_url, target_dir=""):
    cmd = ["gh", "repo", "clone", repo_url]
    if target_dir: cmd.append(target_dir)
    try:
        subprocess.run(cmd, check=True, capture_output=True, cwd=CWD)
        return f"Repo {repo_url} di-clone."
    except Exception as e:
        return f"ERROR: {e}"

# ----------------------- TMUX / AUTO RUN -----------------------
LOG_DIR = CWD / "logs"
LOG_DIR.mkdir(exist_ok=True)

def auto_run(command, project_name):
    global active_project
    subprocess.run(["tmux", "kill-session", "-t", project_name], capture_output=True)
    log_file = LOG_DIR / f"{project_name}.log"
    subprocess.run([
        "tmux", "new-session", "-d", "-s", project_name,
        f"bash -c '{command} 2>&1 | tee {log_file}'"
    ])
    active_project = project_name
    return f"Proyek {project_name} dijalankan. Log: {log_file}"

def auto_stop(project_name):
    global active_project
    subprocess.run(["tmux", "kill-session", "-t", project_name], capture_output=True)
    if active_project == project_name:
        active_project = None
    return f"Sesi {project_name} dihentikan."

# ----------------------- AUTO FIX / MONITOR -----------------------
error_queue = queue.Queue()

def monitor_logs(project_name):
    log_file = LOG_DIR / f"{project_name}.log"
    if not log_file.exists():
        return
    last_size = 0
    while True:
        time.sleep(2)
        if not log_file.exists():
            continue
        try:
            current_size = log_file.stat().st_size
            if current_size > last_size:
                with open(log_file, 'r') as f:
                    f.seek(last_size)
                    new_content = f.read()
                last_size = current_size
                if any(kw in new_content for kw in ["Traceback", "Error", "error", "FATAL"]):
                    error_queue.put((project_name, new_content))
        except:
            pass

# ----------------------- LOG PANEL -----------------------
def show_log_panel(project_name, lines=10):
    if not project_name:
        return
    log_file = LOG_DIR / f"{project_name}.log"
    if not log_file.exists():
        return
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        content = "".join(last_lines).rstrip()
        if content:
            console.print(Panel(content, title=f"📋 Log [{project_name}]", border_style="blue", height=min(10, len(last_lines)+2)))
    except Exception as e:
        console.print(f"[yellow]Gagal membaca log: {e}[/]")

# ----------------------- TOOLS: BASE -----------------------
def change_directory(path):
    global CWD
    try:
        new = (CWD / path).resolve()
        if not new.is_dir():
            return f"ERROR: {path} bukan direktori."
        os.chdir(new)
        CWD = new
        return f"Pindah ke {CWD}"
    except Exception as e:
        return f"ERROR: {e}"

def list_directory(path="."):
    target = (CWD / path).resolve()
    if not target.is_dir():
        return f"ERROR: {path} bukan direktori."
    items = os.listdir(target)
    dirs = [d for d in items if (target / d).is_dir()]
    files = [f for f in items if (target / f).is_file()]
    result = ""
    if dirs:
        result += "[DIR] " + ", ".join(dirs) + "\n"
    if files:
        result += "[FILE] " + ", ".join(files)
    return result.strip() or "Kosong"

def shell_command(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=CWD)
        output = (res.stdout + res.stderr).strip()
        return output if output else "(ok)"
    except subprocess.TimeoutExpired:
        return "ERROR: Perintah timeout (60 detik)."
    except Exception as e:
        return f"ERROR: {e}"

def read_file(path):
    full = (CWD / path).resolve()
    return full.read_text() if full.is_file() else f"ERROR: {path} tidak ditemukan."

def write_file(path, content):
    full = (CWD / path).resolve()
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return f"✅ {path} ditulis ({len(content)} karakter)."

def edit_file(path, old_str, new_str):
    full = (CWD / path).resolve()
    if not full.is_file():
        return f"ERROR: {path} tidak ditemukan."
    text = full.read_text()
    if old_str not in text:
        return f"ERROR: string tidak ditemukan dalam file."
    new_text = text.replace(old_str, new_str, 1)
    full.write_text(new_text)
    return f"✅ {path} diedit (1 perubahan)."

# ----------------------- TOOL: CHANGE PROVIDER -----------------------
def change_provider(provider=None, api_key=None, base_url=None, model=None):
    """Ganti provider/API/key/model langsung dari chat."""
    if provider:
        set_key(ENV_FILE, "API_PROVIDER", provider)
    if api_key:
        set_key(ENV_FILE, "API_KEY", api_key)
    if base_url:
        set_key(ENV_FILE, "API_BASE_URL", base_url)
    if model:
        set_key(ENV_FILE, "MODEL", model)
    # Reload environment
    load_dotenv(ENV_FILE, override=True)
    new_provider = os.getenv("API_PROVIDER", "Tidak diketahui")
    new_model = os.getenv("MODEL", "Tidak diketahui")
    return f"✅ Provider diubah: {new_provider} | Model: {new_model}"

# ----------------------- TOOL SPECS -----------------------
tools_spec = [
    {"type": "function", "function": {"name": "change_directory", "description": "Pindah direktori.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_directory", "description": "Lihat isi direktori (jangan ulangi).", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}}},
    {"type": "function", "function": {"name": "shell_command", "description": "Jalankan perintah shell. Hindari pengulangan.", "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Baca file (hanya jika diperlukan).", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Tulis file baru atau timpa.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Edit file dengan find/replace.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}}, "required": ["path", "old_str", "new_str"]}}},
    {"type": "function", "function": {"name": "github_create_repo", "description": "Buat repo GitHub.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "private": {"type": "boolean", "default": False}, "description": {"type": "string", "default": ""}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "github_push", "description": "Push perubahan ke GitHub.", "parameters": {"type": "object", "properties": {"commit_msg": {"type": "string", "default": "Update from AI Agent"}}}}},
    {"type": "function", "function": {"name": "github_clone", "description": "Clone repo dari GitHub.", "parameters": {"type": "object", "properties": {"repo_url": {"type": "string"}, "target_dir": {"type": "string", "default": ""}}, "required": ["repo_url"]}}},
    {"type": "function", "function": {"name": "auto_run", "description": "Jalankan proyek di tmux session (non-bloking).", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "project_name": {"type": "string"}}, "required": ["command", "project_name"]}}},
    {"type": "function", "function": {"name": "auto_stop", "description": "Hentikan proyek yang berjalan.", "parameters": {"type": "object", "properties": {"project_name": {"type": "string"}}, "required": ["project_name"]}}},
    {"type": "function", "function": {"name": "change_provider", "description": "Ganti provider AI (OpenAI, OpenRouter, Custom), API key, base URL, atau model.", "parameters": {"type": "object", "properties": {
        "provider": {"type": "string", "description": "Nama provider (OpenAI, OpenRouter, Custom)"},
        "api_key": {"type": "string", "description": "API key baru"},
        "base_url": {"type": "string", "description": "Base URL API (contoh: https://api.openai.com/v1)"},
        "model": {"type": "string", "description": "Nama model (contoh: gpt-4o, google/gemini-2.0-flash-001)"}
    }, "required": []}}},
]

tool_map = {
    "change_directory": change_directory,
    "list_directory": list_directory,
    "shell_command": shell_command,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "github_create_repo": github_create_repo,
    "github_push": github_push,
    "github_clone": github_clone,
    "auto_run": auto_run,
    "auto_stop": auto_stop,
    "change_provider": change_provider,
}

# ----------------------- DETEKSI PENGULANGAN TOOL -----------------------
MAX_REPEATED_CALLS = 3   # maksimum panggilan tool identik berturut-turut

def process_tool_calls(messages, tool_calls):
    global active_project, tool_call_counter
    new_msgs = []
    for tc in tool_calls:
        func_name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        args_str = json.dumps(args, sort_keys=True)  # urutkan supaya konsisten
        key = f"{func_name}:{args_str}"

        # Hitung pengulangan
        tool_call_counter[key] = tool_call_counter.get(key, 0) + 1
        if tool_call_counter[key] > MAX_REPEATED_CALLS:
            console.print(f"[red]⚠ Tool {func_name} dipanggil >{MAX_REPEATED_CALLS}x dengan argumen sama. Diabaikan.[/]")
            result = f"❌ Tindakan '{func_name}' diabaikan karena terlalu sering diulang dengan argumen yang sama."
        else:
            console.print(f"[dim]🔧 {func_name}[/]")
            func = tool_map.get(func_name)
            if func:
                try:
                    result = func(**args)
                except TypeError as e:
                    result = f"ERROR: Argumen tidak sesuai - {e}"
                except Exception as e:
                    result = f"ERROR: {e}"
            else:
                result = "Tool tidak dikenal."

        console.print(Panel(Syntax(str(result), "text", theme="monokai"), title=f"📤 {func_name}"))
        new_msgs.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": func_name,
            "content": str(result)
        })

        # Jika auto_run, mulai monitor
        if func_name == "auto_run":
            project = args.get("project_name")
            if project:
                t = threading.Thread(target=monitor_logs, args=(project,), daemon=True)
                t.start()
    return new_msgs

# ----------------------- MAIN LOOP -----------------------
def run_agent():
    global active_project, tool_call_counter
    load_config()
    model = os.getenv("MODEL", "meta-llama/llama-3.1-70b-instruct")
    SYSTEM_PROMPT = f"""Kamu AI Developer Agent di Termux. Dir: {CWD}
Tools: baca/tulis/edit file, shell cmd, GitHub, auto_run/auto_stop, change_provider.

PENTING:
- Jangan mengulangi perintah yang sama jika hasilnya sudah jelas. Contoh: jika kamu sudah mengecek status server dan berhasil, jangan cek lagi.
- Jika diminta membuat fitur, rencanakan dulu, lalu eksekusi. Setelah selesai, beri ringkasan dan berhenti.
- Jangan membaca direktori yang sama berulang kali; gunakan informasi yang sudah kamu miliki.
- Jika ada error dari monitor, analisis perbaikan **hanya satu kali**, jangan mengulangi siklus tanpa batas.
- Gunakan change_provider jika pengguna ingin mengganti API/model.
- Gunakan bahasa Indonesia ramah."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    os.system('clear')
    console.print("[dim]Memeriksa update...[/]")
    check_and_update()
    time.sleep(1)
    os.system('clear')

    console.print(Panel.fit(
        f"[bold cyan]● AI Agent Ultimate[/]\n"
        f"Provider: {os.getenv('API_PROVIDER')} | Model: {model} | GitHub: {'✅' if check_github() else '❌'}\n"
        f"[dim]Fitur: Auto Update | Auto Run | Auto Fix | Log Panel | Anti‑Pengulangan | Ganti Provider[/]",
        border_style="bright_blue"))

    while True:
        # Reset counter pengulangan setiap loop utama agar tidak menumpuk selamanya
        tool_call_counter.clear()

        # Proses error dari queue (auto fix) SEBELUM prompt
        try:
            project, err_text = error_queue.get_nowait()
            console.print(Panel(f"[bold red]🐛 Error terdeteksi di {project}![/]\n{err_text[:500]}", title="Auto Monitor"))
            messages.append({"role": "user", "content": f"ERROR terdeteksi di proyek {project}:\n{err_text}\nPerbaiki dan restart."})
            # Hanya sekali perbaikan, jangan loop, beri kesempatan user
            retry_fix = 0
            while retry_fix < 3:  # maks 3 percobaan perbaikan
                try:
                    resp = chat_completion(messages, tools_spec)
                except KeyboardInterrupt:
                    break
                if "error" in resp:
                    console.print(f"[red]{resp['error']}[/]")
                    break
                msg = resp["choices"][0]["message"]
                messages.append(msg)
                if "tool_calls" in msg:
                    tool_msgs = process_tool_calls(messages, msg["tool_calls"])
                    messages.extend(tool_msgs)
                    retry_fix += 1
                    # Jika tool sudah tidak ada lagi (mungkin sudah selesai), keluar
                    if not tool_msgs:
                        break
                else:
                    if msg.get("content"):
                        console.print(Panel(Markdown(msg["content"]), title="🤖 AI (Auto Fix)", border_style="green"))
                    break
            show_log_panel(active_project)
        except queue.Empty:
            pass

        # Prompt input user
        try:
            user_input = Prompt.ask("\n[bold green]▸[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[red]Keluar.[/]")
            break
        if user_input.lower() in ["exit", "quit", "keluar"]:
            break
        if not user_input.strip():
            continue

        messages.append({"role": "user", "content": user_input})

        # Batasi iterasi agar tidak looping tanpa akhir (maks 20 langkah tool-call replies)
        step = 0
        while step < 20:
            try:
                resp = chat_completion(messages, tools_spec)
            except KeyboardInterrupt:
                console.print("\n[dim]⚠ Dibatalkan.[/]")
                break
            if "error" in resp:
                console.print(f"[red]{resp['error']}[/]")
                break
            msg = resp["choices"][0]["message"]
            messages.append(msg)
            if "tool_calls" in msg:
                tool_msgs = process_tool_calls(messages, msg["tool_calls"])
                messages.extend(tool_msgs)
                step += 1
            else:
                if msg.get("content"):
                    console.print(Panel(Markdown(msg["content"]), title="🤖 AI", border_style="green"))
                break

        show_log_panel(active_project)

if __name__ == "__main__":
    try:
        run_agent()
    except KeyboardInterrupt:
        console.print("\n[red]Keluar.[/]")
