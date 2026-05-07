#!/usr/bin/env python3
"""
AI Agent Ultimate – Multi-Provider + Setup Wizard + Clear Screen + Cancel + Retry Koneksi
Mendukung OpenAI, OpenRouter, Custom API. GitHub via gh CLI.
"""

import os, sys, subprocess, json, time
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter, Retry
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm
import git
from dotenv import load_dotenv, set_key

console = Console()
ENV_FILE = Path(__file__).parent / ".env"
CWD = Path.cwd()

# ==================== SETUP WIZARD ====================
def run_setup():
    console.print(Panel.fit(
        "[bold cyan]🛠️  AI Agent Setup Wizard[/]\n"
        "[dim]Konfigurasi multi‑API, cukup sekali.[/]",
        border_style="bright_blue"
    ))

    # 1. Provider
    console.print("\n[bold]1️⃣  Pilih Penyedia API[/]")
    providers = {
        "1": {"name": "OpenAI", "base": "https://api.openai.com/v1", "key_link": "https://platform.openai.com/api-keys"},
        "2": {"name": "OpenRouter (akses Google, Meta, dll.)", "base": "https://openrouter.ai/api/v1", "key_link": "https://openrouter.ai/keys"},
        "3": {"name": "Custom (base URL sendiri)", "base": "", "key_link": ""}
    }
    for k, p in providers.items():
        console.print(f"  [dim]{k}.[/] {p['name']}")
    choice = Prompt.ask("Pilih nomor", choices=list(providers.keys()), default="2")
    provider = providers[choice]

    console.print(f"\n[bold]2️⃣  API Key {provider['name']}[/]")
    if provider["key_link"]:
        console.print(f"🔗 Dapatkan: [underline blue]{provider['key_link']}[/]")
    api_key = Prompt.ask("Masukkan API key", password=True)
    set_key(ENV_FILE, "API_KEY", api_key)
    set_key(ENV_FILE, "API_PROVIDER", provider["name"])

    if choice == "3":
        base_url = Prompt.ask("Masukkan base URL (contoh: https://api.mistral.ai/v1)")
        set_key(ENV_FILE, "API_BASE_URL", base_url)
    else:
        set_key(ENV_FILE, "API_BASE_URL", provider["base"])

    # 3. Model
    console.print("\n[bold]3️⃣  Pilih Model AI[/]")
    if choice == "1":
        models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "Custom"]
    elif choice == "2":
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
    model_choice = Prompt.ask("Pilih nomor", choices=[str(i) for i in range(1, len(models)+1)], default="1")
    if models[int(model_choice)-1] == "Custom":
        model = Prompt.ask("Masukkan ID model")
    else:
        model = models[int(model_choice)-1]
    set_key(ENV_FILE, "MODEL", model)

    # 4. GitHub
    console.print("\n[bold]4️⃣  Koneksi GitHub[/]")
    try:
        subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        console.print("[green]✓ gh CLI sudah login.[/]")
    except:
        console.print("[yellow]⚠ Jalankan 'gh auth login' untuk fitur GitHub.[/]")

    # 5. Working directory
    console.print("\n[bold]5️⃣  Direktori Kerja (opsional)[/]")
    custom_dir = Prompt.ask("Path (kosongkan = direktori ini)")
    if custom_dir.strip():
        set_key(ENV_FILE, "WORK_DIR", custom_dir)

    console.print(Panel.fit("[bold green]✅ Setup selesai![/]", border_style="green"))

# ==================== LOAD CONFIG ====================
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

# ==================== API CLIENT ====================
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

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    for attempt in range(max_retries):
        try:
            resp = session.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {resp.text}"}
            return resp.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            if attempt < max_retries - 1:
                console.print(f"[yellow]⚠ Koneksi terputus, mengulangi ({attempt+2}/{max_retries})...[/]")
                time.sleep(2 ** attempt)
            else:
                return {"error": f"Koneksi gagal setelah {max_retries}x: {e}"}
        except Exception as e:
            return {"error": f"Error: {e}"}
    return {"error": "Gagal tidak diketahui"}

# ==================== GITHUB VIA gh CLI ====================
def check_github():
    try:
        subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        console.print("[green]✓ GitHub Ready[/]")
        return True
    except:
        console.print("[yellow]⚠ GitHub belum login[/]")
        return False

def github_create_repo(name: str, private: bool = False, description: str = "") -> str:
    try:
        cmd = ["gh", "repo", "create", name, "--push"]
        if private:
            cmd.append("--private")
        else:
            cmd.append("--public")
        if description:
            cmd.extend(["-d", description])
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=CWD)
        return result.stdout.strip() or f"Repo {name} dibuat di GitHub."
    except Exception as e:
        return f"ERROR: {e}"

def github_push(commit_msg: str = "Update from AI Agent") -> str:
    try:
        repo = git.Repo(CWD)
        if repo.is_dirty(untracked_files=True):
            repo.git.add(A=True)
            repo.index.commit(commit_msg)
            subprocess.run(["git", "push", "origin", "HEAD"], check=True, capture_output=True, cwd=CWD)
            return f"✅ Pushed: {commit_msg}"
        return "Tidak ada perubahan."
    except Exception as e:
        return f"ERROR: {e}"

def github_clone(repo_url: str, target_dir: str = "") -> str:
    try:
        cmd = ["gh", "repo", "clone", repo_url]
        if target_dir:
            cmd.append(target_dir)
        subprocess.run(cmd, check=True, capture_output=True, cwd=CWD)
        return f"Repo {repo_url} berhasil di-clone."
    except Exception as e:
        return f"ERROR: {e}"

# ==================== TOOLS ====================
def change_directory(path: str) -> str:
    global CWD
    try:
        new_path = (CWD / path).resolve()
        if not new_path.is_dir():
            return f"ERROR: {path} bukan direktori."
        os.chdir(new_path)
        CWD = new_path
        return f"Pindah ke: {CWD}"
    except Exception as e:
        return f"ERROR: {e}"

def list_directory(path: str = ".") -> str:
    target = (CWD / path).resolve()
    if not target.is_dir():
        return f"ERROR: {path} bukan direktori."
    items = os.listdir(target)
    dirs = [d for d in items if (target / d).is_dir()]
    files = [f for f in items if (target / f).is_file()]
    return ("[DIR] " + ", ".join(dirs) + "\n" if dirs else "") + ("[FILE] " + ", ".join(files) if files else "Kosong")

def shell_command(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=CWD)
        return (result.stdout + result.stderr).strip() or "(ok)"
    except Exception as e:
        return f"ERROR: {e}"

def read_file(path: str) -> str:
    full_path = (CWD / path).resolve()
    return full_path.read_text() if full_path.is_file() else f"ERROR: {path} tidak ditemukan."

def write_file(path: str, content: str) -> str:
    full_path = (CWD / path).resolve()
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    return f"✅ {path} ditulis ({len(content)} karakter)."

def edit_file(path: str, old_str: str, new_str: str) -> str:
    full_path = (CWD / path).resolve()
    if not full_path.is_file():
        return f"ERROR: {path} tidak ditemukan."
    text = full_path.read_text()
    if old_str not in text:
        return f"ERROR: string tidak ditemukan."
    full_path.write_text(text.replace(old_str, new_str, 1))
    return f"✅ {path} diedit."

tools_spec = [
    {"type": "function", "function": {"name": "change_directory", "description": "Pindah direktori.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_directory", "description": "Lihat isi direktori.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}}},
    {"type": "function", "function": {"name": "shell_command", "description": "Jalankan perintah shell.", "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Baca file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Tulis file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Edit file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}}, "required": ["path", "old_str", "new_str"]}}},
    {"type": "function", "function": {"name": "github_create_repo", "description": "Buat repo GitHub.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "private": {"type": "boolean", "default": False}, "description": {"type": "string", "default": ""}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "github_push", "description": "Push perubahan ke GitHub.", "parameters": {"type": "object", "properties": {"commit_msg": {"type": "string", "default": "Update from AI Agent"}}}}},
    {"type": "function", "function": {"name": "github_clone", "description": "Clone repo GitHub.", "parameters": {"type": "object", "properties": {"repo_url": {"type": "string"}, "target_dir": {"type": "string", "default": ""}}, "required": ["repo_url"]}}}
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
    "github_clone": github_clone
}

# ==================== MAIN LOOP ====================
def run_agent():
    load_config()
    model = os.getenv("MODEL", "meta-llama/llama-3.1-70b-instruct")

    SYSTEM_PROMPT = f"""Kamu AI Developer Agent di Termux. Dir: {CWD}
Tools: baca/tulis/edit file, shell cmd, GitHub via gh CLI.
Buat proyek: buat folder → init → tulis file → buat repo GitHub → push.
Gunakan bahasa Indonesia ramah."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    os.system('clear')

    console.print(Panel.fit(
        f"[bold cyan]● AI Agent Ultimate[/]\nProvider: {os.getenv('API_PROVIDER')} | Model: {model} | GitHub: {'✅' if check_github() else '❌'}\n[dim]Ctrl+C untuk membatalkan aksi[/]",
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
            try:
                response = chat_completion(messages, tools_spec)
            except KeyboardInterrupt:
                console.print("\n[dim]⚠ Dibatalkan sebelum respons diterima.[/]")
                messages.pop()
                break

            if "error" in response:
                console.print(f"[red]{response['error']}[/]")
                break

            msg = response["choices"][0]["message"]
            messages.append(msg)

            if "tool_calls" not in msg:
                if msg.get("content"):
                    console.print(Panel(Markdown(msg["content"]), title="🤖 AI", border_style="green"))
                break

            for tc in msg["tool_calls"]:
                func_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                console.print(f"[dim]🔧 Menjalankan [bold]{func_name}[/]...[/] (Ctrl+C untuk batal)")

                try:
                    func = tool_map.get(func_name)
                    if func:
                        result = func(**args)
                    else:
                        result = "Tool tidak dikenal."
                except KeyboardInterrupt:
                    console.print(f"[yellow]⚠ Tool {func_name} dibatalkan.[/]")
                    result = f"DIBATALKAN: {func_name} tidak selesai."

                console.print(Panel(Syntax(str(result), "text", theme="monokai"), title=f"📤 {func_name}", border_style="yellow"))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": str(result)
                })

if __name__ == "__main__":
    run_agent()
