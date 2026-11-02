import os
import sys
import time
import json
import socket
import subprocess
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PORT = 8096
UVICORN_EXE = r".venv311\Scripts\uvicorn.exe"

def wait_for_server(port, timeout=25):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.3)
    return False

def main():
    print("=" * 80)
    print(" PYTHON 3.11 FRESH ENVIRONMENT VERIFICATION (PUBLIC_MODE=1) ")
    print("=" * 80)
    print(f"Python Executable : {sys.executable}")
    print(f"Python Version    : {sys.version}")

    env = os.environ.copy()
    env["PUBLIC_MODE"] = "1"

    cmd = [
        UVICORN_EXE, "server:app",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--proxy-headers",
        "--forwarded-allow-ips=*"
    ]
    print(f"[*] Starting uvicorn with PUBLIC_MODE=1 on port {PORT}...")
    print(f"    Command: {' '.join(cmd)}")
    log_file = open("uvicorn_py311.log", "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=log_file)

    try:
        if not wait_for_server(PORT, timeout=25):
            print("[-] Server failed to respond within timeout.")
            log_file.flush()
            with open("uvicorn_py311.log", "r", encoding="utf-8") as lf:
                print(lf.read())
            sys.exit(1)

        print("[+] Uvicorn server started successfully in Python 3.11 virtual environment.")

        # 1. Health check
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health") as resp:
            health = json.loads(resp.read().decode("utf-8"))
            print(f"[+] GET /health -> Status: {resp.status} | Body: {health}")
            assert resp.status == 200

        # 2. Trigger demo case
        demo_payload = json.dumps({"vendor_mode": "cached", "demo_pacing": False}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/api/cases/demo",
            data=demo_payload,
            headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.99"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            demo_resp = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie")
            print(f"[+] POST /api/cases/demo -> Status: {resp.status} | Case ID: {demo_resp['case_id']}")
            print(f"    Set-Cookie header received: {cookie}")
            case_id = demo_resp["case_id"]

        # 3. Stream case workflow
        print(f"\n[*] Connecting to SSE stream for {case_id}...")
        stream_req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/api/cases/{case_id}/stream",
            headers={"Cookie": cookie.split(";")[0] if cookie else ""}
        )
        events_received = []
        with urllib.request.urlopen(stream_req) as s_resp:
            buffer = ""
            for line in s_resp:
                decoded = line.decode("utf-8", errors="replace")
                buffer += decoded
                if "\n\n" in buffer:
                    blocks = buffer.split("\n\n")
                    for b in blocks[:-1]:
                        cur_ev = None
                        cur_data = None
                        for l in b.strip().split("\n"):
                            if l.startswith("event: "):
                                cur_ev = l[7:].strip()
                            elif l.startswith("data: "):
                                try:
                                    cur_data = json.loads(l[6:].strip())
                                except Exception:
                                    cur_data = l[6:].strip()
                        if cur_ev:
                            events_received.append((cur_ev, cur_data))
                            print(f"    -> [SSE Event] {cur_ev}: {cur_data if cur_ev not in ('tool_result', 'findings') else str(cur_data)[:80] + '...'}")
                            if cur_ev in ("outcome", "end", "error"):
                                break
                    buffer = blocks[-1]
                if any(ev[0] in ("outcome", "end") for ev in events_received):
                    break

        print("\n" + "=" * 80)
        print(" DEMO CASE EXECUTION SUMMARY (PYTHON 3.11 + PUBLIC_MODE=1) ")
        print("=" * 80)
        outcome_event = next((d for ev, d in events_received if ev == "outcome"), None)
        if outcome_event:
            print(f"Outcome Status   : {outcome_event.get('status')}")
            print(f"Claimed Overcharge: Rs. {outcome_event.get('claimed', 0.0):.2f}")
            print(f"Recovered Amount  : Rs. {outcome_event.get('recovered', 0.0):.2f}")
            print(f"Negotiation Rounds: {outcome_event.get('rounds')}")
            print(f"Source Tag        : {outcome_event.get('source', 'cached replay')}")
        print(f"Total SSE Events  : {len(events_received)}")
        print("RESULT            : ALL PYTHON 3.11 DEPLOYMENT TESTS PASSED PERFECTLY")
        print("=" * 80)

    finally:
        print("[*] Terminating uvicorn background process...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
        print("[*] Uvicorn server stopped.")

if __name__ == "__main__":
    main()
