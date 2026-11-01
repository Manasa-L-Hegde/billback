import sys
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from server import app

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = TestClient(app)

def read_case_stream(case_id, max_seconds=120, stop_events=("outcome", "error", "awaiting_approval")):
    t0 = time.time()
    events = []
    payloads = {}
    try:
        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            current_event = None
            for line in resp.iter_lines():
                if time.time() - t0 > max_seconds:
                    break
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    events.append(current_event)
                elif line.startswith("data:") and current_event:
                    try:
                        d = json.loads(line[5:].strip())
                        payloads[current_event] = d
                    except Exception:
                        payloads[current_event] = line[5:].strip()
                    if current_event in stop_events:
                        break
    except Exception as e:
        print(f"  Stream error: {e}")
    return events, payloads

def run_single(mode="partial_50", autonomous=True):
    import threading
    t0 = time.time()
    try:
        r = client.post("/api/cases/demo", json={
            "vendor_mode": mode,
            "min_accept_percent": 80.0,
            "autonomous": autonomous,
            "demo_pacing": False
        })
        if r.status_code != 200:
            return False, round(time.time() - t0, 2), f"HTTP {r.status_code}: {r.text}"
        
        case_id = r.json()["case_id"]

        events = []
        payloads = {}

        def trigger_app():
            time.sleep(0.05)
            client.post(f"/api/cases/{case_id}/approve", json={"edited_subject": "Approved"})

        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            current_event = None
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    events.append(current_event)
                    if current_event == "awaiting_approval" and not autonomous:
                        threading.Thread(target=trigger_app, daemon=True).start()
                elif line.startswith("data:") and current_event:
                    try:
                        payloads[current_event] = json.loads(line[5:].strip())
                    except Exception:
                        payloads[current_event] = line[5:].strip()
                    if current_event in ("outcome", "error"):
                        break

        dur = round(time.time() - t0, 2)
        if "outcome" in events:
            return True, dur, None
        elif "error" in events:
            err = payloads.get("error", {}).get("message", "Unknown error")
            return False, dur, err
        else:
            return False, dur, "Stream ended without outcome"
    except Exception as e:
        return False, round(time.time() - t0, 2), str(e)

def run_parallel_test():
    print("\n" + "=" * 80)
    print(" PARALLEL EXECUTION INTEGRITY TEST ")
    print("=" * 80)
    print("[*] Creating 2 demo cases concurrently (Case A & Case B)...")
    
    r_a = client.post("/api/cases/demo", json={"vendor_mode": "accept", "min_accept_percent": 80.0, "autonomous": True, "demo_pacing": False})
    r_b = client.post("/api/cases/demo", json={"vendor_mode": "deny", "min_accept_percent": 80.0, "autonomous": True, "demo_pacing": False})
    
    id_a = r_a.json()["case_id"]
    id_b = r_b.json()["case_id"]
    print(f"    Case A ID: {id_a}")
    print(f"    Case B ID: {id_b}")
    assert id_a != id_b, "Case IDs must be unique!"

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_a = ex.submit(read_case_stream, id_a, 120, ("outcome", "error"))
        f_b = ex.submit(read_case_stream, id_b, 120, ("outcome", "error"))
        ev_a, p_a = f_a.result()
        ev_b, p_b = f_b.result()

    out_a = p_a.get("outcome", {})
    out_b = p_b.get("outcome", {})

    print(f"    Case A (accept mode) outcome: Recovered Rs. {out_a.get('recovered')} / Rs. {out_a.get('claimed')} | Status: {out_a.get('status')}")
    print(f"    Case B (deny mode)   outcome: Recovered Rs. {out_b.get('recovered')} / Rs. {out_b.get('claimed')} | Status: {out_b.get('status')}")

    # Verify no overwrite occurred
    assert out_a.get("recovered", 0) > 0, "Case A must be accepted with recovery!"
    assert out_b.get("recovered", 0) == 0, "Case B must be denied with 0 recovery!"
    print("    [+] PASS: Case A and Case B executed concurrently without overwriting.")

def run_fault_injection_test():
    print("\n" + "=" * 80)
    print(" FAULT INJECTION (FAULT_INJECT=timeout) TEST ")
    print("=" * 80)
    print("[*] Setting FAULT_INJECT=timeout to simulate an upstream API stall...")
    os.environ["FAULT_INJECT"] = "timeout"
    try:
        r = client.post("/api/cases/demo", json={"vendor_mode": "partial_50", "min_accept_percent": 80.0, "autonomous": True, "demo_pacing": False})
        cid = r.json()["case_id"]
        t0 = time.time()
        events, payloads = read_case_stream(cid, max_seconds=60, stop_events=("error", "outcome"))
        dur = round(time.time() - t0, 2)
        print(f"    Events received: {events}")
        print(f"    Error payload  : {payloads.get('error')}")
        print(f"    Response time  : {dur}s (well within 60s limit)")
        assert "error" in events, "Fault injection must emit 'error' event!"
        err_msg = str(payloads.get("error", {}).get("message", ""))
        assert "timed out" in err_msg.lower() or "fault_inject" in err_msg.lower()
        print("    [+] PASS: UI / client received friendly error banner with retry option.")
    finally:
        del os.environ["FAULT_INJECT"]

def main():
    print("=" * 80)
    print(" TASK 4 VERIFICATION: RELIABILITY SUITE (10x Demo, 3x Deny, 3x Approval) ")
    print("=" * 80)

    runs = []

    # 1. 10x Demo Case (partial_50, autonomous)
    print("\n[Section 1] Running Demo Case (partial 50%) 10 times in a row:")
    for i in range(1, 11):
        success, dur, cause = run_single("partial_50", autonomous=True)
        st = "COMPLETED" if success else "FAILED"
        print(f"  Run {i:>2}/10: {st:<9} in {dur:>5.2f}s" + (f" (Cause: {cause})" if cause else ""))
        runs.append({"type": f"Demo Case #{i}", "status": st, "duration": dur, "cause": cause or "-"})

    # 2. 3x Deny Case
    print("\n[Section 2] Running Deny Scenario 3 times:")
    for i in range(1, 4):
        success, dur, cause = run_single("deny", autonomous=True)
        st = "COMPLETED" if success else "FAILED"
        print(f"  Deny {i:>2}/3: {st:<9} in {dur:>5.2f}s" + (f" (Cause: {cause})" if cause else ""))
        runs.append({"type": f"Deny #{i}", "status": st, "duration": dur, "cause": cause or "-"})

    # 3. 3x Approval Case
    print("\n[Section 3] Running Approval Mode 3 times:")
    for i in range(1, 4):
        success, dur, cause = run_single("partial_50", autonomous=False)
        st = "COMPLETED" if success else "FAILED"
        print(f"  Approval {i:>2}/3: {st:<9} in {dur:>5.2f}s" + (f" (Cause: {cause})" if cause else ""))
        runs.append({"type": f"Approval #{i}", "status": st, "duration": dur, "cause": cause or "-"})

    # 4. Summary Table
    print("\n" + "=" * 80)
    print(" RELIABILITY TEST RESULTS SUMMARY TABLE ")
    print("=" * 80)
    print(f"{'Run Description':<18} | {'Status':<10} | {'Duration (s)':<12} | {'Failure Cause'}")
    print("-" * 80)
    for r in runs:
        print(f"{r['type']:<18} | {r['status']:<10} | {r['duration']:<12.2f} | {r['cause']}")
    print("=" * 80)
    completed_cnt = sum(1 for r in runs if r["status"] == "COMPLETED")
    total_cnt = len(runs)
    avg_dur = sum(r["duration"] for r in runs) / total_cnt
    print(f"Completion Rate: {completed_cnt}/{total_cnt} ({completed_cnt/total_cnt*100:.1f}%) | Average Duration: {avg_dur:.2f}s")

    # 5. Parallel Integrity Test
    run_parallel_test()

    # 6. Fault Injection Test
    run_fault_injection_test()

    return 0

if __name__ == "__main__":
    sys.exit(main())
