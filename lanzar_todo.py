#!/usr/bin/env python3
"""Inicia y supervisa los servicios locales de Kula Balam y Monitor del Mercado."""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


TRADING_ROOT = Path(__file__).resolve().parent


def _resolve_monitor_root() -> Path:
    env_dir = os.environ.get("MONITOR_PROJECT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    for candidate_name in ("monitor del mercado", "monitor_del_mercado"):
        candidate = TRADING_ROOT.parent / candidate_name
        if candidate.is_dir():
            return candidate.resolve()
    return (TRADING_ROOT.parent / "monitor del mercado").resolve()


MONITOR_ROOT = _resolve_monitor_root()
STOP_REQUESTED = False
CHILDREN: list[subprocess.Popen] = []


def request_ok(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def port_is_occupied(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def ensure_free_ports() -> None:
    for port in (18767, 18087, 8520, 8000):
        if not port_is_occupied(port):
            continue
        if os.name == "nt":
            try:
                output = subprocess.check_output(["netstat", "-ano"], text=True)
                for line in output.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and parts[0] == "TCP" and parts[1].endswith(f":{port}"):
                        pid = int(parts[4])
                        if pid > 0 and pid != os.getpid():
                            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            except Exception:
                pass
        else:
            try:
                subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
            except Exception:
                pass
        freed = False
        for _ in range(6):
            time.sleep(0.5)
            if not port_is_occupied(port):
                freed = True
                break
        if not freed and port_is_occupied(port):
            raise RuntimeError(
                f"El puerto {port} sigue ocupado tras intentar liberarlo automáticamente."
            )


def python_for(project: Path) -> Path:
    executable = project / ("venv" if project == TRADING_ROOT else ".venv")
    executable /= "Scripts/python.exe" if os.name == "nt" else "bin/python"
    if not executable.is_file():
        raise RuntimeError(f"No se encontró el intérprete del proyecto: {executable}")
    return executable


def start_child(command: list[str], cwd: Path, name: str) -> subprocess.Popen:
    print(f"Iniciando {name}...", flush=True)
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(command, cwd=cwd, env=child_env)
    CHILDREN.append(process)
    time.sleep(0.2)
    if process.poll() is not None:
        raise RuntimeError(f"{name} terminó durante el arranque (código {process.returncode}).")
    return process


def monitor_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["KULA_BALAM_PROJECT_DIR"] = str(TRADING_ROOT)
    env["TRADING_OLLAMA_PROJECT_DIR"] = str(TRADING_ROOT)
    try:
        from dotenv import dotenv_values

        trading_config = dotenv_values(TRADING_ROOT / ".env")
    except ImportError:
        trading_config = {}
    token = (
        env.get("KULA_BALAM_API_TOKEN")
        or env.get("TRADING_OLLAMA_API_TOKEN")
        or trading_config.get("APP_SECRET_TOKEN")
        or trading_config.get("APP_TOKEN")
        or ""
    )
    env["MONITOR_NO_BROWSER"] = "1"
    if token:
        env["KULA_BALAM_API_TOKEN"] = str(token)
        env["TRADING_OLLAMA_API_TOKEN"] = str(token)
    return env


def is_ollama_alive(timeout: float = 1.0) -> bool:
    for endpoint in (
        "http://localhost:11434/api/version",
        "http://localhost:11434/",
        "http://localhost:11434/api/tags",
    ):
        if request_ok(endpoint, timeout=timeout):
            return True
    return False


def ensure_ollama_running() -> None:
    if is_ollama_alive(timeout=1.5):
        return
    import shutil
    ollama_bin = shutil.which("ollama")
    if ollama_bin:
        print("Iniciando servicio de Ollama...", flush=True)
        try:
            subprocess.Popen([ollama_bin, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(20):
                time.sleep(0.5)
                if is_ollama_alive(timeout=1.0):
                    print("Ollama iniciado correctamente.", flush=True)
                    return
        except Exception:
            pass
    print(
        "⚠️ ADVERTENCIA: Ollama local no respondió en localhost:11434. "
        "Continuando con motores en la nube (Gemini / Antigravity).",
        flush=True,
    )


def start_monitor(command: list[str], cwd: Path, name: str) -> subprocess.Popen:
    print(f"Iniciando {name}...", flush=True)
    process = subprocess.Popen(command, cwd=cwd, env=monitor_environment())
    CHILDREN.append(process)
    time.sleep(0.2)
    if process.poll() is not None:
        raise RuntimeError(f"{name} terminó durante el arranque (código {process.returncode}).")
    return process


def wait_for_health(url: str, name: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline and not STOP_REQUESTED:
        if process.poll() is not None:
            raise RuntimeError(f"{name} terminó antes de responder HTTP 200.")
        if request_ok(url):
            print(f"{name}: HTTP 200 en {url}", flush=True)
            return
        time.sleep(0.5)
    if STOP_REQUESTED:
        return
    raise RuntimeError(f"Tiempo agotado esperando HTTP 200 de {name}: {url}")


def stop_children() -> None:
    for process in reversed(CHILDREN):
        if process.poll() is None:
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
                except Exception:
                    pass
            else:
                process.terminate()
    for process in reversed(CHILDREN):
        if process.poll() is None:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def request_stop(_signum, _frame) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def main() -> int:
    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, request_stop)

    try:
        if not MONITOR_ROOT.is_dir():
            raise RuntimeError(
                f"No se encontró Monitor del Mercado en {MONITOR_ROOT}. "
                "Define MONITOR_PROJECT_DIR si está en otra ubicación."
            )
        ensure_ollama_running()
        ensure_free_ports()

        trading_python = python_for(TRADING_ROOT)
        monitor_python = python_for(MONITOR_ROOT)
        backend = start_child(
            [
                str(trading_python),
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18767",
                "--reload",
                "--reload-dir",
                "backend",
                "--reload-exclude",
                "venv",
                "--reload-exclude",
                "*.sqlite3",
                "--reload-exclude",
                "*.csv",
            ],
            TRADING_ROOT,
            "backend Kula Balam",
        )
        frontend = start_child(
            [str(trading_python), "-m", "http.server", "18087", "--bind", "127.0.0.1", "--directory", str(TRADING_ROOT / "frontend")],
            TRADING_ROOT,
            "frontend Kula Balam",
        )
        monitor = start_monitor(
            [str(monitor_python), "main.py", "--dashboard", "--port", "8520"],
            MONITOR_ROOT,
            "Monitor del Mercado",
        )
        lab = start_child(
            [
                str(trading_python),
                "-m",
                "uvicorn",
                "server:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--reload",
            ],
            TRADING_ROOT / "backtest_lab",
            "Backtest Lab",
        )

        wait_for_health("http://127.0.0.1:18767/", "Backend Kula Balam", backend)
        wait_for_health("http://127.0.0.1:18087/", "Frontend Kula Balam", frontend)
        wait_for_health("http://127.0.0.1:8520/", "Monitor del Mercado", monitor)
        wait_for_health("http://127.0.0.1:8000/", "Backtest Lab", lab)
        if STOP_REQUESTED:
            return 0

        webbrowser.open_new_tab("http://127.0.0.1:18087/")
        time.sleep(0.4)
        webbrowser.open_new_tab("http://127.0.0.1:8520/")
        time.sleep(0.4)
        webbrowser.open_new_tab("http://127.0.0.1:8000/")
        print("Sistemas disponibles. Presiona Ctrl+C para detener solo los procesos iniciados aquí.", flush=True)
        while not STOP_REQUESTED:
            for name, process in (
                ("backend Kula Balam", backend),
                ("frontend Kula Balam", frontend),
                ("Monitor del Mercado", monitor),
                ("Backtest Lab", lab),
            ):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} terminó inesperadamente (código {process.returncode}).")
            time.sleep(0.5)
        return 0
    except Exception as exc:
        print(f"Error al iniciar el sistema integrado: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_children()


if __name__ == "__main__":
    raise SystemExit(main())
