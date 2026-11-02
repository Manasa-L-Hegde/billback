import os
import sys
import time
import io
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Force PUBLIC_MODE=1 for this test suite
os.environ["PUBLIC_MODE"] = "1"
os.environ["DRY_RUN"] = "0"
os.environ["GMAIL_USER"] = "trap_user@gmail.com"
os.environ["GMAIL_APP_PASSWORD"] = "trap_password_123"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from server import app, UPLOAD_DIR, IP_CASE_TIMESTAMPS, GLOBAL_CASE_TIMESTAMPS
import email_tools

client = TestClient(app)

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

    # -------------------------------------------------------------
    # (ii) The 6th case from one IP in an hour is refused politely
    # -------------------------------------------------------------
    print("\n[Check 2/6] Proving rate limit: 6th case from 1 IP in 1 hr refused politely (HTTP 429):", flush=True)
    IP_CASE_TIMESTAMPS.clear()
    GLOBAL_CASE_TIMESTAMPS.clear()
    test_ip = "203.0.113.42"
    headers = {"x-forwarded-for": test_ip}

    for i in range(1, 6):
        r = client.post("/api/cases/demo", json={"vendor_mode": "cached"}, headers=headers)
        assert r.status_code == 200, f"Expected 200 for case #{i}, got {r.status_code}: {r.text}"
        print(f"    Case #{i} from IP {test_ip} -> HTTP {r.status_code} (Allowed)", flush=True)

    # 6th case attempt
    r6 = client.post("/api/cases/demo", json={"vendor_mode": "cached"}, headers=headers)
    print(f"    Case #6 from IP {test_ip} -> HTTP {r6.status_code}", flush=True)
    print(f"    Detail message: {r6.json().get('detail')}", flush=True)
    assert r6.status_code == 429
    assert "rate limit reached" in r6.json().get("detail", "").lower()
    print("    [+] PASS (ii): 6th case from IP is refused politely with HTTP 429.", flush=True)

    # -------------------------------------------------------------
    # (iii) A .exe renamed to .jpg is rejected
    # -------------------------------------------------------------
    print("\n[Check 3/6] Proving .exe file renamed to .jpg is rejected by content inspection:", flush=True)
    fake_exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This is a Windows executable header!"
    r_exe = client.post(
        "/api/cases",
        files={"invoice": ("malicious_payload.jpg", fake_exe_content, "image/jpeg")},
        data={"vendor_email": "test@example.com"}
    )
    print(f"    Upload response status : HTTP {r_exe.status_code}", flush=True)
    print(f"    Upload response detail : {r_exe.json().get('detail')}", flush=True)
    assert r_exe.status_code == 400
    assert "invalid file type" in r_exe.json().get("detail", "").lower() or "only jpg, png, and webp" in r_exe.json().get("detail", "").lower()
    print("    [+] PASS (iii): Renamed .exe rejected by magic byte / content verification.", flush=True)

    # -------------------------------------------------------------
    # (iv) A 12 MB file is rejected
    # -------------------------------------------------------------
    print("\n[Check 4/6] Proving 12 MB file is rejected (exceeds 5 MB limit):", flush=True)
    large_payload = b"\xff\xd8\xff\xe0" + b"\x00" * (12 * 1024 * 1024)
    r_large = client.post(
        "/api/cases",
        files={"invoice": ("oversized_bill.jpg", large_payload, "image/jpeg")},
        data={"vendor_email": "test@example.com"}
    )
    print(f"    Upload response status : HTTP {r_large.status_code}", flush=True)
    print(f"    Upload response detail : {r_large.json().get('detail')}", flush=True)
    assert r_large.status_code == 413
    assert "5 mb" in r_large.json().get("detail", "").lower()
    print("    [+] PASS (iv): 12 MB file rejected with HTTP 413.", flush=True)

    # -------------------------------------------------------------
    # (v) Uploads folder is empty after a run
    # -------------------------------------------------------------
    print("\n[Check 5/6] Proving uploads folder is empty after a case run completes:", flush=True)
    # Clear uploads dir and IP timestamps for clean run
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    IP_CASE_TIMESTAMPS.clear()
    sample_bill_bytes = Path("samples/test_bill5.jpg").read_bytes()
    r_case = client.post(
        "/api/cases",
        files={"invoice": ("test_bill5.jpg", sample_bill_bytes, "image/jpeg")},
        data={"vendor_email": "vendor@test.com", "vendor_mode": "accept", "demo_pacing": "false"}
    )
    assert r_case.status_code == 200, f"Failed to create case: {r_case.text}"
    case_id = r_case.json()["case_id"]
    print(f"    Created case ID : {case_id}", flush=True)
    
    # Check that case folder was created during upload
    case_folder = UPLOAD_DIR / case_id
    assert case_folder.exists(), "Case folder should exist right after upload"
    print(f"    Files in upload folder during processing: {[f.name for f in case_folder.iterdir()]}", flush=True)

    # Stream the case to completion
    with client.stream("GET", f"/api/cases/{case_id}/stream") as stream_resp:
        for line in stream_resp.iter_lines():
            if not line:
                continue
            if line.startswith("event: outcome") or line.startswith("event: error") or line.startswith("event: end"):
                break

    # Verify upload folder cleanup
    time.sleep(0.2)
    remaining_items = list(UPLOAD_DIR.iterdir())
    print(f"    Remaining items in 'uploads/' after run: {remaining_items}", flush=True)
    assert len(remaining_items) == 0, f"Uploads folder not empty: {remaining_items}"
    print("    [+] PASS (v): Uploads folder is completely empty after run completes.", flush=True)

    # -------------------------------------------------------------
    # (vi) git grep finds no API key, password or personal email in repo
    # -------------------------------------------------------------
    print("\n[Check 6/6] Proving git grep finds no API key, password, or personal email in the repo:", flush=True)
    
    # 1. API key checks
    p1 = subprocess.run(["git", "grep", "-i", "aizasy"], capture_output=True, text=True)
    print(f"    git grep -i 'aizasy' matches: {len(p1.stdout.strip().splitlines()) if p1.stdout.strip() else 0}")
    assert p1.returncode != 0, f"Found Google API key in repo:\n{p1.stdout}"

    p2 = subprocess.run(["git", "grep", "-E", "sk-[a-zA-Z0-9]{20,}"], capture_output=True, text=True)
    print(f"    git grep -E 'sk-...' matches: {len(p2.stdout.strip().splitlines()) if p2.stdout.strip() else 0}")
    assert p2.returncode != 0, f"Found OpenAI/Meta secret key in repo:\n{p2.stdout}"

    # 2. Gmail App Password check
    p3 = subprocess.run(["git", "grep", "-i", "gmail_app_password="], capture_output=True, text=True)
    non_placeholder_p3 = [l for l in p3.stdout.splitlines() if not any(fake in l.lower() for fake in ["your_", "placeholder", "example", "verify.md"])]
    print(f"    git grep 'GMAIL_APP_PASSWORD=' (non-placeholder) matches: {len(non_placeholder_p3)}")
    assert len(non_placeholder_p3) == 0, f"Found hardcoded Gmail app password:\n{non_placeholder_p3}"

    # 3. Personal emails check
    p4 = subprocess.run(["git", "grep", "-E", "[a-zA-Z0-9_.]+@[a-zA-Z0-9]+\\.[a-zA-Z]+"], capture_output=True, text=True)
    raw_lines = p4.stdout.strip().splitlines()
    # Filter out safe placeholders and system/sample names
    leaked_emails = []
    for line in raw_lines:
        lower = line.lower()
        if any(safe in lower for safe in ["example.com", "your_email@gmail.com", "verify.md", "samples/screens", "samples/test_hard"]):
            continue
        leaked_emails.append(line)

    print(f"    git grep email scan: {len(raw_lines)} total matches, {len(leaked_emails)} personal/unwhitelisted matches")
    assert len(leaked_emails) == 0, f"Found leaked personal email in tracked repo:\n{leaked_emails}"
    print("    [+] PASS (vi): 0 API keys, 0 passwords, 0 personal emails found in repository.")

    print("\n" + "=" * 80, flush=True)
    print(" ALL 6 PUBLIC_MODE SECURITY & RATE-LIMIT CHECKS PASSED (100%) ", flush=True)
    print("=" * 80, flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
