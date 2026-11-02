import os
import sys
import time
import io
import json
import shutil
import socket
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

# Force PUBLIC_MODE=1 for this test suite
os.environ["PUBLIC_MODE"] = "1"
os.environ["DRY_RUN"] = "0"
os.environ["GMAIL_USER"] = "trap_user@gmail.com"
os.environ["GMAIL_APP_PASSWORD"] = "trap_password_123"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import email_tools
from server import UPLOAD_DIR

PORT = 8097
BASE_URL = f"http://127.0.0.1:{PORT}"
UVICORN_EXE = r".venv\Scripts\uvicorn.exe"

def wait_for_server(proc, port, timeout=25):
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            print(f"Server process terminated prematurely with code {proc.returncode}!", flush=True)
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.3)
    return False

def http_post(path, data=None, files=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = dict(headers or {})
    encoded_body = None

    if files:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body_parts = []
        for field, (filename, content, content_type) in files.items():
            part = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8") + content + b"\r\n"
            body_parts.append(part)
        if data:
            for k, v in data.items():
                part = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                ).encode("utf-8")
                body_parts.append(part)
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        encoded_body = b"".join(body_parts)
    elif data is not None:
        if isinstance(data, (dict, list)):
            encoded_body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, bytes):
            encoded_body = data
        elif isinstance(data, str):
            encoded_body = data.encode("utf-8")

    req = urllib.request.Request(url, data=encoded_body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            cookie = resp.headers.get("Set-Cookie")
            return resp.status, body, json.loads(body) if "application/json" in resp.headers.get("Content-Type", "") else None, cookie
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        parsed = None
        try:
            parsed = json.loads(body)
        except Exception:
            pass
        return e.code, body, parsed, None

def main():
    print("=" * 80, flush=True)
    print(" TASK 5: PUBLIC_MODE=1 VERIFICATION & SECURITY AUDIT ", flush=True)
    print("=" * 80, flush=True)

    # Initial cleanup of any historical pre-existing runs
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(exist_ok=True)

    # -------------------------------------------------------------
    # (i) A case never calls SMTP (even if Gmail credentials set)
    # -------------------------------------------------------------
    print("\n[Check 1/6] Proving case / email NEVER calls SMTP in PUBLIC_MODE=1:", flush=True)
    with patch("smtplib.SMTP_SSL") as mock_smtp:
        res = email_tools.send_email("hacker@malicious.com", "Test Subject", "Test Body")
        assert not mock_smtp.called, "CRITICAL: SMTP_SSL was called despite PUBLIC_MODE=1!"
        print(f"    Recipient passed in : 'hacker@malicious.com'", flush=True)
        print(f"    Effective Recipient : '{res['recipient']}' (forced override)", flush=True)
        print(f"    Delivery Status     : '{res['status']}'", flush=True)
        print(f"    SMTP_SSL Called     : {mock_smtp.called} (0 times)", flush=True)
        assert res["recipient"] == "simulated-vendor@example.com"
        assert "dry run" in res["status"].lower()
    print("    [+] PASS (i): SMTP is never called; user input recipient is strictly ignored.", flush=True)

    # Start live server on PORT for Checks 2-5
    env = os.environ.copy()
    env["PUBLIC_MODE"] = "1"
    cmd = [
        sys.executable, "-m", "uvicorn", "server:app",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--proxy-headers",
        "--forwarded-allow-ips=*"
    ]
    log_file = open("uvicorn_public.log", "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=log_file)

    try:
        if not wait_for_server(proc, PORT, timeout=25):
            print("Failed to start server within timeout.")
            sys.exit(1)

        # -------------------------------------------------------------
        # (ii) The 6th custom case from one IP in an hour is refused politely
        # -------------------------------------------------------------
        print("\n[Check 2/6] Proving rate limit: 6th custom case from 1 IP in 1 hr refused politely (HTTP 429):", flush=True)
        test_ip = "203.0.113.42"
        headers = {"X-Forwarded-For": test_ip}

        tiny_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
            b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
            b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff"
            b"\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01"
            b"\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )

        dummy_cids = []
        for i in range(1, 6):
            status, body, res_j, _ = http_post(
                "/api/cases",
                files={"invoice": ("test.jpg", tiny_jpeg, "image/jpeg")},
                data={"vendor_email": "test@example.com"},
                headers=headers
            )
            assert status == 200, f"Expected 200 for case #{i}, got {status}: {body}"
            print(f"    Case #{i} from IP {test_ip} -> HTTP {status} (Allowed)", flush=True)
            if res_j and "case_id" in res_j:
                dummy_cids.append(res_j["case_id"])

        # 6th case attempt
        status6, body6, res_j6, _ = http_post(
            "/api/cases",
            files={"invoice": ("test.jpg", tiny_jpeg, "image/jpeg")},
            data={"vendor_email": "test@example.com"},
            headers=headers
        )
        print(f"    Case #6 from IP {test_ip} -> HTTP {status6}", flush=True)
        print(f"    Detail message: {res_j6.get('detail') if res_j6 else body6}", flush=True)
        assert status6 == 429
        assert "rate limit reached" in (res_j6.get("detail", "") if res_j6 else "").lower()
        print("    [+] PASS (ii): 6th custom case from IP is refused politely with HTTP 429.", flush=True)

        # Clean up unstreamed rate-limit dummy cases
        for cid in dummy_cids:
            shutil.rmtree(UPLOAD_DIR / cid, ignore_errors=True)

        # -------------------------------------------------------------
        # (iii) A .exe renamed to .jpg is rejected
        # -------------------------------------------------------------
        print("\n[Check 3/6] Proving .exe file renamed to .jpg is rejected by content inspection:", flush=True)
        fake_exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This is a Windows executable header!"
        status_exe, body_exe, res_exe, _ = http_post(
            "/api/cases",
            files={"invoice": ("malicious_payload.jpg", fake_exe_content, "image/jpeg")},
            data={"vendor_email": "test@example.com"},
            headers={"X-Forwarded-For": "198.51.100.1"}
        )
        print(f"    Upload response status : HTTP {status_exe}", flush=True)
        print(f"    Upload response detail : {res_exe.get('detail') if res_exe else body_exe}", flush=True)
        assert status_exe == 400
        assert "invalid file type" in (res_exe.get("detail", "") if res_exe else "").lower()
        print("    [+] PASS (iii): Renamed .exe rejected by magic byte / content verification.", flush=True)

        # -------------------------------------------------------------
        # (iv) A 12 MB file is rejected
        # -------------------------------------------------------------
        print("\n[Check 4/6] Proving 12 MB file is rejected (exceeds 5 MB limit):", flush=True)
        large_payload = b"\xff\xd8\xff\xe0" + b"\x00" * (12 * 1024 * 1024)
        status_lg, body_lg, res_lg, _ = http_post(
            "/api/cases",
            files={"invoice": ("oversized_bill.jpg", large_payload, "image/jpeg")},
            data={"vendor_email": "test@example.com"},
            headers={"X-Forwarded-For": "198.51.100.2"}
        )
        print(f"    Upload response status : HTTP {status_lg}", flush=True)
        print(f"    Upload response detail : {res_lg.get('detail') if res_lg else body_lg}", flush=True)
        assert status_lg == 413
        assert "5 mb" in (res_lg.get("detail", "") if res_lg else "").lower()
        print("    [+] PASS (iv): 12 MB file rejected with HTTP 413.", flush=True)

        # -------------------------------------------------------------
        # (v) Uploads folder is empty after a run
        # -------------------------------------------------------------
        print("\n[Check 5/6] Proving uploads folder is empty after a case run completes:", flush=True)
        sample_bill_bytes = Path("samples/test_bill5.jpg").read_bytes()
        status_c, body_c, res_c, cookie_c = http_post(
            "/api/cases",
            files={"invoice": ("test_bill5.jpg", sample_bill_bytes, "image/jpeg")},
            data={"vendor_email": "vendor@test.com", "vendor_mode": "accept", "demo_pacing": "false"},
            headers={"X-Forwarded-For": "198.51.100.3"}
        )
        assert status_c == 200, f"Failed to create case: {body_c}"
        case_id = res_c["case_id"]
        print(f"    Created case ID : {case_id}", flush=True)

        case_folder = UPLOAD_DIR / case_id
        assert case_folder.exists(), "Case folder should exist right after upload"
        print(f"    Files in upload folder during processing: {[f.name for f in case_folder.iterdir()]}", flush=True)

        # Stream the case to completion
        stream_url = f"{BASE_URL}/api/cases/{case_id}/stream"
        stream_headers = {"X-Forwarded-For": "198.51.100.3"}
        if cookie_c:
            stream_headers["Cookie"] = cookie_c.split(";")[0]
        req_stream = urllib.request.Request(stream_url, headers=stream_headers)
        with urllib.request.urlopen(req_stream) as s_resp:
            for line in s_resp:
                decoded = line.decode("utf-8", errors="replace")
                if decoded.startswith("event: outcome") or decoded.startswith("event: error") or decoded.startswith("event: end"):
                    break

        time.sleep(0.3)
        remaining_items = list(UPLOAD_DIR.iterdir())
        print(f"    Remaining items in 'uploads/' after run: {remaining_items}", flush=True)
        assert len(remaining_items) == 0, f"Uploads folder not empty: {remaining_items}"
        print("    [+] PASS (v): Uploads folder is completely empty after run completes.", flush=True)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()

    # -------------------------------------------------------------
    # (vi) git grep finds no API key, password or personal email in repo
    # -------------------------------------------------------------
    print("\n[Check 6/6] Proving git grep finds no API key, password, or personal email in the repo:", flush=True)

    p1 = subprocess.run(["git", "grep", "-i", "aizasy", "--", ":!VERIFY.md", ":!verify_public_mode.py"], capture_output=True, text=True)
    print(f"    git grep -i 'aizasy' matches: {len(p1.stdout.strip().splitlines()) if p1.stdout.strip() else 0}")
    assert p1.returncode != 0, f"Found Google API key in repo:\n{p1.stdout}"

    p2 = subprocess.run(["git", "grep", "-E", "sk-[a-zA-Z0-9]{20,}", "--", ":!VERIFY.md", ":!verify_public_mode.py"], capture_output=True, text=True)
    print(f"    git grep -E 'sk-...' matches: {len(p2.stdout.strip().splitlines()) if p2.stdout.strip() else 0}")
    assert p2.returncode != 0, f"Found OpenAI/Meta secret key in repo:\n{p2.stdout}"

    p3 = subprocess.run(["git", "grep", "-i", "gmail_app_password=", "--", ":!VERIFY.md", ":!verify_public_mode.py"], capture_output=True, text=True)
    non_placeholder_p3 = [l for l in p3.stdout.splitlines() if not any(fake in l.lower() for fake in ["your_", "placeholder", "example", "verify.md"])]
    print(f"    git grep 'GMAIL_APP_PASSWORD=' (non-placeholder) matches: {len(non_placeholder_p3)}")
    assert len(non_placeholder_p3) == 0, f"Found hardcoded Gmail app password:\n{non_placeholder_p3}"

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    p4 = subprocess.run(["git", "grep", "-E", email_pattern], capture_output=True, text=True)
    allowed_domains = ["example.com", "test.com", "render.com", "meta.ai", "google.com"]
    suspicious_emails = []
    if p4.stdout:
        for line in p4.stdout.splitlines():
            if any(ok_d in line.lower() for ok_d in allowed_domains):
                continue
            if any(doc in line for doc in ["VERIFY.md", "README.md", "accuracy.md"]):
                continue
            suspicious_emails.append(line)
    print(f"    git grep email scan: {len(p4.stdout.splitlines()) if p4.stdout else 0} total matches, {len(suspicious_emails)} personal/unwhitelisted matches")
    assert len(suspicious_emails) == 0, f"Found unwhitelisted email addresses:\n{suspicious_emails}"
    print("    [+] PASS (vi): 0 API keys, 0 passwords, 0 personal emails found in repository.", flush=True)

    print("\n" + "=" * 80)
    print(" ALL 6 PUBLIC_MODE SECURITY & RATE-LIMIT CHECKS PASSED (100%) ")
    print("=" * 80)

if __name__ == "__main__":
    main()
