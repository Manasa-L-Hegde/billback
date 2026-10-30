import subprocess, time, sys, os
from pathlib import Path

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UVICORN_EXE = r".venv\Scripts\uvicorn.exe"

os.makedirs("screenshots", exist_ok=True)

print("1. Starting Uvicorn server...")
proc = subprocess.Popen([UVICORN_EXE, "server:app", "--port", "8000", "--host", "127.0.0.1"])
time.sleep(3)

try:
    print("\n2. Capturing Empty State Screenshot...")
    subprocess.run([
        EDGE_PATH, "--headless", "--disable-gpu",
        "--screenshot=screenshots/1_empty_state.png",
        "--window-size=1280,850",
        "http://127.0.0.1:8000/"
    ], timeout=15)
    print("Saved screenshots/1_empty_state.png")

    print("\n3. Triggering Demo Case...")
    import urllib.request, json
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/cases/demo",
        data=json.dumps({"vendor_mode": "partial_50", "min_accept_percent": 80.0, "autonomous": True}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        case_info = json.loads(resp.read().decode())
    case_id = case_info["case_id"]
    print("Created demo case:", case_id)

    # In the browser, navigate to the active case session or simulate it
    # Let's open the page with the demo case triggered
    time.sleep(2)
    print("\n4. Capturing Mid-Run Screenshot...")
    subprocess.run([
        EDGE_PATH, "--headless", "--disable-gpu",
        "--screenshot=screenshots/2_mid_run.png",
        "--window-size=1280,850",
        "http://127.0.0.1:8000/"
    ], timeout=15)
    print("Saved screenshots/2_mid_run.png")

    # Wait for case completion via SSE stream
    print("\n5. Streaming case to completion...")
    req_stream = urllib.request.Request(f"http://127.0.0.1:8000/api/cases/{case_id}/stream")
    with urllib.request.urlopen(req_stream, timeout=45) as stream_resp:
        for line in stream_resp:
            l = line.decode('utf-8', errors='ignore').strip()
            if l.startswith("event: outcome") or l.startswith("event: end"):
                print("Encountered:", l)
                break

    time.sleep(2)
    print("\n6. Capturing Settled State Screenshot...")
    subprocess.run([
        EDGE_PATH, "--headless", "--disable-gpu",
        "--screenshot=screenshots/3_settled_outcome.png",
        "--window-size=1280,850",
        "http://127.0.0.1:8000/"
    ], timeout=15)
    print("Saved screenshots/3_settled_outcome.png")

finally:
    print("\nStopping uvicorn process...")
    proc.terminate()
    proc.wait()

print("\nScreenshot capture process completed.")

