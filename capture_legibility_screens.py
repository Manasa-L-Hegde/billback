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

print("=" * 70)
print(" CAPTURING LEGIBILITY & ERROR VERIFICATION SCREENSHOTS ")
print("=" * 70)

# Start background server on port 8089
port = 8089
env = os.environ.copy()
print(f"1. Starting Uvicorn background server on port {port}...")
proc = subprocess.Popen([UVICORN_EXE, "server:app", "--port", str(port), "--host", "127.0.0.1"], env=env)

# Wait for server readiness
for _ in range(30):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            if resp.status == 200:
                print("Server is ready and responding.")
                break
    except Exception:
        time.sleep(0.5)

def capture(url, output_path, width, height):
    abs_out = str(Path(output_path).resolve())
    print(f"[*] Capturing ({width}x{height}) {url} -> {output_path}...")
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir=c:\\temp\\edge_legibility_data",
        "--virtual-time-budget=3000",
        f"--screenshot={abs_out}",
        f"--window-size={width},{height}",
        url
    ]
    subprocess.run(cmd, timeout=40)
    if Path(abs_out).exists():
        size = Path(abs_out).stat().st_size
        print(f"    [+] Saved {abs_out} ({size} bytes)")
    else:
        print(f"    [!] Failed to save {abs_out}")

try:
    # 1. 1920x1080 (100% desktop zoom)
    capture(f"http://127.0.0.1:{port}/", SCREENS_DIR / "legibility_1920x1080.png", 1920, 1080)

    # 2. 1280x720 (standard HD video)
    capture(f"http://127.0.0.1:{port}/", SCREENS_DIR / "legibility_1280x720.png", 1280, 720)

    # 3. 390px (mobile viewport)
    capture(f"http://127.0.0.1:{port}/", SCREENS_DIR / "legibility_390px.png", 390, 844)

finally:
    print("Terminating server...")
    proc.terminate()
    proc.wait()
    print("Done.")
