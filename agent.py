#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tagent – Your AI Agent by Vicienna
+ Session Memory (reset on restart, max 100)
+ Project Memory (persistent)
+ GitHub username remembered
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
from rich.text import Text
from rich.align import Align
import git
from dotenv import load_dotenv, set_key

# ---------- password input ----------
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
PROJECTS_DIR = None
active_project = None
tool_call_counter = {}
DEVELOPER_MODE = False

# ========== SESSION MEMORY (dihapus saat restart) ==========
SESSION_MEMORY_FILE = Path(__file__).parent / "session_memory.json"
MAX_SESSION_MEMORY = 100

session_memory = {
    "github_username": "",
    "current_project": "",
    "last_action": "",
    "conversation": [],  # max 100
    "pending_tasks": [],
    "start_time": time.time()
}

def load_session_memory():
    """Muat memori sesi dari file, lalu hapus filenya (reset)."""
    global session_memory
    if SESSION_MEMORY_FILE.exists():
        try:
            # Baca untuk informasi yang mungkin berguna, tapi kita reset conversation
            old_data = json.loads(SESSION_MEMORY_FILE.read_text())
            # Pertahankan github_username jika ada
            if old_data.get("github_username"):
                session_memory["github_username"] = old_data["github_username"]
        except: pass
        # Hapus file sesi lama
        SESSION_MEMORY_FILE.unlink()
    # Inisialisasi ulang memori sesi
    session_memory["start_time"] = time.time()
    session_memory["conversation"] = []
    session_memory["pending_tasks"] = []
    save_session_memory()

def save_session_memory():
    """Simpan memori sesi ke file."""
    try:
        data = {
            "github_username": session_memory.get("github_username", ""),
            "current_project": active_project or "",
            "last_action": session_memory.get("last_action", ""),
            "conversation": session_memory.get("conversation", [])[-MAX_SESSION_MEMORY:],
            "pending_tasks": session_memory.get("pending_tasks", [])[-MAX_SESSION_MEMORY:],
            "start_time": session_memory.get("start_time", time.time())
        }
        SESSION_MEMORY_FILE.write_text(json.dumps(data, indent=2))
    except: pass

def add_to_session_conversation(role, content):
    """Tambahkan ke percakapan sesi, maks 100."""
    if not content: return
    entry = {
        "role": role,
        "content": str(content)[:1000],  # batasi panjang per entri
        "time": time.time()
    }
    session_memory["conversation"].append(entry)
    if len(session_memory["conversation"]) > MAX_SESSION_MEMORY:
        session_memory["conversation"] = session_memory["conversation"][-MAX_SESSION_MEMORY:]
    save_session_memory()

def get_session_context():
    """Dapatkan konteks sesi untuk dimasukkan ke system prompt."""
    ctx = ""
    if session_memory.get("github_username"):
        ctx += f"GitHub user: {session_memory['github_username']}\n"
    if session_memory.get("last_action"):
        ctx += f"Tindakan terakhir: {session_memory['last_action']}\n"
    if session_memory["conversation"]:
        ctx += "Riwayat sesi ini:\n"
        for entry in session_memory["conversation"][-5:]:  # 5 terakhir saja
            ctx += f"  - {entry['role']}: {entry['content'][:200]}\n"
    return ctx

# ========== PROJECT MEMORY (persistent) ==========
PROJECT_MEMORY_DIR = Path(__file__).parent / "project_memories"
PROJECT_MEMORY_DIR.mkdir(exist_ok=True)

def get_project_memory_file(project_name):
    if not project_name: return None
    return PROJECT_MEMORY_DIR / f"{project_name}.json"

def load_project_memory(project_name):
    file = get_project_memory_file(project_name)
    if file and file.exists():
        try:
            data = json.loads(file.read_text())
            return (
                data.get("tasks", []),
                data.get("history", []),
                data.get("dir_cache", {}),
                data.get("file_cache", {}),
                data.get("last_modified", {})
            )
        except: pass
    return [], [], {}, {}, {}

def save_project_memory(project_name, tasks, history, dir_cache=None, file_cache=None, last_modified=None):
    if not project_name: return
    file = get_project_memory_file(project_name)
    data = {"tasks": tasks, "history": history}
    if dir_cache is not None: data["dir_cache"] = dir_cache
    if file_cache is not None: data["file_cache"] = file_cache
    if last_modified is not None: data["last_modified"] = last_modified
    file.write_text(json.dumps(data, indent=2))

current_tasks = []
current_history = []
current_dir_cache = {}
current_file_cache = {}
current_last_modified = {}

def switch_project(project_name):
    global active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified
    if active_project == project_name: return
    if active_project:
        save_project_memory(active_project, current_tasks, current_history,
                            current_dir_cache, current_file_cache, current_last_modified)
    active_project = project_name
    current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified = load_project_memory(project_name)
    session_memory["current_project"] = project_name
    save_session_memory()
    console.print(f"[dim]📂 Masuk proyek: {project_name}[/]")

# Cache helpers
def cache_dir(path, entries):
    rel = str(Path(path).relative_to(PROJECTS_DIR))
    current_dir_cache[rel] = {"entries": entries, "time": time.time()}
    current_last_modified[rel] = time.time()

def cache_file(path, content):
    rel = str(Path(path).relative_to(PROJECTS_DIR))
    current_file_cache[rel] = {"content": content, "time": time.time()}
    current_last_modified[rel] = time.time()

def get_cached_dir(path):
    rel = str(Path(path).relative_to(PROJECTS_DIR))
    return current_dir_cache.get(rel)

def get_cached_file(path):
    rel = str(Path(path).relative_to(PROJECTS_DIR))
    return current_file_cache.get(rel)

def invalidate_cache_for(path):
    rel = str(Path(path).relative_to(PROJECTS_DIR))
    current_file_cache.pop(rel, None)
    current_dir_cache.pop(rel, None)
    current_last_modified.pop(rel, None)
    parent = str(Path(rel).parent)
    if parent and parent != '.':
        current_dir_cache.pop(parent, None)
        current_last_modified.pop(parent, None)

# ----------------------- AUTO UPDATE -----------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Vicienna/ai-agent/main/agent.py"
SCRIPT_PATH = Path(__file__).resolve()

def check_and_update():
    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=10)
        if resp.status_code != 200: return False
        remote = resp.text
        local = SCRIPT_PATH.read_text()
        if hashlib.md5(remote.encode()).hexdigest() != hashlib.md5(local.encode()).hexdigest():
            console.print("[bold cyan]🔃 Update tersedia! Memperbarui...[/]")
            SCRIPT_PATH.write_text(remote)
            console.print("[bold green]✅ Script diperbarui. Restart...[/]")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return True
    except: return True

# ----------------------- SETUP WIZARD -----------------------
def install_trigger():
    try:
        target_dir = Path("/data/data/com.termux/files/usr/bin")
        if not target_dir.exists(): target_dir = Path.home() / "bin"; target_dir.mkdir(exist_ok=True)
        trigger_path = target_dir / "tagent"
        with open(trigger_path, 'w') as f:
            f.write(f"#!/bin/bash\ncd \"{SCRIPT_PATH.parent}\" && python \"{SCRIPT_PATH}\" \"$@\"\n")
        os.chmod(trigger_path, 0o755)
        console.print("[green]✅ Perintah 'tagent' siap![/]")
    except Exception as e: console.print(f"[yellow]⚠ Gagal membuat trigger: {e}[/]")

def run_setup():
    global PROJECTS_DIR
    console.print(Panel.fit("[bold cyan]🛠️  Setup Wizard – Tagent[/]", border_style="bright_blue"))
    providers = {
        "1":{"name":"OpenAI","base":"https://api.openai.com/v1","key_link":"https://platform.openai.com/api-keys"},
        "2":{"name":"OpenRouter","base":"https://openrouter.ai/api/v1","key_link":"https://openrouter.ai/keys"},
        "3":{"name":"Groq","base":"https://api.groq.com/openai/v1","key_link":"https://console.groq.com/keys"},
        "4":{"name":"Ollama (Local)","base":"http://localhost:11434/v1","key_link":""},
        "5":{"name":"Custom","base":"","key_link":""}
    }
    for k,v in providers.items(): console.print(f"  {k}. {v['name']}")
    choice = Prompt.ask("Pilih provider", choices=list(providers.keys()), default="2")
    provider = providers[choice]
    api_key = "" if provider["name"]=="Ollama (Local)" else password_prompt(f"API Key {provider['name']}: ")
    set_key(ENV_FILE, "API_KEY", api_key)
    set_key(ENV_FILE, "API_PROVIDER", provider["name"])
    if choice=="5": set_key(ENV_FILE, "API_BASE_URL", Prompt.ask("Base URL").strip().rstrip('/'))
    else: set_key(ENV_FILE, "API_BASE_URL", provider["base"])
    if choice=="1": model = Prompt.ask("Model", default="gpt-4o")
    elif choice=="2":
        console.print("1. google/gemini-2.0-flash-001 (gratis)\n2. openai/gpt-4o\n3. anthropic/claude-3.5-sonnet\n4. Custom")
        mc = Prompt.ask("Pilih", choices=["1","2","3","4"], default="1")
        model = {"1":"google/gemini-2.0-flash-001","2":"openai/gpt-4o","3":"anthropic/claude-3.5-sonnet"}.get(mc) or Prompt.ask("ID model")
    elif choice=="3":
        console.print("1. llama-3.1-70b-versatile\n2. mixtral-8x7b-32768\n3. gemma2-9b-it\n4. Custom")
        mc = Prompt.ask("Pilih", choices=["1","2","3","4"], default="1")
        model = {"1":"llama-3.1-70b-versatile","2":"mixtral-8x7b-32768","3":"gemma2-9b-it"}.get(mc) or Prompt.ask("ID model")
    elif choice=="4": model = Prompt.ask("Nama model", default="nemotron-3-super:cloud")
    else: model = Prompt.ask("ID model")
    set_key(ENV_FILE, "MODEL", model)
    
    # GitHub token + username
    gh_token = password_prompt("\n🔐 GitHub Token (opsional): ")
    if gh_token.strip():
        try:
            subprocess.run(["gh","auth","login","--with-token"], input=gh_token, text=True, capture_output=True, check=True)
            user_res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if user_res.returncode==0:
                data = json.loads(user_res.stdout)
                set_key(ENV_FILE, "GITHUB_USER", data["login"]); os.environ["GITHUB_USER"] = data["login"]
                session_memory["github_username"] = data["login"]
                subprocess.run(["git","config","--global","user.name", data.get("name",data["login"])])
                subprocess.run(["git","config","--global","user.email", data.get("email","")])
                console.print(f"[green]✓ Login sebagai {data['login']}[/]")
        except: pass
    else:
        try:
            subprocess.run(["gh","auth","status"], check=True, capture_output=True)
            # Ambil username dari gh yang sudah login
            user_res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if user_res.returncode==0:
                data = json.loads(user_res.stdout)
                session_memory["github_username"] = data["login"]
                set_key(ENV_FILE, "GITHUB_USER", data["login"])
        except:
            console.print("[yellow]⚠ gh CLI belum login[/]")
    
    default_projects = str(Path.home() / "proyek")
    projects_dir = Prompt.ask("Folder proyek", default=default_projects)
    set_key(ENV_FILE, "PROJECTS_DIR", projects_dir)
    Path(projects_dir).mkdir(parents=True, exist_ok=True)
    if Prompt.ask("Buat perintah global 'tagent'?", choices=["y","n"], default="y")=="y": install_trigger()
    save_session_memory()
    console.print("[green]✅ Setup selesai![/]")

def load_config():
    global DEVELOPER_MODE, PROJECTS_DIR, CWD, active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified
    if ENV_FILE.exists(): load_dotenv(ENV_FILE)
    if not os.getenv("API_KEY") and not os.getenv("API_PROVIDER","").startswith("Ollama"):
        run_setup()
        load_dotenv(ENV_FILE, override=True)
    PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", str(Path.home() / "proyek"))).expanduser().resolve()
    if not PROJECTS_DIR.exists(): PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(PROJECTS_DIR)
    CWD = PROJECTS_DIR
    
    # Load/reset session memory
    load_session_memory()
    
    # Ambil GitHub username
    gh_user = os.getenv("GITHUB_USER", "")
    if gh_user and not session_memory.get("github_username"):
        session_memory["github_username"] = gh_user
    if not gh_user and session_memory.get("github_username"):
        set_key(ENV_FILE, "GITHUB_USER", session_memory["github_username"])
        os.environ["GITHUB_USER"] = session_memory["github_username"]
    
    # Verifikasi gh CLI
    if not os.getenv("GITHUB_USER"):
        try:
            res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if res.returncode==0:
                login = json.loads(res.stdout).get("login")
                if login: 
                    set_key(ENV_FILE, "GITHUB_USER", login)
                    os.environ["GITHUB_USER"] = login
                    session_memory["github_username"] = login
        except: pass
    
    DEVELOPER_MODE = os.getenv("GITHUB_USER","").strip().lower()=="vicienna"
    save_session_memory()
    switch_project(PROJECTS_DIR.name)

# ---------- API ----------
def normalize_api_url(base):
    base = base.rstrip('/')
    return base if base.endswith('/chat/completions') else f"{base}/chat/completions"

def stream_chat_completion(messages, tools=None):
    api_key = os.getenv("API_KEY"); base_url = os.getenv("API_BASE_URL"); provider = os.getenv("API_PROVIDER",""); model = os.getenv("MODEL")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if "OpenRouter" in provider: headers["HTTP-Referer"] = "http://localhost"; headers["X-Title"] = "Tagent"
    payload = {"model":model,"messages":messages,"temperature":0.2,"stream":True}
    if tools: payload["tools"] = tools; payload["tool_choice"] = "auto"
    session = requests.Session()
    url = normalize_api_url(base_url)
    try:
        resp = session.post(url, headers=headers, json=payload, stream=True, timeout=180)
        if resp.status_code != 200: yield ('error', f"HTTP {resp.status_code}: {resp.text[:300]}"); return
        content = ""; thinking = ""; tool_calls = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line: continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]": break
                try:
                    obj = json.loads(data_str)
                    delta = obj.get("choices",[{}])[0].get("delta",{})
                    reasoning = delta.get("reasoning") or delta.get("thinking") or delta.get("reasoning_content")
                    if reasoning: thinking += reasoning; yield ('thinking', reasoning)
                    if "content" in delta and delta["content"] is not None: content += delta["content"]; yield ('content', delta["content"])
                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index",0)
                            while len(tool_calls) <= idx: tool_calls.append({"id":"","type":"function","function":{"name":"","arguments":""}})
                            if tc.get("id"): tool_calls[idx]["id"] = tc["id"]
                            if tc.get("function"):
                                if "name" in tc["function"]: tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                if "arguments" in tc["function"]: tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]
                except json.JSONDecodeError: pass
        final_msg = {"role":"assistant","content":content}
        if thinking: final_msg["thinking"] = thinking
        if tool_calls: final_msg["tool_calls"] = tool_calls
        yield ('done', final_msg)
    except requests.exceptions.RequestException as e: yield ('error', f"Koneksi gagal: {e}")

def chat_completion_nonstream(messages, tools=None, max_retries=3):
    api_key = os.getenv("API_KEY"); base_url = os.getenv("API_BASE_URL"); provider = os.getenv("API_PROVIDER",""); model = os.getenv("MODEL")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if "OpenRouter" in provider: headers["HTTP-Referer"] = "http://localhost"; headers["X-Title"] = "Tagent"
    payload = {"model":model,"messages":messages,"temperature":0.2}
    if tools: payload["tools"] = tools; payload["tool_choice"] = "auto"
    session = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=1, status_forcelist=[429,502,503,504], allowed_methods=["POST"], respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retries)); session.mount("http://", HTTPAdapter(max_retries=retries))
    url = normalize_api_url(base_url)
    for attempt in range(max_retries):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After",10))
                console.print(f"[yellow]⏳ Rate limit 429, tunggu {wait}s[/]"); time.sleep(wait); continue
            if resp.status_code != 200: return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            return resp.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            if attempt < max_retries-1: console.print(f"[yellow]⚠ Koneksi gagal, coba {attempt+2}/{max_retries}[/]"); time.sleep(2**attempt)
            else: return {"error": f"Koneksi gagal: {e}"}
    return {"error":"Gagal"}

# ---------- TOOLS ----------
def check_github():
    try: subprocess.run(["gh","auth","status"], check=True, capture_output=True); return True
    except: return False

def ensure_git_identity():
    try:
        repo = git.Repo(CWD); r = repo.config_reader()
        if not r.has_option("user","email") or not r.has_option("user","name"):
            res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if res.returncode == 0:
                d = json.loads(res.stdout); email = d.get("email","user@example.com"); name = d.get("name", d.get("login","User"))
            else: email = "user@example.com"; name = "AI Agent User"
            w = repo.config_writer(); w.set_value("user","email",email); w.set_value("user","name",name); w.release()
    except: pass

def ensure_git_remote(repo_name):
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=CWD)
        if result.returncode != 0:
            user = os.getenv("GITHUB_USER", "") or session_memory.get("github_username", "")
            if user:
                subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{user}/{repo_name}.git"], capture_output=True, cwd=CWD)
                return True
            return False
        return True
    except: return False

def github_create_repo(name, private=False, description=""):
    ensure_git_identity()
    cmd = ["gh","repo","create",name,"--push"] + (["--private"] if private else ["--public"])
    if description: cmd.extend(["-d",description])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=CWD)
        out = res.stdout.strip() or f"Repo {name} dibuat."
        user = os.getenv("GITHUB_USER","") or session_memory.get("github_username", "")
        if user: 
            subprocess.run(["git","remote","remove","origin"], capture_output=True, cwd=CWD)
            subprocess.run(["git","remote","add","origin", f"https://github.com/{user}/{name}.git"], capture_output=True, cwd=CWD)
        session_memory["last_action"] = f"Buat repo GitHub: {name}"
        save_session_memory()
        return out
    except Exception as e: return f"ERROR: {e}"

def github_push(commit_msg="Update from Tagent"):
    try:
        ensure_git_identity()
        if not (CWD / ".git").exists():
            return "ERROR: Direktori ini bukan repository Git. Gunakan github_create_repo dulu atau git init."
        
        # Cek submodule
        status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=CWD)
        status_lines = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
        
        submodule_paths = []
        for line in status_lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    path = parts[-1].strip()
                    full_path = CWD / path
                    if full_path.is_dir() and (full_path / ".git").exists():
                        submodule_paths.append(path)
        
        if submodule_paths:
            warning = "⚠️ Terdeteksi folder yang merupakan repo git sendiri (submodule):\n"
            for sp in submodule_paths:
                warning += f"  - {sp}\n"
            warning += "Tips: masuk ke folder tersebut dengan change_directory, lalu push dari sana.\n"
            warning += "Atau hapus .git di dalamnya: rm -rf <folder>/.git"
            return warning
        
        gitignore_path = CWD / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("node_modules/\n*.log\n.env\n__pycache__/\n")
        
        repo = git.Repo(CWD)
        if not repo.is_dirty(untracked_files=True):
            return "Tidak ada perubahan."
        
        repo.git.add(A=True)
        repo.index.commit(commit_msg)
        
        repo_name = CWD.name
        ensure_git_remote(repo_name)
        
        branch_result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=CWD)
        branch = branch_result.stdout.strip() or "main"
        
        push_result = subprocess.run(["git", "push", "-u", "origin", branch], capture_output=True, text=True, cwd=CWD)
        if push_result.returncode != 0:
            error_msg = push_result.stderr.strip()
            if "master" in branch:
                subprocess.run(["git", "branch", "-M", "main"], capture_output=True, cwd=CWD)
                push_result2 = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True, cwd=CWD)
                if push_result2.returncode == 0:
                    return f"✅ Pushed: {commit_msg} (branch: main)"
            return f"ERROR push: {error_msg[:200]}"
        
        session_memory["last_action"] = f"Push: {commit_msg}"
        save_session_memory()
        return f"✅ Pushed: {commit_msg} (branch: {branch})"
    except Exception as e:
        return f"ERROR: {str(e)[:200]}"

def github_clone(repo_url, target_dir=""):
    cmd = ["gh","repo","clone",repo_url] + ([target_dir] if target_dir else [])
    try: 
        subprocess.run(cmd, check=True, capture_output=True, cwd=CWD)
        if target_dir:
            new_path = CWD / target_dir
            if new_path.exists():
                switch_project(target_dir)
        session_memory["last_action"] = f"Clone: {repo_url}"
        save_session_memory()
        return f"Repo {repo_url} di-clone."
    except Exception as e: return f"ERROR: {e}"

LOG_DIR = CWD / "logs"; LOG_DIR.mkdir(exist_ok=True)

def auto_run(command, project_name):
    global active_project
    subprocess.run(["tmux","kill-session","-t",project_name], capture_output=True)
    log = LOG_DIR / f"{project_name}.log"
    subprocess.run(["tmux","new-session","-d","-s",project_name, f"bash -c '{command} 2>&1 | tee {log}'"])
    active_project = project_name
    session_memory["last_action"] = f"Run: {project_name}"
    save_session_memory()
    return f"Proyek {project_name} dijalankan. Log: {log}"

def auto_stop(project_name):
    global active_project
    subprocess.run(["tmux","kill-session","-t",project_name], capture_output=True)
    return f"Sesi {project_name} dihentikan."

error_queue = queue.Queue()

def monitor_logs(project_name):
    log = LOG_DIR / f"{project_name}.log"
    if not log.exists(): return
    last = 0
    while True:
        time.sleep(2)
        if not log.exists(): continue
        try:
            cur = log.stat().st_size
            if cur > last:
                with open(log,'r') as f: f.seek(last); new = f.read()
                last = cur
                if any(k in new for k in ["Traceback","Error","error","FATAL"]): error_queue.put((project_name, new))
        except: pass

def show_log_panel(project_name, lines=10):
    if not project_name: return
    log = LOG_DIR / f"{project_name}.log"
    if not log.exists(): return
    try:
        lines_data = log.read_text().splitlines()[-lines:]
        if lines_data: console.print(Panel("\n".join(lines_data), title=f"📋 Log [{project_name}]", border_style="blue"))
    except: pass

def change_provider(provider=None, api_key=None, base_url=None, model=None):
    if provider: set_key(ENV_FILE, "API_PROVIDER", provider)
    if api_key: set_key(ENV_FILE, "API_KEY", api_key)
    if base_url: set_key(ENV_FILE, "API_BASE_URL", base_url)
    if model: set_key(ENV_FILE, "MODEL", model)
    load_dotenv(ENV_FILE, override=True)
    return f"✅ Provider diubah: {os.getenv('API_PROVIDER')} | Model: {os.getenv('MODEL')}"

def change_directory(path):
    global CWD
    try:
        target = (CWD / path).resolve()
        if not str(target).startswith(str(PROJECTS_DIR)):
            return f"ERROR: Tidak bisa keluar dari folder proyek ({PROJECTS_DIR})."
        if not target.is_dir():
            return f"ERROR: {path} bukan direktori."
        os.chdir(target); CWD = target
        switch_project(target.name)
        session_memory["last_action"] = f"Pindah ke {target.name}"
        save_session_memory()
        return f"Pindah ke {CWD}"
    except Exception as e: return f"ERROR: {e}"

def list_directory(path="."):
    target = (CWD / path).resolve()
    if not str(target).startswith(str(PROJECTS_DIR)):
        return f"ERROR: Tidak bisa keluar dari folder proyek."
    if not target.is_dir(): return f"ERROR: {path} bukan direktori."
    cached = get_cached_dir(target)
    if cached: return cached["entries"]
    try: items = os.listdir(target)
    except: return f"ERROR: tidak bisa membaca {path}"
    dirs = [d for d in items if (target/d).is_dir()]
    files = [f for f in items if (target/f).is_file()]
    res = ""
    if dirs: res += "[DIR] " + ", ".join(dirs) + "\n"
    if files: res += "[FILE] " + ", ".join(files)
    entries = res.strip() or "Kosong"
    cache_dir(target, entries)
    save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
    return entries

def shell_command(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=CWD,
                             executable="/data/data/com.termux/files/usr/bin/bash" if "ANDROID_ROOT" in os.environ else None)
        out = (res.stdout+res.stderr).strip()
        if not out: return "(ok)"
        if "command not found" in out: return f"ERROR: Perintah tidak ditemukan. Coba busybox {cmd}"
        invalidate_cache_for(CWD)
        save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
        return out
    except subprocess.TimeoutExpired: return "ERROR: Timeout"
    except Exception as e: return f"ERROR: {e}"

def read_file(path):
    full = (CWD / path).resolve()
    if not str(full).startswith(str(PROJECTS_DIR)):
        return f"ERROR: File di luar folder proyek."
    if not full.is_file(): return f"ERROR: {path} tidak ditemukan."
    cached = get_cached_file(full)
    if cached: return cached["content"]
    try: content = full.read_text()
    except: return f"ERROR: tidak bisa membaca {path}"
    cache_file(full, content)
    save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
    return content

def write_file(path, content):
    full = (CWD / path).resolve()
    if not str(full).startswith(str(PROJECTS_DIR)):
        return f"ERROR: Tidak bisa menulis di luar folder proyek."
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    cache_file(full, content)
    invalidate_cache_for(full.parent)
    save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
    return f"✅ {path} ditulis ({len(content)} karakter)."

def edit_file(path, old_str, new_str, **kwargs):
    full = (CWD / path).resolve()
    if not str(full).startswith(str(PROJECTS_DIR)):
        return f"ERROR: File di luar folder proyek."
    content = read_file(path)
    search = old_str
    if search not in content:
        for key in ["old_string","old","find","search"]:
            if key in kwargs and kwargs[key] in content:
                search = kwargs[key]
                break
    if search not in content: return "ERROR: string tidak ditemukan."
    new_content = content.replace(search, new_str, 1)
    full.write_text(new_content)
    cache_file(full, new_content)
    invalidate_cache_for(full.parent)
    save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
    return f"✅ {path} diedit."

tools_spec = [
    {"type":"function","function":{"name":"change_directory","description":"Pindah ke folder proyek spesifik.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_directory","description":"Lihat isi direktori.","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}}}}},
    {"type":"function","function":{"name":"shell_command","description":"Jalankan perintah shell.","parameters":{"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}},
    {"type":"function","function":{"name":"read_file","description":"Baca file.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Tulis file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"edit_file","description":"Edit file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"github_create_repo","description":"Buat repo GitHub di folder proyek saat ini.","parameters":{"type":"object","properties":{"name":{"type":"string"},"private":{"type":"boolean","default":False},"description":{"type":"string","default":""}},"required":["name"]}}},
    {"type":"function","function":{"name":"github_push","description":"Commit dan push perubahan ke GitHub. Pastikan sudah berada di folder proyek yang benar.","parameters":{"type":"object","properties":{"commit_msg":{"type":"string","default":"Update from Tagent"}}}}},
    {"type":"function","function":{"name":"github_clone","description":"Clone repo ke folder proyek.","parameters":{"type":"object","properties":{"repo_url":{"type":"string"},"target_dir":{"type":"string","default":""}},"required":["repo_url"]}}},
    {"type":"function","function":{"name":"auto_run","description":"Jalankan proyek di tmux.","parameters":{"type":"object","properties":{"command":{"type":"string"},"project_name":{"type":"string"}},"required":["command","project_name"]}}},
    {"type":"function","function":{"name":"auto_stop","description":"Hentikan proyek.","parameters":{"type":"object","properties":{"project_name":{"type":"string"}},"required":["project_name"]}}},
    {"type":"function","function":{"name":"change_provider","description":"Ganti provider API/model.","parameters":{"type":"object","properties":{"provider":{"type":"string"},"api_key":{"type":"string"},"base_url":{"type":"string"},"model":{"type":"string"}}}}},
]

tool_map = {t["function"]["name"]: eval(t["function"]["name"]) for t in tools_spec}

MAX_REPEATED = 3

def execute_tool_chain(messages, initial_tool_calls):
    global tool_call_counter
    with console.status("[bold cyan]🔧 Memproses...[/]", spinner="dots") as status:
        pending = list(initial_tool_calls)
        while pending:
            tc = pending.pop(0)
            func_name = tc["function"]["name"]
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                try: args = json.loads(args)
                except: pass
            key = f"{func_name}:{json.dumps(args, sort_keys=True)}"
            tool_call_counter[key] = tool_call_counter.get(key,0)+1
            if tool_call_counter[key] > MAX_REPEATED:
                result = f"❌ Tindakan '{func_name}' diabaikan."
            else:
                status.update(f"[bold yellow]⚙️  {func_name}...[/]")
                func = tool_map.get(func_name)
                try: result = func(**args) if func else "Tool tidak dikenal."
                except Exception as e: result = f"ERROR: {e}"
            console.print(f"[dim]🔧 {func_name}[/]")
            console.print(Panel(Syntax(str(result),"text",theme="monokai"), title=f"📤 {func_name}"))
            messages.append({"role":"tool","tool_call_id":tc.get("id","manual"),"name":func_name,"content":str(result)})
            if func_name == "auto_run":
                project = args.get("project_name")
                if project: threading.Thread(target=monitor_logs, args=(project,), daemon=True).start()
        for _ in range(5):
            status.update("[bold cyan]🤖 Meminta respons AI...[/]")
            resp = chat_completion_nonstream(messages, tools_spec)
            if "error" in resp:
                console.print(f"[red]{resp['error']}[/]")
                return messages, None
            msg = resp["choices"][0]["message"]
            messages.append(msg)
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    pending.append(tc)
                while pending:
                    tc = pending.pop(0)
                    func_name = tc["function"]["name"]
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: pass
                    key = f"{func_name}:{json.dumps(args, sort_keys=True)}"
                    tool_call_counter[key] = tool_call_counter.get(key,0)+1
                    if tool_call_counter[key] > MAX_REPEATED:
                        result = f"❌ Tindakan '{func_name}' diabaikan."
                    else:
                        status.update(f"[bold yellow]⚙️  {func_name}...[/]")
                        func = tool_map.get(func_name)
                        try: result = func(**args) if func else "Tool tidak dikenal."
                        except Exception as e: result = f"ERROR: {e}"
                    console.print(f"[dim]🔧 {func_name}[/]")
                    console.print(Panel(Syntax(str(result),"text",theme="monokai"), title=f"📤 {func_name}"))
                    messages.append({"role":"tool","tool_call_id":tc.get("id","manual"),"name":func_name,"content":str(result)})
            else:
                return messages, msg.get("content") or "✅ Semua tugas selesai."
    return messages, "⚠️ Terjadi kendala, tetapi beberapa tugas mungkin sudah selesai."

# ---------- DISPLAY STREAMING + TIMER ----------
def display_stream(messages):
    start = time.time(); thinking = ""; content = ""; has_thinking = False; final_msg = None; first_content = None
    def render():
        elapsed = time.time()-start; timer = f"⏱ {elapsed:.1f}s"
        panel_text = Text()
        if has_thinking:
            panel_text.append("🧠 Thinking Process (", style="bold cyan")
            panel_text.append(timer, style="bold magenta"); panel_text.append(")\n", style="bold cyan")
            panel_text.append("─"*50+"\n", style="dim"); panel_text.append(thinking, style="dim cyan"); panel_text.append("\n"+"─"*50, style="dim")
        else: panel_text.append("🧠 Thinking... ", style="bold yellow"); panel_text.append(timer, style="bold magenta")
        panel_text.append("\n"); panel_text.append("(Ctrl+C untuk batal)", style="red")
        return Panel(panel_text, border_style="blue", title="Streaming")
    try:
        with Live(render(), refresh_per_second=8, vertical_overflow="visible") as live:
            for ev, data in stream_chat_completion(messages, tools_spec):
                if ev == 'thinking': has_thinking = True; thinking += data; live.update(render())
                elif ev == 'content':
                    if not first_content: first_content = time.time()
                    content += data; live.update(render())
                elif ev == 'error': console.print(f"[red]{data}[/]"); return None, ""
                elif ev == 'done': final_msg = data; break
    except KeyboardInterrupt: console.print("\n[red]⚠ Dibatalkan.[/]"); return None, ""
    end = time.time(); think_dur = (first_content or end)-start; total_dur = end-start
    if has_thinking: console.print(f"[bold magenta]⏱ Thinking selesai dalam {think_dur:.1f}s (total {total_dur:.1f}s)[/]")
    else: console.print(f"[bold magenta]⏱ Response time: {total_dur:.1f}s[/]")
    return final_msg, content

# ---------- MAIN ----------
def run_agent():
    global tool_call_counter, active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified, DEVELOPER_MODE
    load_config()
    model = os.getenv("MODEL","google/gemini-2.0-flash-001")
    
    # Dapatkan konteks sesi
    session_context = get_session_context()
    
    SYSTEM_PROMPT = f"""Kamu Tagent, AI Developer Agent di Termux.
Folder proyek: {PROJECTS_DIR} (semua pekerjaan di sini)
Proyek saat ini: {active_project or 'none'}
GitHub user: {session_memory.get('github_username', 'unknown')}

{ 'Riwayat sesi:' + chr(10) + session_context if session_context else '' }

Tools: baca/tulis/edit file, shell cmd, GitHub, auto_run/stop, change_provider.

PENTING:
- Sebelum push ke GitHub, PASTIKAN kamu sudah masuk ke folder proyek yang benar (gunakan change_directory ke folder proyeknya).
- Jangan bekerja atau push dari folder proyek utama ({PROJECTS_DIR}), selalu masuk ke folder proyek spesifik.
- Jika github_push gagal, cek apakah folder tersebut adalah submodule/repo git sendiri. Jika ya, masuk ke folder itu dulu baru push.
- Kamu memiliki memory untuk setiap proyek. Jangan ulangi list_directory/read_file jika data sudah ada.
- Gunakan username GitHub ({session_memory.get('github_username', 'unknown')}) untuk semua operasi GitHub.
- Setelah semua tugas selesai, berikan ringkasan singkat.
Gunakan bahasa Indonesia ramah."""

    messages = [{"role":"system","content":SYSTEM_PROMPT}]

    os.system('clear')
    console.print("[dim]Memeriksa update...[/]"); check_and_update(); time.sleep(1); os.system('clear')

    banner_text = Text()
    banner_text.append("🤖  T A G E N T  🤖\n\n", style="bold white on blue")
    banner_text.append("Creator : Vicienna\n", style="cyan")
    banner_text.append("Source  : github.com/Vicienna/ai-agent\n", style="cyan")
    banner_text.append("IG: ceena.dev  GitHub: Vicienna\n", style="cyan")
    banner_text.append("Discord: hallo.dev\n\n", style="cyan")
    if session_memory.get("github_username"):
        banner_text.append(f"Logged in as: {session_memory['github_username']}", style="green")
    console.print(Panel(Align.center(banner_text), border_style="bright_cyan", padding=(1,2), title="Welcome", title_align="left"))

    gh_ok = "✅" if check_github() else "❌"
    dev_ok = "✅" if DEVELOPER_MODE else "❌"
    console.print(Panel(f"Provider: {os.getenv('API_PROVIDER')} | Model: {model} | GitHub: {gh_ok} | Developer: {dev_ok} | Folder: {PROJECTS_DIR} | Proyek: {active_project}", border_style="blue"))

    while True:
        tool_call_counter.clear()
        try:
            proj, err = error_queue.get_nowait()
            console.print(Panel(f"[red]🐛 Error di {proj}![/]\n{err[:500]}", title="Auto Monitor"))
            session_memory["pending_tasks"].append(f"Perbaiki error di {proj}: {err[:200]}")
            current_tasks.append(f"Perbaiki error di {proj}: {err[:200]}")
            save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
            save_session_memory()
        except queue.Empty: pass

        if session_memory.get("pending_tasks"):
            user_input = session_memory["pending_tasks"].pop(0)
            current_tasks.pop(0) if current_tasks else None
            save_session_memory()
            save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
            console.print(f"[yellow]🔧 Auto‑fix: {user_input}[/]")
        elif current_tasks:
            user_input = current_tasks.pop(0)
            save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)
            console.print(f"[yellow]🔧 Tugas proyek: {user_input}[/]")
        else:
            try: user_input = Prompt.ask("\n[bold green]▸[/]")
            except (KeyboardInterrupt, EOFError): console.print("\n[red]Bye![/]"); break
            if user_input.lower() in ["exit","quit","keluar"]: break
            if not user_input.strip(): continue

        # Simpan ke sesi
        add_to_session_conversation("user", user_input)

        # Bangun konteks
        use_memory = active_project and any(kw in user_input.lower() for kw in [active_project.lower(), "proyek", "lanjut", "ubah", "edit", "file", "kode", "push", "commit", "jalankan"])

        if use_memory:
            base_messages = [{"role":"system","content":SYSTEM_PROMPT}]
            for h in current_history[-20:]: base_messages.append(h)
            base_messages.append({"role":"user","content":user_input})
        else:
            base_messages = [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":user_input}]

        final_msg, content = None, ""
        try: final_msg, content = display_stream(base_messages)
        except Exception as e: console.print(f"[red]Stream error: {e}[/]"); continue
        if final_msg is None: continue

        # Simpan ke sesi
        add_to_session_conversation("assistant", content or "Tool calls executed")

        if use_memory:
            current_history.append({"role":"user","content":user_input})
            current_history.append(final_msg)
            if len(current_history) > 40: current_history = current_history[-40:]
            save_project_memory(active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified)

        if "tool_calls" in final_msg:
            messages = base_messages + [final_msg]
            try:
                messages, final_content = execute_tool_chain(messages, final_msg["tool_calls"])
                if final_content:
                    console.print(Panel(Markdown(final_content), title="🤖 Tagent", border_style="green"))
                    add_to_session_conversation("assistant", final_content)
                else:
                    console.print("[dim]✅ Semua tugas selesai.[/]")
            except KeyboardInterrupt:
                console.print("\n[red]⚠ Dibatalkan.[/]"); continue
        else:
            if content: 
                console.print(Panel(Markdown(content), title="🤖 Tagent", border_style="green"))
            else: 
                console.print("[dim]✅ Selesai.[/]")

        show_log_panel(active_project)
        save_session_memory()

if __name__ == "__main__":
    try: run_agent()
    except KeyboardInterrupt: console.print("\n[red]Tagent dimatikan.[/]")
