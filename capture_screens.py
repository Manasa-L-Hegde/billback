import subprocess
import time
import sys
import os
from pathlib import Path

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UVICORN_EXE = r".venv\Scripts\uvicorn.exe"
SCREENS_DIR = Path("samples/screens")
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from reset_demo import reset_demo

reset_demo()

print("1. Starting Uvicorn background server on port 8088...")
proc = subprocess.Popen([UVICORN_EXE, "server:app", "--port", "8088", "--host", "127.0.0.1"])
time.sleep(3)

def capture_url(url, output_path):
    print(f"[*] Capturing {url} -> {output_path}...")
    abs_out = str(Path(output_path).resolve())
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir=c:\\temp\\edge_shot_data",
        "--virtual-time-budget=4000",
        f"--screenshot={abs_out}",
        "--window-size=1280,850",
        url
    ]
    subprocess.run(cmd, timeout=25)
    if Path(abs_out).exists():
        size = Path(abs_out).stat().st_size
        print(f"    Saved {abs_out} ({size} bytes)")
    else:
        print(f"    [!] Failed to save {abs_out}")

try:
    # 1. Empty state
    capture_url("http://127.0.0.1:8088/", SCREENS_DIR / "empty_state.png")

    # 2. Needs review card (hck.jpeg)
    capture_url("http://127.0.0.1:8088/?demo_preview=needs_review", SCREENS_DIR / "needs_review_hck.png")

    # 3. Invoice-only audit with skipped chips
    capture_url("http://127.0.0.1:8088/?demo_preview=invoice_only", SCREENS_DIR / "invoice_only_skipped_chips.png")

finally:
    print("Terminating uvicorn server...")
    proc.terminate()
    proc.wait()
    print("Uvicorn terminated.")
