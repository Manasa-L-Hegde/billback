import os
import sys
import time
import json
import socket
import subprocess
import urllib.request
import urllib.error
import http.client
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PORT = 8095
BASE_URL = f"http://127.0.0.1:{PORT}"

def wait_for_server(port, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.3)
    return False

def http_req(path, method="GET", data=None, headers=None, cookies=None):
    url = f"{BASE_URL}{path}"
    req_headers = dict(headers or {})
    if cookies:
        req_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    
    encoded_data = None
    if data is not None:
        if isinstance(data, (dict, list)):
            encoded_data = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, bytes):
            encoded_data = data
        elif isinstance(data, str):
            encoded_data = data.encode("utf-8")

    req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            set_cookie = resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else [resp.headers.get("Set-Cookie")]
            return {
                "status": resp.status,
                "body": body,
                "json": json.loads(body) if "application/json" in resp.headers.get("Content-Type", "") else None,
                "headers": resp_headers,
                "cookies": set_cookie
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        parsed_json = None
        try:
            parsed_json = json.loads(err_body)
        except Exception:
            pass
        return {
            "status": e.code,
            "body": err_body,
            "json": parsed_json,
            "headers": dict(e.headers),
            "cookies": []
        }

def extract_cookie(cookies_list, cookie_name="bb_session"):
    for c in cookies_list:
        if not c:
            continue
        parts = c.split(";")
        for p in parts:
            if "=" in p:
                k, v = p.strip().split("=", 1)
                if k == cookie_name:
                    return v
    return None

def main():
    print("=" * 80)
    print(" DEPLOY HARDENING VERIFICATION: CLIENT IP & VISITOR ISOLATION ")
    print("=" * 80)

    # 1. Start Uvicorn with --proxy-headers and --forwarded-allow-ips="*"
    env = os.environ.copy()
    env["PUBLIC_MODE"] = "1"
    
    UVICORN_EXE = r".venv\Scripts\uvicorn.exe"
    cmd = [
        UVICORN_EXE, "server:app",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--proxy-headers",
        '--forwarded-allow-ips=*'
    ]
    print(f"[*] Starting uvicorn with PUBLIC_MODE=1 on port {PORT}...")
    print(f"    Command: {' '.join(cmd)}")
    log_file = open("uvicorn_verify.log", "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=log_file)

    try:
        if not wait_for_server(PORT, timeout=25):
            print("Failed to start server within timeout. Log contents:")
            log_file.flush()
            with open("uvicorn_verify.log", "r", encoding="utf-8") as lf:
                print(lf.read())
            sys.exit(1)

        print("[+] Uvicorn server is up and listening.")

        # Health check
        h_res = http_req("/health")
        print(f"[+] Health check returned status {h_res['status']}: {h_res['body']}")
        assert h_res["status"] == 200

        # -----------------------------------------------------------------
        # TEST ITEM 1: CLIENT IP RATE LIMITING & SEPARATE QUOTAS
        # -----------------------------------------------------------------
        print("\n" + "=" * 70)
        print(" ITEM 1: CLIENT IP RATE LIMITING & SEPARATE QUOTAS")
        print("=" * 70)

        ip_a = "203.0.113.195"
        ip_b = "198.51.100.42"

        # Multi-hop proxy chain simulating Render / Cloudflare / Nginx proxy
        headers_a = {"X-Forwarded-For": f"{ip_a}, 10.0.0.1, 172.16.0.1"}
        headers_b = {"X-Forwarded-For": f"{ip_b}, 10.0.0.2"}

        print(f"[*] Proving Demo Case IP rate limit (30 cases/hour/IP) for IP A ({ip_a})...")
        for i in range(1, 31):
            r = http_req("/api/cases/demo", method="POST", data={"vendor_mode": "cached"}, headers=headers_a)
            assert r["status"] == 200, f"Demo case {i} failed: {r['body']}"
        print(f"    -> Demo cases 1-30 for IP A: ALL succeeded with HTTP 200 OK.")

        # 31st demo case for IP A must be rejected with HTTP 429
        r31 = http_req("/api/cases/demo", method="POST", data={"vendor_mode": "cached"}, headers=headers_a)
        print(f"    -> 31st demo case for IP A status: HTTP {r31['status']} (Expected 429)")
        assert r31["status"] == 429, f"Expected 429, got {r31['status']}: {r31['body']}"
        print(f"    -> Detail: {r31['json'].get('detail')}")

        # IP B has a separate quota: 1st request must succeed immediately
        print(f"\n[*] Proving separate quota for IP B ({ip_b})...")
        rb = http_req("/api/cases/demo", method="POST", data={"vendor_mode": "cached"}, headers=headers_b)
        print(f"    -> 1st demo case for IP B status: HTTP {rb['status']} (Expected 200)")
        assert rb["status"] == 200, f"Expected 200 for IP B, got {rb['status']}: {rb['body']}"
        print("    [+] PASS: IP A and IP B maintain independent, separated rate limit quotas.")

        # Custom cases limit: 5/hour/IP
        ip_c = "192.0.2.77"
        headers_c = {"X-Forwarded-For": ip_c}
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        dummy_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
            b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
            b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff"
            b"\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01"
            b"\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )
        multipart_body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="invoice"; filename="bill.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + dummy_jpeg + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers_c["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        print(f"\n[*] Proving Custom Case rate limit (5 cases/hour/IP) for IP C ({ip_c})...")
        for i in range(1, 6):
            rc = http_req("/api/cases", method="POST", data=multipart_body, headers=headers_c)
            assert rc["status"] == 200, f"Custom case {i} failed: {rc['body']}"
        print(f"    -> Custom cases 1-5 for IP C: ALL succeeded with HTTP 200 OK.")

        # 6th custom case must be rejected with HTTP 429
        rc6 = http_req("/api/cases", method="POST", data=multipart_body, headers=headers_c)
        print(f"    -> 6th custom case for IP C status: HTTP {rc6['status']} (Expected 429)")
        assert rc6["status"] == 429, f"Expected 429, got {rc6['status']}: {rc6['body']}"
        print(f"    -> Detail: {rc6['json'].get('detail')}")
        print("    [+] PASS: Custom case quota enforced at 5/hour/IP; demo case quota at 30/hour/IP.")

        # -----------------------------------------------------------------
        # TEST ITEM 2: VISITOR ISOLATION & SESSION COOKIES
        # -----------------------------------------------------------------
        print("\n" + "=" * 70)
        print(" ITEM 2: VISITOR ISOLATION & SESSION COOKIES")
        print("=" * 70)

        # Session A creates a case
        ip_visitor = "100.64.1.50"
        headers_vis = {"X-Forwarded-For": ip_visitor}
        print("[*] Session A creating a demo case with no initial cookie...")
        res_a = http_req("/api/cases/demo", method="POST", data={"vendor_mode": "cached"}, headers=headers_vis)
        assert res_a["status"] == 200
        case_a_id = res_a["json"]["case_id"]
        
        cookie_a = extract_cookie(res_a["cookies"], "bb_session")
        print(f"    -> Case A created: id = {case_a_id}")
        print(f"    -> Response Set-Cookie: {res_a['cookies']}")
        print(f"    -> Extracted Session A cookie: {cookie_a}")
        assert cookie_a, "Expected bb_session cookie in Set-Cookie header!"
        cookies_a = {"bb_session": cookie_a}

        # Session A lists cases
        list_a_res = http_req("/api/cases", headers=headers_vis, cookies=cookies_a)
        case_ids_a = [c["id"] for c in list_a_res["json"]]
        print(f"    -> Session A cases retrieved: {len(case_ids_a)} case(s)")
        assert case_a_id in case_ids_a, f"Session A's case {case_a_id} must appear in Session A's listing!"

        # Session B: independent session
        cookie_b = f"sess_visitor_b_{int(time.time())}"
        cookies_b = {"bb_session": cookie_b}
        print(f"\n[*] Session B accessing case listing with Session B cookie ({cookie_b})...")
        list_b_res = http_req("/api/cases", headers=headers_vis, cookies=cookies_b)
        case_ids_b = [c["id"] for c in list_b_res["json"]]
        print(f"    -> Session B cases retrieved: {len(case_ids_b)} case(s)")
        assert case_a_id not in case_ids_b, f"ISOLATION FAILURE: Case {case_a_id} created by Session A leaked into Session B!"
        print(f"    [+] CONFIRMED: Session A's case ({case_a_id}) is completely hidden from Session B.")

        # Session B attempts unauthorized stream access
        print(f"\n[*] Session B attempting unauthorized access to stream of Session A's case ({case_a_id})...")
        stream_b_res = http_req(f"/api/cases/{case_a_id}/stream", headers=headers_vis, cookies=cookies_b)
        print(f"    -> Status code: HTTP {stream_b_res['status']} (Expected 403 Forbidden)")
        assert stream_b_res["status"] == 403, f"Expected 403, got {stream_b_res['status']}: {stream_b_res['body']}"
        print(f"    -> Detail: {stream_b_res['json'].get('detail')}")
        print(f"    [+] CONFIRMED: Cross-session stream access strictly blocked with HTTP 403.")

        # Session B attempts unauthorized case approval
        print(f"\n[*] Session B attempting unauthorized approve on Session A's case ({case_a_id})...")
        appr_b_res = http_req(f"/api/cases/{case_a_id}/approve", method="POST", data={"edited_subject": "Hacked"}, headers=headers_vis, cookies=cookies_b)
        print(f"    -> Status code: HTTP {appr_b_res['status']} (Expected 403 Forbidden)")
        assert appr_b_res["status"] == 403, f"Expected 403, got {appr_b_res['status']}: {appr_b_res['body']}"
        print(f"    -> Detail: {appr_b_res['json'].get('detail')}")
        print(f"    [+] CONFIRMED: Cross-session approval strictly blocked with HTTP 403.")

        # Drift alerts must remain global for both sessions
        print("\n[*] Verifying Price-Drift Alerts stay global across visitor sessions (labelled seeded)...")
        drift_a = http_req("/api/drift", headers=headers_vis, cookies=cookies_a)["json"]
        drift_b = http_req("/api/drift", headers=headers_vis, cookies=cookies_b)["json"]
        print(f"    -> Session A drift alerts count: {len(drift_a.get('alerts', []))}")
        print(f"    -> Session B drift alerts count: {len(drift_b.get('alerts', []))}")
        assert len(drift_a.get("alerts", [])) == len(drift_b.get("alerts", [])) > 0
        print("    [+] CONFIRMED: Drift alerts remain global and seeded across all visitor sessions.")

        print("\n" + "=" * 80)
        print(" ALL DEPLOY HARDENING & VISITOR ISOLATION CHECKS PASSED (100%) ")
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
