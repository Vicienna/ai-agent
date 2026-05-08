#!/usr/bin/env python3
"""
AI Agent Ultimate – Direct & Streaming, Anti-Pengulangan, Change Provider, Auto Everything
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
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
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
active_project = None
tool_call_counter = {}

# ----------------------- MEMORY (hanya simpan tugas aktif) -----------------------
memory_file = Path(__file__).parent / "agent_memory.json"
task_list = []          # daftar tugas aktif (jika ada dari auto-fix)
completed_tasks = []    # riwayat

def load_memory():
    global task_list, completed_tasks
    if memory_file.exists():
        try:
            data = json.loads(memory_file.read_text())
            task_list = data.get("pending", [])
            completed_tasks = data.get("completed", [])
        except:
            pass

def save_memory():
    memory_file.write_text(json.dumps({
        "pending": task_list,
        "completed": completed_tasks
    }, indent=2))

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

    # --- GitHub Token (opsional) ---
    console.print("\n[bold]🔐 GitHub Token (Opsional)[/]")
    console.print("Masukkan Personal Access Token (classic) dengan scope 'repo' dan 'user'.")
    console.print("Kosongkan jika sudah login gh CLI.")
    github_token = password_prompt("GitHub Token: ")
    if github_token.strip():
        try:
            login_res = subprocess.run(
                ["gh", "auth", "login", "--with-token"],
                input=github_token,
                text=True,
                capture_output=True
            )
            if login_res.returncode == 0:
                console.print("[green]✓ Login gh berhasil.[/]")
                # Ambil info user
                user_res = subprocess.run(["gh", "api", "user"], capture_output=True, text=True)
                if user_res.returncode == 0:
                    user_data = json.loads(user_res.stdout)
                    github_username = user_data.get("login")
                    github_email = user_data.get("email") or f"{github_username}@users.noreply.github.com"
                    github_name = user_data.get("name") or github_username
                    set_key(ENV_FILE, "GITHUB_USER", github_username)
                    os.environ["GITHUB_USER"] = github_username
                    subprocess.run(["git", "config", "--global", "user.name", github_name], check=False)
                    subprocess.run(["git", "config", "--global", "user.email", github_email], check=False)
                    console.print(f"[green]✓ Git config: {github_name} <{github_email}>[/]")
            else:
                console.print(f"[red]Gagal login gh: {login_res.stderr}[/]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
    else:
        try:
            subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
            console.print("[green]✓ gh CLI sudah login.[/]")
        except:
            console.print("[yellow]⚠ gh CLI belum login.[/]")

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
    if not os.getenv("GITHUB_USER"):
        try:
            res = subprocess.run(["gh", "api", "user"], capture_output=True, text=True)
            if res.returncode == 0:
                login = json.loads(res.stdout).get("login")
                if login:
                    set_key(ENV_FILE, "GITHUB_USER", login)
                    os.environ["GITHUB_USER"] = login
        except:
            pass
    load_memory()

# ----------------------- API CLIENT + STREAMING -----------------------
def normalize_api_url(base):
    base = base.rstrip('/')
    if base.endswith('/chat/completions'):
        return base
    else:
        return f"{base}/chat/completions"

def stream_chat_completion(messages, tools=None):
    """
    Streaming chat completion.
    Yields (event_type, data) where event_type is 'token', 'done', 'error'.
    """
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
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    session = requests.Session()
    url = normalize_api_url(base_url)
    try:
        resp = session.post(url, headers=headers, json=payload, stream=True, timeout=120)
        if resp.status_code != 200:
            yield ('error', f"HTTP {resp.status_code}: {resp.text[:300]}")
            return
        # Proses baris SSE
        collected_content = ""
        tool_calls = []   # akan diisi jika ada
        current_tool_call = None
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta and delta["content"] is not None:
                        token = delta["content"]
                        collected_content += token
                        yield ('token', token)
                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            if "index" in tc:
                                idx = tc["index"]
                                # Ensure tool_calls list large enough
                                while len(tool_calls) <= idx:
                                    tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                if tc.get("id"):
                                    tool_calls[idx]["id"] = tc["id"]
                                if tc.get("function"):
                                    if "name" in tc["function"]:
                                        tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                    if "arguments" in tc["function"]:
                                        tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]
                except json.JSONDecodeError:
                    pass
        # Setelah stream selesai, kirim final message
        final_message = {"role": "assistant", "content": collected_content}
        if tool_calls:
            # Parse arguments string menjadi dict untuk setiap tool call
            for tc in tool_calls:
                try:
                    tc["function"]["arguments"] = json.loads(tc["function"]["arguments"])
                except:
                    pass
            final_message["tool_calls"] = tool_calls
        yield ('done', final_message)
    except requests.exceptions.RequestException as e:
        yield ('error', f"Koneksi gagal: {e}")

def chat_completion_nonstream(messages, tools=None, max_retries=3):
    """Fallback untuk error atau non-streaming (masih dipakai planner)."""
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
                continue
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            return resp.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            if attempt < max_retries - 1:
                console.print(f"[yellow]⚠ Koneksi gagal, coba lagi ({attempt+2}/{max_retries})...[/]")
                time.sleep(2 ** attempt)
            else:
                return {"error": f"Koneksi gagal: {e}"}
    return {"error": "Gagal"}

# ----------------------- TOOLS (fungsi persis sama dengan versi sebelumnya) -----------------------
def check_github():
    try:
        subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        return True
    except:
        return False

def ensure_git_identity():
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
    except:
        pass

def github_create_repo(name, private=False, description=""):
    ensure_git_identity()
    cmd = ["gh", "repo", "create", name, "--push"]
    if private: cmd.append("--private")
    else: cmd.append("--public")
    if description: cmd.extend(["-d", description])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=CWD)
        output = res.stdout.strip() or f"Repo {name} dibuat."
        github_user = os.getenv("GITHUB_USER") or os.environ.get("GITHUB_USER", "")
        if github_user:
            subprocess.run(["git", "remote", "remove", "origin"], capture_output=True, cwd=CWD)
            subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{github_user}/{name}.git"], capture_output=True, cwd=CWD)
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
            console.print(Panel(content, title=f"📋 Log [{project_name}]", border_style="blue"))
    except Exception as e:
        console.print(f"[yellow]Gagal membaca log: {e}[/]")

def change_provider(provider=None, api_key=None, base_url=None, model=None):
    if provider:
        set_key(ENV_FILE, "API_PROVIDER", provider)
    if api_key:
        set_key(ENV_FILE, "API_KEY", api_key)
    if base_url:
        set_key(ENV_FILE, "API_BASE_URL", base_url)
    if model:
        set_key(ENV_FILE, "MODEL", model)
    load_dotenv(ENV_FILE, override=True)
    new_provider = os.getenv("API_PROVIDER", "Tidak diketahui")
    new_model = os.getenv("MODEL", "Tidak diketahui")
    return f"✅ Provider diubah: {new_provider} | Model: {new_model}"

# Tool dasar
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

# ----------------------- TOOL SPECS -----------------------
tools_spec = [
    {"type": "function", "function": {"name": "change_directory", "description": "Pindah direktori.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_directory", "description": "Lihat isi direktori.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}}},
    {"type": "function", "function": {"name": "shell_command", "description": "Jalankan perintah shell.", "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Baca file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Tulis file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Edit file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}}, "required": ["path", "old_str", "new_str"]}}},
    {"type": "function", "function": {"name": "github_create_repo", "description": "Buat repo GitHub.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "private": {"type": "boolean", "default": False}, "description": {"type": "string", "default": ""}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "github_push", "description": "Push ke GitHub.", "parameters": {"type": "object", "properties": {"commit_msg": {"type": "string", "default": "Update from AI Agent"}}}}},
    {"type": "function", "function": {"name": "github_clone", "description": "Clone repo.", "parameters": {"type": "object", "properties": {"repo_url": {"type": "string"}, "target_dir": {"type": "string", "default": ""}}, "required": ["repo_url"]}}},
    {"type": "function", "function": {"name": "auto_run", "description": "Jalankan proyek di tmux.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "project_name": {"type": "string"}}, "required": ["command", "project_name"]}}},
    {"type": "function", "function": {"name": "auto_stop", "description": "Hentikan proyek.", "parameters": {"type": "object", "properties": {"project_name": {"type": "string"}}, "required": ["project_name"]}}},
    {"type": "function", "function": {"name": "change_provider", "description": "Ganti provider API/model.", "parameters": {"type": "object", "properties": {"provider": {"type": "string"}, "api_key": {"type": "string"}, "base_url": {"type": "string"}, "model": {"type": "string"}}}}},
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

MAX_REPEATED_CALLS = 3

def process_tool_calls(messages, tool_calls):
    global tool_call_counter
    new_msgs = []
    for tc in tool_calls:
        func_name = tc["function"]["name"]
        args = tc["function"]["arguments"]  # sudah dict
        args_str = json.dumps(args, sort_keys=True)
        key = f"{func_name}:{args_str}"
        tool_call_counter[key] = tool_call_counter.get(key, 0) + 1
        if tool_call_counter[key] > MAX_REPEATED_CALLS:
            console.print(f"[red]⚠ {func_name} diulang >{MAX_REPEATED_CALLS}x. Diabaikan.[/]")
            result = f"❌ Tindakan '{func_name}' diabaikan karena terlalu sering diulang."
        else:
            console.print(f"[dim]🔧 {func_name}[/]")
            func = tool_map.get(func_name)
            try:
                result = func(**args) if func else "Tool tidak dikenal."
            except Exception as e:
                result = f"ERROR: {e}"
        console.print(Panel(Syntax(str(result), "text", theme="monokai"), title=f"📤 {func_name}"))
        new_msgs.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": func_name,
            "content": str(result)
        })
        if func_name == "auto_run":
            project = args.get("project_name")
            if project:
                threading.Thread(target=monitor_logs, args=(project,), daemon=True).start()
    return new_msgs

# ----------------------- STREAMING DISPLAY -----------------------
def show_streamed_response(user_input, system_prompt, conversation_messages):
    """
    Mengirim user_input, menampilkan streaming token, dan mengembalikan final message + pesan tambahan untuk tool.
    """
    messages = conversation_messages + [{"role": "user", "content": user_input}]
    full_content = ""
    final_message = None

    # Spinner sebelum token pertama
    with console.status("[bold cyan]🧠 Thinking...[/]", spinner="dots") as status:
        first_token = True
        for event, data in stream_chat_completion(messages, tools_spec):
            if event == 'error':
                console.print(f"[red]{data}[/]")
                return None
            if event == 'token':
                if first_token:
                    status.stop()  # hentikan spinner
                    first_token = False
                    # Mulai panel live untuk streaming
                    with Live(Text(""), auto_refresh=False, vertical_overflow="visible") as live:
                        text_display = Text()
                        while True:
                            text_display.append(data)
                            live.update(text_display)
                            # ambil token berikutnya
                            try:
                                next_event, next_data = next(generator)
                            except StopIteration:
                                break
                            if next_event == 'token':
                                data = next_data
                            elif next_event == 'done':
                                final_message = next_data
                                break
                            elif next_event == 'error':
                                console.print(f"[red]{next_data}[/]")
                                return None
                        # pastikan live selesai
                else:
                    # Jika sudah dalam Live (karena kita sudah stop status dan live ada di luar)
                    # kita tidak bisa karena kita keluar dari with Live blok? Perlu restruktur.
                    pass
    # Sebenarnya implementasi streaming lebih rapi dengan generator luar.
    # Kita akan tulis ulang show_streamed_response dengan iterasi sederhana.

    # Karena kerumitan, kita pakai pendekatan: kumpulkan token, lalu tampilkan dengan Live.
    # Atau tampilkan langsung dengan console.print(token, end="") tanpa buffer.
    # Kita lakukan yang sederhana: kumpulkan token sambil tampilkan dengan console.print(token, end="", flush=True) tapi tanpa live panel.
    # Setelah selesai, kita print newline dan return.
    # Namun untuk "thinking" animasi, kita gunakan console.status sampai token pertama.

    # Mari kita implementasikan ulang dengan jelas:
    console.print("[bold cyan]🧠 Thinking...[/]", end="\r")
    collected = ""
    final_msg = None
    first = True
    for ev, dat in stream_chat_completion(messages, tools_spec):
        if ev == 'token':
            if first:
                console.print(" " * 20, end="\r")  # hapus thinking
                first = False
            console.print(dat, end="", highlight=False)
            collected += dat
        elif ev == 'done':
            final_msg = dat
            break
        elif ev == 'error':
            console.print(f"\n[red]{dat}[/]")
            return None
    console.print()  # newline setelah streaming selesai
    if final_msg is None:
        return None
    # Jika ada tool calls, proses di luar
    return final_msg

# ----------------------- MAIN LOOP -----------------------
def run_agent():
    global tool_call_counter, task_list
    load_config()
    model = os.getenv("MODEL", "google/gemini-2.0-flash-001")
    SYSTEM_PROMPT = f"""Kamu AI Developer Agent di Termux. Dir: {CWD}
Tools: baca/tulis/edit file, shell cmd, GitHub, auto_run/stop, change_provider.
Kerjakan tugas dengan efisien, tanpa pengulangan. Gunakan bahasa Indonesia ramah."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    os.system('clear')
    console.print("[dim]Memeriksa update...[/]")
    check_and_update()
    time.sleep(1)
    os.system('clear')

    console.print(Panel.fit(
        f"[bold cyan]● AI Agent Ultimate — Direct & Streaming[/]\n"
        f"Provider: {os.getenv('API_PROVIDER')} | Model: {model} | GitHub: {'✅' if check_github() else '❌'}",
        border_style="bright_blue"))

    if task_list:
        console.print(f"[yellow]📋 {len(task_list)} tugas dari auto-fix.[/]")

    while True:
        tool_call_counter.clear()
        # Auto-fix dari error queue
        try:
            project, err_text = error_queue.get_nowait()
            console.print(Panel(f"[bold red]🐛 Error di {project}![/]\n{err_text[:500]}", title="Auto Monitor"))
            # Masukkan ke task_list agar segera diperbaiki (langsung kirim ke AI)
            task_list.append(f"Perbaiki error di proyek {project}: {err_text[:200]}")
            save_memory()
        except queue.Empty:
            pass

        # Jika ada tugas auto-fix, langsung kerjakan sebagai user input
        if task_list:
            user_input = task_list.pop(0)
            save_memory()
            console.print(f"[bold yellow]🔧 Auto‑fix: {user_input}[/]")
        else:
            try:
                user_input = Prompt.ask("\n[bold green]▸[/]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[red]Keluar.[/]")
                break
            if user_input.lower() in ["exit", "quit", "keluar"]:
                break
            if not user_input.strip():
                continue

        # --- Proses langsung (streaming) ---
        final_msg = show_streamed_response(user_input, SYSTEM_PROMPT, messages)
        if final_msg is None:
            continue

        # Tambahkan user input dan assistant message ke history
        messages.append({"role": "user", "content": user_input})
        # Jika final_msg punya tool_calls, simpan dan proses
        if "tool_calls" in final_msg:
            # Simpan assistant message dengan tool_calls
            messages.append(final_msg)
            # Proses tool calls
            tool_msgs = process_tool_calls(messages, final_msg["tool_calls"])
            messages.extend(tool_msgs)
            # Setelah tool calls, minta AI melanjutkan (auto) tanpa input user
            # Kita loop tool calls sampai selesai (max 5 langkah)
            for _ in range(5):
                # Streaming lagi? Tidak, karena setelah tool calls, kita perlu respon final yang mungkin teks.
                # Kita gunakan non-streaming untuk efisiensi.
                resp = chat_completion_nonstream(messages, tools_spec)
                if "error" in resp:
                    console.print(f"[red]{resp['error']}[/]")
                    break
                msg = resp["choices"][0]["message"]
                messages.append(msg)
                if "tool_calls" in msg:
                    tool_msgs = process_tool_calls(messages, msg["tool_calls"])
                    messages.extend(tool_msgs)
                else:
                    if msg.get("content"):
                        console.print(Panel(Markdown(msg["content"]), title="🤖 AI", border_style="green"))
                    break
        else:
            # Sematkan konten teks
            messages.append(final_msg)
            if final_msg.get("content"):
                console.print(Panel(Markdown(final_msg["content"]), title="🤖 AI", border_style="green"))

        show_log_panel(active_project)

if __name__ == "__main__":
    try:
        run_agent()
    except KeyboardInterrupt:
        console.print("\n[red]Keluar.[/]")
