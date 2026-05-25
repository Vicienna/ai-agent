#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tagent v2.1 – Your AI Agent by Vicienna
+ Fixed GitHub Operations (Submodule detection, Remote handling, Branch normalization)
+ Upgraded Memory System (JSON locking, Corruption recovery, Auto-save)
+ Enhanced Security (Path traversal protection)
+ Better Error Handling & Logging
"""

import os, sys, subprocess, json, time, hashlib, queue, threading, fcntl
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

# ---------- Configuration & Globals ----------
console = Console()
ENV_FILE = Path(__file__).parent / ".env"
CWD = Path.cwd()
PROJECTS_DIR = None
active_project = None
tool_call_counter = {}
DEVELOPER_MODE = False

# ---------- Password Input Helper ----------
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
            elif ch == '\x7f': # Backspace
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

# ========== SESSION MEMORY (Volatile) ==========
MAX_SESSION_MESSAGES = 100
session_messages = [] 
session_github_user = ""
session_active_project = ""

def add_session_message(role, content):
    global session_messages
    session_messages.append({
        "role": role,
        "content": str(content)[:2000],
        "time": time.time()
    })
    if len(session_messages) > MAX_SESSION_MESSAGES:
        session_messages = session_messages[-MAX_SESSION_MESSAGES:]

def get_session_context():
    if not session_messages:
        return ""
    last_msgs = session_messages[-10:] # Ambil 10 terakhir saja untuk efisiensi
    context = "🗂 Context Sesi Terbaru:\n"
    for m in last_msgs:
        role_icon = "👤" if m["role"] == "user" else "🤖" if m["role"] == "assistant" else "🔧"
        content_preview = str(m["content"]).replace('\n', ' ')[:150]
        context += f"{role_icon} {content_preview}\n"
    return context

# ========== PROJECT MEMORY (Persistent with Locking) ==========
PROJECT_MEMORY_DIR = Path(__file__).parent / "project_memories"
PROJECT_MEMORY_DIR.mkdir(exist_ok=True)

def get_project_memory_file(project_name):
    if not project_name: return None
    safe_name = "".join(c for c in project_name if c.isalnum() or c in "._- ")
    safe_name = safe_name.replace(" ", "_")
    return PROJECT_MEMORY_DIR / f"{safe_name}.json"

def load_project_memory(project_name):
    file = get_project_memory_file(project_name)
    if file and file.exists():
        try:
            # Basic lock read
            with open(file, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
            
            return (
                data.get("tasks", []),
                data.get("history", []),
                data.get("dir_cache", {}),
                data.get("file_cache", {}),
                data.get("last_modified", {}),
                data.get("github_remote", "")
            )
        except Exception as e:
            console.print(f"[yellow]⚠️ Warning: Memory corrupt for {project_name}, resetting.[/]")
            # Backup corrupt file
            try: file.rename(file.with_suffix(".json.bak"))
            except: pass
    return [], [], {}, {}, {}, ""

def save_project_memory(project_name, tasks=None, history=None, dir_cache=None, file_cache=None, last_modified=None, github_remote=None):
    if not project_name: return
    file = get_project_memory_file(project_name)
    
    # Load existing first to merge
    existing = {}
    if file.exists():
        try:
            with open(file, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                existing = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
        except: existing = {}

    # Update fields
    if tasks is not None: existing["tasks"] = tasks
    if history is not None: existing["history"] = history
    if dir_cache is not None: existing["dir_cache"] = dir_cache
    if file_cache is not None: existing["file_cache"] = file_cache
    if last_modified is not None: existing["last_modified"] = last_modified
    if github_remote is not None: existing["github_remote"] = github_remote

    # Write with lock
    try:
        with open(file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(existing, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        console.print(f"[red]❌ Error saving memory: {e}[/]")

# Global State for Current Project
current_tasks = []
current_history = []
current_dir_cache = {}
current_file_cache = {}
current_last_modified = {}
current_github_remote = ""

def switch_project(project_name):
    global active_project, current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified, current_github_remote, session_active_project
    
    # Save previous project state before switching
    if active_project and active_project != project_name:
        save_project_memory(active_project, current_tasks, current_history,
                            current_dir_cache, current_file_cache, current_last_modified, current_github_remote)
    
    active_project = project_name
    session_active_project = project_name
    
    # Load new project state
    current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified, current_github_remote = load_project_memory(project_name)
    
    add_session_message("system", f"📂 Switched to project: {project_name}")
    console.print(f"[dim]📂 Active Project: {project_name}[/]")

def needs_memory(user_input, project_name):
    if not project_name: return False
    keywords = [project_name.lower(), "proyek", "lanjut", "ubah", "edit", "file", "kode", "push", "commit", "jalankan", "run"]
    return any(kw in user_input.lower() for kw in keywords)

def cache_dir(path, entries):
    try:
        rel = str(Path(path).relative_to(PROJECTS_DIR))
        current_dir_cache[rel] = {"entries": entries, "time": time.time()}
    except ValueError: pass # Path not relative to PROJECTS_DIR

def cache_file(path, content):
    try:
        rel = str(Path(path).relative_to(PROJECTS_DIR))
        current_file_cache[rel] = {"content": content, "time": time.time()}
        current_last_modified[rel] = time.time()
    except ValueError: pass

def get_cached_dir(path):
    try:
        rel = str(Path(path).relative_to(PROJECTS_DIR))
        return current_dir_cache.get(rel)
    except ValueError: return None

def get_cached_file(path):
    try:
        rel = str(Path(path).relative_to(PROJECTS_DIR))
        return current_file_cache.get(rel)
    except ValueError: return None

def invalidate_cache_for(path):
    try:
        rel = str(Path(path).relative_to(PROJECTS_DIR))
        current_file_cache.pop(rel, None)
        current_dir_cache.pop(rel, None)
        parent = str(Path(rel).parent)
        if parent and parent != '.':
            current_dir_cache.pop(parent, None)
    except ValueError: pass

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
            console.print("[bold cyan]🔃 Update tersedia! Memperbarui script...[/]")
            SCRIPT_PATH.write_text(remote)
            console.print("[bold green]✅ Script diperbarui. Restarting...[/]")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return True
    except Exception as e:
        # console.print(f"[dim]Update check skipped: {e}[/]")
        return True

# ----------------------- SETUP WIZARD -----------------------
def install_trigger():
    try:
        target_dir = Path("/data/data/com.termux/files/usr/bin")
        if not target_dir.exists(): 
            target_dir = Path.home() / "bin"
            target_dir.mkdir(exist_ok=True)
        
        trigger_path = target_dir / "tagent"
        script_content = f"#!/bin/bash\ncd \"{SCRIPT_PATH.parent}\" && python3 \"{SCRIPT_PATH}\" \"$@\"\n"
        
        with open(trigger_path, 'w') as f:
            f.write(script_content)
        os.chmod(trigger_path, 0o755)
        console.print("[green]✅ Perintah global 'tagent' siap![/]")
    except Exception as e: 
        console.print(f"[yellow]⚠ Gagal membuat trigger global: {e}[/]")

def run_setup():
    global PROJECTS_DIR, session_github_user
    console.print(Panel.fit("[bold cyan]🛠️  Setup Wizard – Tagent v2.1[/]", border_style="bright_blue"))
    
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
    
    if choice=="5": 
        set_key(ENV_FILE, "API_BASE_URL", Prompt.ask("Base URL").strip().rstrip('/'))
    else: 
        set_key(ENV_FILE, "API_BASE_URL", provider["base"])
        
    if choice=="1": model = Prompt.ask("Model", default="gpt-4o")
    elif choice=="2":
        console.print("1. google/gemini-2.0-flash-001 (Recommended)\n2. openai/gpt-4o\n3. anthropic/claude-3.5-sonnet\n4. Custom")
        mc = Prompt.ask("Pilih", choices=["1","2","3","4"], default="1")
        model = {"1":"google/gemini-2.0-flash-001","2":"openai/gpt-4o","3":"anthropic/claude-3.5-sonnet"}.get(mc) or Prompt.ask("ID model")
    elif choice=="3":
        console.print("1. llama-3.1-70b-versatile\n2. mixtral-8x7b-32768\n3. gemma2-9b-it\n4. Custom")
        mc = Prompt.ask("Pilih", choices=["1","2","3","4"], default="1")
        model = {"1":"llama-3.1-70b-versatile","2":"mixtral-8x7b-32768","3":"gemma2-9b-it"}.get(mc) or Prompt.ask("ID model")
    elif choice=="4": model = Prompt.ask("Nama model Ollama", default="llama3")
    else: model = Prompt.ask("ID model")
    
    set_key(ENV_FILE, "MODEL", model)
    
    gh_token = password_prompt("\n🔐 GitHub Token (opsional, tekan Enter untuk skip): ")
    if gh_token.strip():
        try:
            # Login via GH CLI
            subprocess.run(["gh","auth","login","--with-token"], input=gh_token, text=True, capture_output=True, check=True)
            user_res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if user_res.returncode==0:
                data = json.loads(user_res.stdout)
                set_key(ENV_FILE, "GITHUB_USER", data["login"])
                os.environ["GITHUB_USER"] = data["login"]
                session_github_user = data["login"]
                
                # Set Git Config Global
                subprocess.run(["git","config","--global","user.name", data.get("name", data["login"])])
                subprocess.run(["git","config","--global","user.email", data.get("email", "user@github.com")])
                console.print(f"[green]✓ Login GitHub berhasil作为: {data['login']}[/]")
        except Exception as e: 
            console.print(f"[yellow]⚠ GitHub Login Gagal: {e}[/]")
            
    default_projects = str(Path.home() / "proyek")
    projects_dir = Prompt.ask("Folder Proyek Utama", default=default_projects)
    set_key(ENV_FILE, "PROJECTS_DIR", projects_dir)
    Path(projects_dir).mkdir(parents=True, exist_ok=True)
    
    if Prompt.ask("Buat perintah global 'tagent'?", choices=["y","n"], default="y")=="y": 
        install_trigger()
        
    console.print("[green]✅ Setup selesai! Silakan restart Tagent.[/]")
    sys.exit(0)

def load_config():
    global DEVELOPER_MODE, PROJECTS_DIR, CWD, active_project, session_github_user
    global current_tasks, current_history, current_dir_cache, current_file_cache, current_last_modified, current_github_remote
    
    if ENV_FILE.exists(): load_dotenv(ENV_FILE)
    
    # Check if setup is needed
    if not os.getenv("API_KEY") and not os.getenv("API_PROVIDER","").startswith("Ollama"):
        run_setup()
        load_dotenv(ENV_FILE, override=True)
        
    PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", str(Path.home() / "proyek"))).expanduser().resolve()
    if not PROJECTS_DIR.exists(): PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Change CWD to Projects Dir initially
    os.chdir(PROJECTS_DIR)
    CWD = PROJECTS_DIR
    
    # Ensure GitHub User is loaded
    if not os.getenv("GITHUB_USER"):
        try:
            res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if res.returncode==0:
                login = json.loads(res.stdout).get("login")
                if login:
                    set_key(ENV_FILE, "GITHUB_USER", login)
                    os.environ["GITHUB_USER"] = login
                    session_github_user = login
        except: pass
    else:
        session_github_user = os.getenv("GITHUB_USER", "")
        
    DEVELOPER_MODE = session_github_user.lower()=="vicienna"
    
    # Initialize first project context
    switch_project(PROJECTS_DIR.name)
    add_session_message("system", f"Tagent v2.1 Started. GitHub: {session_github_user or 'Guest'}")

# ---------- API HANDLING ----------
def normalize_api_url(base):
    base = base.rstrip('/')
    if base.endswith('/chat/completions'): return base
    return f"{base}/chat/completions"

def stream_chat_completion(messages, tools=None):
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("API_BASE_URL")
    provider = os.getenv("API_PROVIDER","")
    model = os.getenv("MODEL")
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if "OpenRouter" in provider: 
        headers["HTTP-Referer"] = "http://localhost"
        headers["X-Title"] = "Tagent"
        
    payload = {"model":model,"messages":messages,"temperature":0.2,"stream":True}
    if tools: 
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
        
    session = requests.Session()
    url = normalize_api_url(base_url)
    
    try:
        resp = session.post(url, headers=headers, json=payload, stream=True, timeout=180)
        if resp.status_code != 200: 
            yield ('error', f"HTTP {resp.status_code}: {resp.text[:300]}")
            return
            
        content = ""
        thinking = ""
        tool_calls = []
        
        for line in resp.iter_lines(decode_unicode=True):
            if not line: continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]": break
                try:
                    obj = json.loads(data_str)
                    delta = obj.get("choices",[{}])[0].get("delta",{})
                    
                    # Handle Thinking/Reasoning Content (specific models)
                    reasoning = delta.get("reasoning") or delta.get("thinking") or delta.get("reasoning_content")
                    if reasoning: 
                        thinking += reasoning
                        yield ('thinking', reasoning)
                        
                    if "content" in delta and delta["content"] is not None: 
                        content += delta["content"]
                        yield ('content', delta["content"])
                        
                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index",0)
                            while len(tool_calls) <= idx: 
                                tool_calls.append({"id":"","type":"function","function":{"name":"","arguments":""}})
                            if tc.get("id"): tool_calls[idx]["id"] = tc["id"]
                            if tc.get("function"):
                                if "name" in tc["function"]: tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                if "arguments" in tc["function"]: tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]
                                
                except json.JSONDecodeError: pass
                
        final_msg = {"role":"assistant","content":content}
        if thinking: final_msg["thinking"] = thinking
        if tool_calls: final_msg["tool_calls"] = tool_calls
        yield ('done', final_msg)
        
    except requests.exceptions.RequestException as e: 
        yield ('error', f"Koneksi gagal: {e}")

def chat_completion_nonstream(messages, tools=None, max_retries=3):
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("API_BASE_URL")
    provider = os.getenv("API_PROVIDER","")
    model = os.getenv("MODEL")
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if "OpenRouter" in provider: 
        headers["HTTP-Referer"] = "http://localhost"
        headers["X-Title"] = "Tagent"
        
    payload = {"model":model,"messages":messages,"temperature":0.2}
    if tools: 
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
        
    session = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=1, status_forcelist=[429,502,503,504], allowed_methods=["POST"])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    
    url = normalize_api_url(base_url)
    
    for attempt in range(max_retries):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                console.print(f"[yellow]⏳ Rate limit 429, tunggu {wait}s[/]")
                time.sleep(wait)
                continue
            if resp.status_code != 200: 
                return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            return resp.json()
        except Exception as e:
            if attempt < max_retries-1: 
                console.print(f"[yellow]⚠ Koneksi gagal, retry {attempt+2}/{max_retries}[/]")
                time.sleep(2**attempt)
            else: 
                return {"error": f"Koneksi gagal total: {e}"}
    return {"error":"Gagal"}

# ---------- TOOLS IMPLEMENTATION ----------

def check_github_auth():
    try: 
        subprocess.run(["gh","auth","status"], check=True, capture_output=True)
        return True
    except: 
        return False

def ensure_git_identity():
    """Memastikan git config user.name dan email terisi."""
    try:
        repo = git.Repo(CWD)
        reader = repo.config_reader()
        name_set = reader.has_option("user","name")
        email_set = reader.has_option("user","email")
        
        if not name_set or not email_set:
            # Coba ambil dari GitHub API
            res = subprocess.run(["gh","api","user"], capture_output=True, text=True)
            if res.returncode == 0:
                d = json.loads(res.stdout)
                email = d.get("email") or "user@github.com"
                name = d.get("name") or d.get("login") or "AI Agent"
            else:
                email = "user@example.com"
                name = session_github_user or "AI Agent User"
                
            writer = repo.config_writer()
            if not name_set: writer.set_value("user","name",name)
            if not email_set: writer.set_value("user","email",email)
            writer.release()
    except Exception: pass

def ensure_git_remote(repo_name):
    """Memastikan remote origin ada dan benar."""
    try:
        repo = git.Repo(CWD)
        user = session_github_user or os.getenv("GITHUB_USER", "")
        if not user: return False, "GitHub user tidak ditemukan."
        
        expected_url = f"https://github.com/{user}/{repo_name}.git"
        
        if repo.remotes:
            origin = repo.remote('origin')
            current_url = list(origin.urls)[0]
            if current_url != expected_url:
                # Update URL jika berbeda
                origin.set_url(expected_url)
                console.print(f"[dim]🔄 Updated remote origin URL[/]")
        else:
            repo.create_remote('origin', expected_url)
            console.print(f"[dim]➕ Created remote origin[/]")
            
        return True, ""
    except Exception as e:
        return False, str(e)

def github_create_repo(name, private=False, description=""):
    ensure_git_identity()
    cmd = ["gh","repo","create",name,"--push"] + (["--private"] if private else ["--public"])
    if description: cmd.extend(["-d",description])
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=CWD)
        if res.returncode != 0:
            # Cek jika repo sudah ada
            if "already exists" in res.stderr:
                return f"⚠️ Repo '{name}' sudah ada. Pastikan folder lokal sesuai."
            return f"ERROR: {res.stderr.strip()}"
            
        out = res.stdout.strip() or f"Repo {name} dibuat."
        
        # Ensure remote is set correctly in memory
        user = session_github_user or os.getenv("GITHUB_USER","")
        if user:
            remote_url = f"https://github.com/{user}/{name}.git"
            current_github_remote = remote_url
            save_project_memory(active_project, github_remote=current_github_remote)
            
        add_session_message("tool", f"Repo GitHub dibuat: {name}")
        return out
    except Exception as e: return f"ERROR: {e}"

def github_push(commit_msg="Update from Tagent"):
    """
    Fixed Push Logic:
    1. Check if git repo.
    2. Detect submodules (prevent pushing root if submodules have changes).
    3. Add, Commit, Push.
    4. Handle master/main branch naming.
    """
    try:
        ensure_git_identity()
        
        if not (CWD / ".git").exists():
            return "ERROR: Bukan repository Git. Gunakan `github_create_repo` dulu."
        
        repo = git.Repo(CWD)
        
        # 1. Deteksi Submodule
        # Cara aman: cek jika ada folder di dalam yang memiliki .git
        submodule_warnings = []
        for item in CWD.iterdir():
            if item.is_dir() and (item / ".git").exists() and item.name != ".git":
                submodule_warnings.append(item.name)
                
        if submodule_warnings:
            warning = "⚠️ Terdeteksi folder Git terpisah (submodule manual):\n"
            for sp in submodule_warnings: warning += f"  - {sp}\n"
            warning += "Masuk ke folder tersebut (`change_directory`) dan push dari sana secara terpisah."
            return warning

        # 2. Check Status
        if not repo.is_dirty(untracked_files=True): 
            return "✅ Tidak ada perubahan untuk di-push."
        
        # 3. Add & Commit
        repo.git.add(A=True)
        repo.index.commit(commit_msg)
        
        # 4. Ensure Remote
        repo_name = CWD.name
        success, msg = ensure_git_remote(repo_name)
        if not success: return f"ERROR Remote: {msg}"
        
        # 5. Push
        branch = repo.active_branch.name
        
        # Handle case dimana branch belum track remote
        try:
            repo.git.push("--set-upstream", "origin", branch)
        except git.exc.GitCommandError as e:
            stderr = str(e.stderr)
            # Jika error karena branch name mismatch (master vs main)
            if "refs/heads/master" in stderr or "refs/heads/main" in stderr:
                # Coba rename branch lokal ke main jika remote menolak
                if branch != "main":
                    console.print("[yellow]🔄 Mencoba rename branch ke 'main'...[/]")
                    repo.git.branch("-M", "main")
                    repo.git.push("--set-upstream", "origin", "main")
                    branch = "main"
                else:
                    return f"ERROR Push: {stderr[:200]}"
            else:
                return f"ERROR Push: {stderr[:200]}"
                
        add_session_message("tool", f"Push berhasil: {commit_msg} (branch: {branch})")
        return f"✅ Pushed: {commit_msg} (branch: {branch})"
        
    except Exception as e: 
        return f"ERROR: {str(e)[:200]}"

def github_clone(repo_url, target_dir=""):
    cmd = ["gh","repo","clone",repo_url] + ([target_dir] if target_dir else [])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=CWD)
        if res.returncode != 0:
            return f"ERROR Clone: {res.stderr.strip()}"
            
        if target_dir:
            new_path = CWD / target_dir
            if new_path.exists(): 
                switch_project(target_dir)
        else:
            # Extract repo name from URL
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            if (CWD / repo_name).exists():
                switch_project(repo_name)
                
        add_session_message("tool", f"Repo di-clone: {repo_url}")
        return f"Repo {repo_url} di-clone."
    except Exception as e: return f"ERROR: {e}"

# ---------- LOGGING & MONITORING ----------
LOG_DIR = CWD / "logs"
LOG_DIR.mkdir(exist_ok=True)

def auto_run(command, project_name):
    global active_project
    subprocess.run(["tmux","kill-session","-t",project_name], capture_output=True)
    log = LOG_DIR / f"{project_name}.log"
    
    # Use bash explicitly for better compatibility
    shell_cmd = f"bash -c '{command} 2>&1 | tee {log}'"
    subprocess.run(["tmux","new-session","-d","-s",project_name, shell_cmd])
    
    active_project = project_name
    add_session_message("tool", f"Proyek dijalankan: {project_name}")
    return f"Proyek {project_name} dijalankan di background. Log: {log}"

def auto_stop(project_name):
    subprocess.run(["tmux","kill-session","-t",project_name], capture_output=True)
    add_session_message("tool", f"Proyek dihentikan: {project_name}")
    return f"Sesi {project_name} dihentikan."

error_queue = queue.Queue()

def monitor_logs(project_name):
    log = LOG_DIR / f"{project_name}.log"
    if not log.exists(): return
    last_pos = 0
    while True:
        time.sleep(2)
        if not log.exists(): continue
        try:
            cur_size = log.stat().st_size
            if cur_size > last_pos:
                with open(log,'r') as f: 
                    f.seek(last_pos)
                    new_data = f.read()
                last_pos = cur_size
                # Simple error detection
                if any(k in new_data.lower() for k in ["traceback","error","fatal","exception"]): 
                    error_queue.put((project_name, new_data[-500:])) # Ambil ekor error
        except: pass

def show_log_panel(project_name, lines=10):
    if not project_name: return
    log = LOG_DIR / f"{project_name}.log"
    if not log.exists(): return
    try:
        lines_data = log.read_text().splitlines()[-lines:]
        if lines_data: 
            console.print(Panel("\n".join(lines_data), title=f"📋 Log [{project_name}]", border_style="blue"))
    except: pass

# ---------- FILE & DIR OPERATIONS ----------
def change_provider(provider=None, api_key=None, base_url=None, model=None):
    if provider: set_key(ENV_FILE, "API_PROVIDER", provider)
    if api_key: set_key(ENV_FILE, "API_KEY", api_key)
    if base_url: set_key(ENV_FILE, "API_BASE_URL", base_url)
    if model: set_key(ENV_FILE, "MODEL", model)
    load_dotenv(ENV_FILE, override=True)
    add_session_message("tool", f"Provider diubah: {provider} / {model}")
    return f"✅ Provider diubah: {os.getenv('API_PROVIDER')} | Model: {os.getenv('MODEL')}"

def change_directory(path):
    global CWD
    try:
        target = (CWD / path).resolve()
        
        # Security Check: Prevent escaping PROJECTS_DIR
        if not str(target).startswith(str(PROJECTS_DIR)):
            return f"ERROR: Akses ditolak. Tidak bisa keluar dari folder proyek ({PROJECTS_DIR})."
        
        if not target.is_dir(): 
            return f"ERROR: {path} bukan direktori."
            
        os.chdir(target)
        CWD = target
        switch_project(target.name)
        return f"Pindah ke {CWD}"
    except Exception as e: return f"ERROR: {e}"

def list_directory(path="."):
    target = (CWD / path).resolve()
    
    # Security Check
    if not str(target).startswith(str(PROJECTS_DIR)): 
        return f"ERROR: Akses ditolak."
    if not target.is_dir(): 
        return f"ERROR: {path} bukan direktori."
        
    cached = get_cached_dir(target)
    if cached: return cached["entries"]
    
    try: 
        items = os.listdir(target)
    except: 
        return f"ERROR: tidak bisa membaca {path}"
        
    dirs = [d for d in items if (target/d).is_dir()]
    files = [f for f in items if (target/f).is_file()]
    
    res = ""
    if dirs: res += "[DIR] " + ", ".join(sorted(dirs)) + "\n"
    if files: res += "[FILE] " + ", ".join(sorted(files))
    
    entries = res.strip() or "Kosong"
    cache_dir(target, entries)
    save_project_memory(active_project, dir_cache=current_dir_cache) # Async save recommended but sync here for simplicity
    return entries

def shell_command(cmd):
    try:
        # Determine shell
        shell_exec = "/data/data/com.termux/files/usr/bin/bash" if "ANDROID_ROOT" in os.environ else "/bin/bash"
        
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=CWD, executable=shell_exec)
        out = (res.stdout + res.stderr).strip()
        
        if not out: return "(ok)"
        if "command not found" in out.lower(): 
            return f"ERROR: Perintah tidak ditemukan. Coba periksa nama perintah."
            
        invalidate_cache_for(CWD)
        save_project_memory(active_project, dir_cache=current_dir_cache)
        add_session_message("tool", f"Shell: {cmd[:100]}")
        return out
    except subprocess.TimeoutExpired: return "ERROR: Timeout (60s)"
    except Exception as e: return f"ERROR: {e}"

def read_file(path):
    full = (CWD / path).resolve()
    
    # Security Check
    if not str(full).startswith(str(PROJECTS_DIR)): 
        return f"ERROR: File di luar folder proyek."
    if not full.is_file(): 
        return f"ERROR: {path} tidak ditemukan."
        
    cached = get_cached_file(full)
    if cached: return cached["content"]
    
    try: 
        content = full.read_text(encoding='utf-8', errors='ignore')
    except: 
        return f"ERROR: tidak bisa membaca {path}"
        
    cache_file(full, content)
    save_project_memory(active_project, file_cache=current_file_cache)
    return content

def write_file(path, content):
    full = (CWD / path).resolve()
    
    # Security Check
    if not str(full).startswith(str(PROJECTS_DIR)): 
        return f"ERROR: Tidak bisa menulis di luar folder proyek."
        
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding='utf-8')
    
    cache_file(full, content)
    invalidate_cache_for(full.parent)
    save_project_memory(active_project, file_cache=current_file_cache, dir_cache=current_dir_cache)
    add_session_message("tool", f"File ditulis: {path} ({len(content)} char)")
    return f"✅ {path} ditulis ({len(content)} karakter)."

def edit_file(path, old_str, new_str, **kwargs):
    full = (CWD / path).resolve()
    
    # Security Check
    if not str(full).startswith(str(PROJECTS_DIR)): 
        return f"ERROR: File di luar folder proyek."
        
    content = read_file(path)
    if content.startswith("ERROR"): return content
    
    search = old_str
    # Fallback keys for older tool specs
    if search not in content:
        for key in ["old_string","old","find","search"]:
            if key in kwargs and kwargs[key] in content:
                search = kwargs[key]
                break
                
    if search not in content: 
        return "ERROR: String lama tidak ditemukan. Periksa ejaan atau gunakan read_file dulu."
        
    new_content = content.replace(search, new_str, 1)
    full.write_text(new_content, encoding='utf-8')
    
    cache_file(full, new_content)
    invalidate_cache_for(full.parent)
    save_project_memory(active_project, file_cache=current_file_cache)
    add_session_message("tool", f"File diedit: {path}")
    return f"✅ {path} diedit."

# ---------- TOOL DEFINITIONS ----------
tools_spec = [
    {"type":"function","function":{"name":"change_directory","description":"Pindah ke folder proyek spesifik.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_directory","description":"Lihat isi direktori.","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}}}}},
    {"type":"function","function":{"name":"shell_command","description":"Jalankan perintah shell (bash).","parameters":{"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}},
    {"type":"function","function":{"name":"read_file","description":"Baca konten file.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Tulis file baru atau timpa file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"edit_file","description":"Edit sebagian file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"github_create_repo","description":"Buat repo GitHub baru dan inisialisasi Git.","parameters":{"type":"object","properties":{"name":{"type":"string"},"private":{"type":"boolean","default":False},"description":{"type":"string","default":""}},"required":["name"]}}},
    {"type":"function","function":{"name":"github_push","description":"Commit dan push perubahan ke GitHub. Pastikan sudah di folder proyek yang benar.","parameters":{"type":"object","properties":{"commit_msg":{"type":"string","default":"Update from Tagent"}}}}},
    {"type":"function","function":{"name":"github_clone","description":"Clone repo GitHub ke folder proyek.","parameters":{"type":"object","properties":{"repo_url":{"type":"string"},"target_dir":{"type":"string","default":""}},"required":["repo_url"]}}},
    {"type":"function","function":{"name":"auto_run","description":"Jalankan perintah panjang di background (tmux).","parameters":{"type":"object","properties":{"command":{"type":"string"},"project_name":{"type":"string"}},"required":["command","project_name"]}}},
    {"type":"function","function":{"name":"auto_stop","description":"Hentikan proses background.","parameters":{"type":"object","properties":{"project_name":{"type":"string"}},"required":["project_name"]}}},
    {"type":"function","function":{"name":"change_provider","description":"Ganti konfigurasi LLM Provider.","parameters":{"type":"object","properties":{"provider":{"type":"string"},"api_key":{"type":"string"},"base_url":{"type":"string"},"model":{"type":"string"}}}}},
]

tool_map = {t["function"]["name"]: eval(t["function"]["name"]) for t in tools_spec}

MAX_REPEATED = 3

def execute_tool_chain(messages, initial_tool_calls):
    global tool_call_counter
    with console.status("[bold cyan]🔧 Memproses Tools...[/]", spinner="dots") as status:
        pending = list(initial_tool_calls)
        
        while pending:
            tc = pending.pop(0)
            func_name = tc["function"]["name"]
            args = tc["function"]["arguments"]
            
            if isinstance(args, str):
                try: args = json.loads(args)
                except: args = {}
                
            # Loop prevention
            key = f"{func_name}:{json.dumps(args, sort_keys=True)}"
            tool_call_counter[key] = tool_call_counter.get(key,0)+1
            
            if tool_call_counter[key] > MAX_REPEATED:
                result = f"❌ Tindakan '{func_name}' diblokir karena pengulangan berlebihan."
            else:
                status.update(f"[bold yellow]⚙️  Running: {func_name}...[/]")
                func = tool_map.get(func_name)
                try: 
                    result = func(**args) if func else "Tool tidak dikenal."
                except Exception as e: 
                    result = f"ERROR Execution: {e}"
                    
            console.print(f"[dim]🔧 Called: {func_name}[/]")
            # Only print result panel if it's short, otherwise truncate
            res_display = str(result) if len(str(result)) < 500 else str(result)[:500] + "..."
            console.print(Panel(Syntax(res_display,"text",theme="monokai"), title=f"📤 Result: {func_name}"))
            
            messages.append({"role":"tool","tool_call_id":tc.get("id","manual"),"name":func_name,"content":str(result)})
            
            # Special handling for auto_run monitoring
            if func_name == "auto_run":
                project = args.get("project_name")
                if project: 
                    threading.Thread(target=monitor_logs, args=(project,), daemon=True).start()
                    
        # After executing initial tools, ask AI for next step or final answer
        for _ in range(5): # Max 5 turns of tool chaining
            status.update("[bold cyan]🤖 Waiting for AI decision...[/]")
            resp = chat_completion_nonstream(messages, tools_spec)
            
            if "error" in resp:
                console.print(f"[red]{resp['error']}[/]")
                return messages, None
                
            msg = resp["choices"][0]["message"]
            messages.append(msg)
            
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    pending.append(tc)
                    
                # Execute this batch
                while pending:
                    tc = pending.pop(0)
                    func_name = tc["function"]["name"]
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {}
                        
                    key = f"{func_name}:{json.dumps(args, sort_keys=True)}"
                    tool_call_counter[key] = tool_call_counter.get(key,0)+1
                    
                    if tool_call_counter[key] > MAX_REPEATED:
                        result = f"❌ Tindakan '{func_name}' diblokir."
                    else:
                        status.update(f"[bold yellow]⚙️  Running: {func_name}...[/]")
                        func = tool_map.get(func_name)
                        try: result = func(**args) if func else "Tool tidak dikenal."
                        except Exception as e: result = f"ERROR: {e}"
                        
                    console.print(f"[dim]🔧 Called: {func_name}[/]")
                    res_display = str(result) if len(str(result)) < 500 else str(result)[:500] + "..."
                    console.print(Panel(Syntax(res_display,"text",theme="monokai"), title=f"📤 Result: {func_name}"))
                    messages.append({"role":"tool","tool_call_id":tc.get("id","manual"),"name":func_name,"content":str(result)})
                    
                    if func_name == "auto_run":
                        project = args.get("project_name")
                        if project: threading.Thread(target=monitor_logs, args=(project,), daemon=True).start()
            else:
                return messages, msg.get("content") or "✅ Tugas selesai."
                
    return messages, "⚠️ Batas iterasi tool tercapai."

# ---------- DISPLAY STREAMING ----------
def display_stream(messages):
    start = time.time()
    thinking = ""
    content = ""
    has_thinking = False
    final_msg = None
    first_content_time = None
    
    def render():
        elapsed = time.time()-start
        timer = f"⏱ {elapsed:.1f}s"
        panel_text = Text()
        
        if has_thinking:
            panel_text.append("🧠 Thinking Process (", style="bold cyan")
            panel_text.append(timer, style="bold magenta")
            panel_text.append(")\n", style="bold cyan")
            panel_text.append("─"*50+"\n", style="dim")
            panel_text.append(thinking, style="dim cyan")
            panel_text.append("\n"+"─"*50, style="dim")
        else: 
            panel_text.append("🧠 Thinking... ", style="bold yellow")
            panel_text.append(timer, style="bold magenta")
            
        panel_text.append("\n")
        panel_text.append("(Ctrl+C to cancel)", style="red")
        return Panel(panel_text, border_style="blue", title="Streaming Response")
        
    try:
        with Live(render(), refresh_per_second=8, vertical_overflow="visible") as live:
            for ev, data in stream_chat_completion(messages, tools_spec):
                if ev == 'thinking': 
                    has_thinking = True
                    thinking += data
                    live.update(render())
                elif ev == 'content':
                    if not first_content_time: first_content_time = time.time()
                    content += data
                    live.update(render())
                elif ev == 'error': 
                    console.print(f"[red]{data}[/]")
                    return None, ""
                elif ev == 'done': 
                    final_msg = data
                    break
    except KeyboardInterrupt: 
        console.print("\n[red]⚠ Dibatalkan oleh user.[/]")
        return None, ""
        
    end = time.time()
    think_dur = (first_content_time or end)-start
    total_dur = end-start
    
    if has_thinking: 
        console.print(f"[bold magenta]⏱ Thinking: {think_dur:.1f}s | Total: {total_dur:.1f}s[/]")
    else: 
        console.print(f"[bold magenta]⏱ Response Time: {total_dur:.1f}s[/]")
        
    return final_msg, content

# ---------- MAIN LOOP ----------
def run_agent():
    global tool_call_counter, active_project, current_tasks, current_history
    global current_dir_cache, current_file_cache, current_last_modified, current_github_remote
    global DEVELOPER_MODE, session_github_user, session_messages

    load_config()
    model = os.getenv("MODEL","google/gemini-2.0-flash-001")

    SYSTEM_PROMPT = f"""Kamu Tagent v2.1, AI Developer Agent canggih di Termux.
Folder Proyek Utama: {PROJECTS_DIR}
Proyek Aktif Saat Ini: {active_project or 'none'}
GitHub User: {session_github_user or 'Guest'}
Mode Developer: {'✅' if DEVELOPER_MODE else '❌'}

TOOLS TERSEDIA:
- File: read_file, write_file, edit_file
- Dir: list_directory, change_directory (WAJIB masuk folder proyek sebelum kerja)
- Shell: shell_command (untuk install package, run script pendek)
- Git/GitHub: github_create_repo, github_push, github_clone
- Process: auto_run (untuk server long-running), auto_stop

ATURAN PENTING:
1. KEAMANAN PATH: Jangan pernah mengakses file di luar {PROJECTS_DIR}.
2. GIT PUSH: Sebelum push, PASTIKAN kamu sudah `change_directory` ke folder proyek yang tepat. Jangan push dari root.
3. SUBMODULE: Jika ada folder dengan .git di dalamnya, itu submodule. Masuk ke folder itu dulu sebelum push.
4. MEMORY: Gunakan memory proyek untuk mengingat tugas jangka panjang.
5. BAHASA: Gunakan Bahasa Indonesia yang ramah dan teknis.

Jika user minta buat proyek baru:
1. Buat folder (shell_command mkdir).
2. Masuk folder (change_directory).
3. Init git & create repo (github_create_repo).
"""

    messages = [{"role":"system","content":SYSTEM_PROMPT}]

    os.system('clear')
    console.print("[dim]Checking updates...[/]")
    check_and_update()
    time.sleep(0.5)
    os.system('clear')

    banner_text = Text()
    banner_text.append("🤖  T A G E N T  v2.1  🤖\n\n", style="bold white on blue")
    banner_text.append("Creator : Vicienna\n", style="cyan")
    banner_text.append("Source  : github.com/Vicienna/ai-agent\n", style="cyan")
    banner_text.append("IG: ceena.dev  |  Discord: hallo.dev", style="cyan")
    console.print(Panel(Align.center(banner_text), border_style="bright_cyan", padding=(1,2), title="Welcome", title_align="left"))

    gh_ok = "✅" if check_github_auth() else "❌"
    dev_ok = "✅" if DEVELOPER_MODE else "❌"
    console.print(Panel(f"Provider: {os.getenv('API_PROVIDER')} | Model: {model} | GitHub: {gh_ok} | Dev: {dev_ok}\nFolder: {PROJECTS_DIR} | Proyek: {active_project}", border_style="blue"))

    while True:
        tool_call_counter.clear()
        
        # Check for async errors from monitored logs
        try:
            proj, err = error_queue.get_nowait()
            console.print(Panel(f"[red]🐛 Error Detected in {proj}![/]\n{err[:500]}", title="Auto Monitor"))
            current_tasks.append(f"Perbaiki error di {proj}: {err[:200]}")
            save_project_memory(active_project, tasks=current_tasks)
        except queue.Empty: pass

        # Auto-fix mode if tasks exist
        if current_tasks:
            user_input = current_tasks.pop(0)
            save_project_memory(active_project, tasks=current_tasks)
            console.print(f"[yellow]🔧 Auto‑fix Task: {user_input}[/]")
        else:
            try: user_input = Prompt.ask("\n[bold green]▸[/]")
            except (KeyboardInterrupt, EOFError): 
                console.print("\n[red]Bye![/]")
                break
                
            if user_input.lower() in ["exit","quit","keluar"]: break
            if not user_input.strip(): continue

        add_session_message("user", user_input)
        use_memory = needs_memory(user_input, active_project)

        # Construct Message Context
        if use_memory:
            base_messages = [{"role":"system","content":SYSTEM_PROMPT}]
            # Add recent history from project memory
            for h in current_history[-20:]: base_messages.append(h)
            base_messages.append({"role":"user","content":user_input})
        else:
            base_messages = [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":user_input}]

        final_msg, content = None, ""
        try: 
            final_msg, content = display_stream(base_messages)
        except Exception as e: 
            console.print(f"[red]Stream error: {e}[/]")
            continue
            
        if final_msg is None: continue

        add_session_message("assistant", content or "(tool calls)")

        # Save to history if relevant
        if use_memory:
            current_history.append({"role":"user","content":user_input})
            current_history.append(final_msg)
            if len(current_history) > 40: current_history = current_history[-40:]
            save_project_memory(active_project, history=current_history)

        # Handle Tool Calls
        if "tool_calls" in final_msg:
            messages = base_messages + [final_msg]
            try:
                messages, final_content = execute_tool_chain(messages, final_msg["tool_calls"])
                if final_content:
                    add_session_message("assistant", final_content)
                    console.print(Panel(Markdown(final_content), title="🤖 Tagent Final", border_style="green"))
                else:
                    console.print("[dim]✅ Semua tugas tool selesai.[/]")
            except KeyboardInterrupt:
                console.print("\n[red]⚠ Dibatalkan.[/]")
                continue
        else:
            if content: 
                console.print(Panel(Markdown(content), title="🤖 Tagent", border_style="green"))
            else: 
                console.print("[dim]✅ Selesai.[/]")

        show_log_panel(active_project)

if __name__ == "__main__":
    try: run_agent()
    except KeyboardInterrupt: console.print("\n[red]Tagent dimatikan.[/]")
