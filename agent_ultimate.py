#!/usr/bin/env python3
"""
AI Agent Ultimate – Multi-Provider + Setup Wizard Otomatis
Mendukung OpenAI, OpenRouter, Google (via OpenRouter), Custom endpoint.
"""

import os, sys, subprocess, json
from pathlib import Path

import openai
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm

from github import Github, GithubException
import git
from dotenv import load_dotenv, set_key

console = Console()
ENV_FILE = Path(__file__).parent / ".env"
CWD = Path.cwd()

# ==================== SETUP WIZARD ====================
def run_setup():
    console.print(Panel.fit(
        "[bold cyan]🛠️  AI Agent Setup Wizard[/]\n"
        "[dim]Konfigurasi multi‑API, cukup sekali saja.[/]",
        border_style="bright_blue"
    ))

    # 1. Pilih Penyedia API
    console.print("\n[bold]1️⃣  Pilih Penyedia API[/]")
    providers = {
        "1": {"name": "OpenAI", "base": "https://api.openai.com/v1", "key_link": "https://platform.openai.com/api-keys"},
        "2": {"name": "OpenRouter (bisa akses Google, Meta, dll.)", "base": "https://openrouter.ai/api/v1", "key_link": "https://openrouter.ai/keys"},
        "3": {"name": "Custom (base URL sendiri)", "base": "", "key_link": ""}
    }
    for key, p in providers.items():
        console.print(f"  [dim]{key}.[/] {p['name']}")
    choice = Prompt.ask("Pilih nomor penyedia", choices=list(providers.keys()), default="2")
    provider = providers[choice]

    # 2. API Key
    console.print(f"\n[bold]2️⃣  API Key untuk {provider['name']}[/]")
    if provider["key_link"]:
        console.print(f"🔗 Dapatkan key di: [underline blue]{provider['key_link']}[/]")
    api_key = Prompt.ask("Masukkan API key", password=True)
    set_key(ENV_FILE, "API_KEY", api_key)

    # 3. Base URL (hanya untuk custom)
    if choice == "3":
        base_url = Prompt.ask("Masukkan base URL (contoh: https://api.mistral.ai/v1)")
        set_key(ENV_FILE, "API_BASE_URL", base_url)
    else:
        set_key(ENV_FILE, "API_BASE_URL", provider["base"])
    set_key(ENV_FILE, "API_PROVIDER", provider["name"])

    # 4. Pilih Model
    console.print("\n[bold]3️⃣  Pilih Model AI[/]")
    if choice == "1":  # OpenAI
        models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "Custom"]
    elif choice == "2":  # OpenRouter
        models = [
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-2.0-flash-001",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "Custom"
        ]
    else:
        models = ["Custom"]

    for i, m in enumerate(models, 1):
        console.print(f"  [dim]{i}.[/] {m}")
    model_choice = Prompt.ask(
        "Pilih nomor model",
        choices=[str(i) for i in range(1, len(models)+1)],
        default="1"
    )
    if models[int(model_choice)-1] == "Custom":
        model = Prompt.ask("Masukkan ID model (contoh: meta-llama/llama-3.1-70b-instruct)")
    else:
        model = models[int(model_choice)-1]
    set_key(ENV_FILE, "MODEL", model)

    # 5. GitHub Connection (opsional)
    console.print("\n[bold]4️⃣  Koneksi GitHub (opsional)[/]")
    use_token = Confirm.ask("Gunakan GitHub personal access token?", default=False)
    if use_token:
        token = Prompt.ask("Masukkan GitHub token", password=True)
        set_key(ENV_FILE, "GITHUB_TOKEN", token)
        try:
            g = Github(token)
            user = g.get_user().login
            console.print(f"[green]✓ Terhubung sebagai [bold]{user}[/][/]")
        except Exception as e:
            console.print(f"[yellow]⚠ Token mungkin tidak valid: {e}[/]")
    else:
        console.print("[dim]Anda bisa login dengan 'gh auth login' setelah setup.[/]")

    # 6. Direktori Kerja
    console.print("\n[bold]5️⃣  Direktori Kerja (opsional)[/]")
    custom_dir = Prompt.ask("Masukkan path direktori kerja (kosongkan untuk direktori saat ini)")
    if custom_dir.strip():
        set_key(ENV_FILE, "WORK_DIR", custom_dir)

    console.print(Panel.fit("[bold green]✅ Setup selesai![/]\nMenjalankan agent...", border_style="green"))

# ==================== LOAD CONFIG & CLIENT ====================
def load_config():
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    if not os.getenv("API_KEY"):
        console.print("[yellow]⚠ Konfigurasi belum lengkap, memulai setup...[/]")
        run_setup()
        load_dotenv(ENV_FILE, override=True)
    # Set working directory
    work_dir = os.getenv("WORK_DIR")
    if work_dir:
        os.chdir(Path(work_dir).expanduser().resolve())
    global CWD
    CWD = Path.cwd()

def create_client():
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("API_BASE_URL")
    provider = os.getenv("API_PROVIDER", "")
    if not api_key:
        raise ValueError("API_KEY tidak ditemukan di environment.")
    headers = {}
    if "OpenRouter" in provider:
        headers = {
            "HTTP-Referer": "http://localhost",
            "X-Title": "AI-Agent-Ultimate",
        }
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=headers if headers else None,
    )

# ==================== GITHUB HELPERS ====================
def check_github_connection():
    try:
        subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=True)
        console.print("[green]✓ GitHub CLI (gh) terautentikasi.[/]")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    token = os.getenv("GITHUB_TOKEN")
    if token:
        try:
            g = Github(token)
            user = g.get_user().login
            console.print(f"[green]✓ Terhubung ke GitHub sebagai [bold]{user}[/].[/]")
            return True
        except Exception as e:
            console.print(f"[red]✗ Token tidak valid: {e}[/]")
    else:
        console.print("[yellow]⚠ GitHub belum terhubung.[/]")
    return False

def get_github_client():
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return Github(token)
    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return Github(res.stdout.strip())
    except Exception:
        return None

# ==================== TOOLS (sama seperti sebelumnya) ====================
def change_directory(path: str) -> str:
    global CWD
    try:
        new_path = (CWD / path).resolve()
        if not new_path.is_dir():
            return f"ERROR: {path} bukan direktori."
        os.chdir(new_path)
        CWD = new_path
        return f"Direktori kerja sekarang: {CWD}"
    except Exception as e:
        return f"ERROR: {e}"

def list_directory(path: str = ".") -> str:
    target = (CWD / path).resolve()
    if not target.is_dir():
        return f"ERROR: {path} bukan direktori."
    items = os.listdir(target)
    dirs = [d for d in items if (target / d).is_dir()]
    files = [f for f in items if (target / f).is_file()]
    out = f"Isi {target}:\n"
    if dirs:
        out += "[DIR]  " + ", ".join(dirs) + "\n"
    if files:
        out += "[FILE] " + ", ".join(files)
    return out or "Direktori kosong."

def shell_command(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=CWD)
        return (result.stdout + result.stderr).strip() or "(tidak ada output)"
    except Exception as e:
        return f"ERROR: {e}"

def read_file(path: str) -> str:
    full_path = (CWD / path).resolve()
    if not full_path.is_file():
        return f"ERROR: File {path} tidak ditemukan."
    return full_path.read_text()

def write_file(path: str, content: str) -> str:
    full_path = (CWD / path).resolve()
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    return f"File {path} berhasil ditulis ({len(content)} karakter)."

def edit_file(path: str, old_str: str, new_str: str) -> str:
    full_path = (CWD / path).resolve()
    if not full_path.is_file():
        return f"ERROR: File {path} tidak ditemukan."
    text = full_path.read_text()
    if old_str not in text:
        return f"ERROR: string '{old_str[:50]}...' tidak ditemukan."
    new_text = text.replace(old_str, new_str, 1)
    full_path.write_text(new_text)
    return f"File {path} berhasil diedit."

def github_create_repo(name: str, private: bool = False, description: str = "") -> str:
    g = get_github_client()
    if not g:
        return "ERROR: Tidak terhubung ke GitHub."
    try:
        user = g.get_user()
        repo = user.create_repo(name, private=private, description=description)
        return f"Repo [bold]{repo.full_name}[/] dibuat: {repo.html_url}"
    except GithubException as e:
        return f"ERROR GitHub: {e}"

def github_push_changes(repo_path: str = ".", commit_msg: str = "Update from AI Agent") -> str:
    try:
        repo = git.Repo(repo_path)
        if repo.is_dirty(untracked_files=True):
            repo.git.add(A=True)
            repo.index.commit(commit_msg)
            origin = repo.remote(name="origin")
            origin.push()
            return f"Perubahan di-push ke GitHub ({commit_msg})."
        else:
            return "Tidak ada perubahan untuk di-commit."
    except Exception as e:
        return f"ERROR git: {e}"

def git_init_and_set_remote(repo_name: str) -> str:
    try:
        if not (CWD / ".git").exists():
            subprocess.run(["git", "init"], cwd=CWD, check=True)
        g = get_github_client()
        if not g:
            return "ERROR: Tidak ada koneksi GitHub."
        user = g.get_user().login
        remote_url = f"https://github.com/{user}/{repo_name}.git"
        remotes = subprocess.run(["git", "remote"], capture_output=True, text=True, cwd=CWD).stdout
        if "origin" in remotes:
            subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=CWD, check=True)
        else:
            subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=CWD, check=True)
        return f"Git siap. Remote origin: {remote_url}"
    except Exception as e:
        return f"ERROR: {e}"

# Tool definitions (sama seperti sebelumnya)
tools = [
    {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "Pindah direktori kerja.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lihat isi direktori.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shell_command",
            "description": "Jalankan perintah shell.",
            "parameters": {
                "type": "object",
                "properties": {"cmd": {"type": "string"}},
                "required": ["cmd"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Baca isi file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Tulis file baru.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Ganti string dalam file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"}
                },
                "required": ["path", "old_str", "new_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_repo",
            "description": "Buat repo GitHub baru.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "private": {"type": "boolean", "default": False},
                    "description": {"type": "string", "default": ""}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_push_changes",
            "description": "Commit & push perubahan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "default": "."},
                    "commit_msg": {"type": "string", "default": "Update from AI Agent"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_init_and_set_remote",
            "description": "Init git & atur remote origin ke repo GitHub.",
            "parameters": {
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"]
            }
        }
    }
]

tool_map = {
    "change_directory": change_directory,
    "list_directory": list_directory,
    "shell_command": shell_command,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "github_create_repo": github_create_repo,
    "github_push_changes": github_push_changes,
    "git_init_and_set_remote": git_init_and_set_remote,
}

# ==================== MAIN AGENT LOOP ====================
def run_agent():
    load_config()
    model = os.getenv("MODEL", "meta-llama/llama-3.1-70b-instruct")
    client = create_client()

    SYSTEM_PROMPT = f"""Kamu adalah AI Developer Agent yang berjalan di terminal Ubuntu/Termux, terhubung ke GitHub.
Direktori kerja saat ini: {CWD}
Kamu bisa:
- Membaca, menulis, mengedit file.
- Menjalankan perintah shell (npm init, git init, dll).
- Membuat struktur proyek lengkap.
- Membuat repo GitHub dan push semua perubahan.
- Melanjutkan pengembangan proyek: clone repo, edit, commit, push.
PENTING: Untuk membuat proyek baru:
1. Buat folder proyek dengan change_directory.
2. Inisialisasi proyek: npm init -y, git init, dll.
3. Tulis semua file yang diperlukan.
4. Buat repo GitHub, lalu hubungkan remote dengan git_init_and_set_remote.
5. Commit dan push dengan github_push_changes.
Gunakan bahasa Indonesia yang ramah."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    console.print(Panel.fit(
        "[bold cyan]● AI Agent Ultimate[/]\n"
        f"Penyedia: [yellow]{os.getenv('API_PROVIDER', '')}[/]  •  Model: [yellow]{model}[/]  •  GitHub: {'✅' if check_github_connection() else '❌'}",
        border_style="bright_blue"
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]▸[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Keluar.[/]")
            break
        if user_input.lower() in ["exit", "quit", "keluar"]:
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                if msg.content:
                    console.print(Panel(Markdown(msg.content), title="🤖 AI", border_style="green"))
                break

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                console.print(f"[dim]🔧 Menjalankan [bold]{func_name}[/]...[/]")
                func = tool_map.get(func_name)
                if func:
                    try:
                        result = func(**args)
                    except Exception as e:
                        result = f"ERROR: {e}"
                else:
                    result = "ERROR: Tool tidak dikenal."
                panel = Panel(
                    Syntax(str(result), "text", theme="monokai", word_wrap=True),
                    title=f"📤 {func_name}",
                    border_style="yellow"
                )
                console.print(panel)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": str(result)
                })

if __name__ == "__main__":
    run_agent()
