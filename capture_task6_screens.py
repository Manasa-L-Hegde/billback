import subprocess
import time
import sys
import os
import urllib.request
from pathlib import Path

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UVICORN_EXE = r".venv\Scripts\uvicorn.exe"
SCREENS_DIR = Path("samples/screens")
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print("=" * 80)
print(" CAPTURING TASK 6 HIGH-RES SCREENSHOTS (1920x1080 100% Zoom) ")
print("=" * 80)

port = 8092
print(f"1. Starting Uvicorn background server on port {port}...")
proc = subprocess.Popen([UVICORN_EXE, "server:app", "--port", str(port), "--host", "127.0.0.1"])

# Wait for server readiness
for _ in range(30):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            if resp.status == 200:
                print("Server is ready and responding.")
                break
    except Exception:
        time.sleep(0.5)

def capture(url, output_path, width=1920, height=1080):
    abs_out = str(Path(output_path).resolve())
    print(f"[*] Capturing ({width}x{height}) {url} -> {output_path}...")
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir=c:\\temp\\edge_task6_data",
        "--virtual-time-budget=4000",
        f"--screenshot={abs_out}",
        f"--window-size={width},{height}",
        url
    ]
    subprocess.run(cmd, timeout=40)
    if Path(abs_out).exists():
        size = Path(abs_out).stat().st_size
        print(f"    [+] Saved {abs_out} ({size} bytes)")
        return True, size
    else:
        print(f"    [!] Failed to save {abs_out}")
        return False, 0

try:
    # 1. Demo case settled (email + vendor thread + outcome) at 1920x1080
    success1, size1 = capture(f"http://127.0.0.1:{port}/?demo_preview=demo_settled", SCREENS_DIR / "demo_case_settled_1920x1080.png", 1920, 1080)

    # 2. Deny run ending in escalation at 1920x1080
    success2, size2 = capture(f"http://127.0.0.1:{port}/?demo_preview=deny_escalated", SCREENS_DIR / "deny_escalated_1920x1080.png", 1920, 1080)

    print("\nSummary:")
    print(f"  demo_case_settled_1920x1080.png : {'SUCCESS' if success1 else 'FAIL'} ({size1} bytes)")
    print(f"  deny_escalated_1920x1080.png    : {'SUCCESS' if success2 else 'FAIL'} ({size2} bytes)")

finally:
    print("Terminating server...")
    proc.terminate()
    proc.wait()
    print("Server terminated.")

