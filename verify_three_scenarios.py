import sys
import time
import json
import sqlite3
from fastapi.testclient import TestClient
from server import app

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = TestClient(app)

def get_db_case(case_id):
    conn = sqlite3.connect("billback.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def read_case_stream(case_id, max_seconds=120, stop_events=("outcome", "error", "awaiting_approval")):
    t0 = time.time()
    events = []
    try:
        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            for line in resp.iter_lines():
                if time.time() - t0 > max_seconds:
                    print(f"  [Timeout after {max_seconds}s]")
                    break
                if not line:
                    continue
                if line.startswith("event:"):
                    ev = line.split(":", 1)[1].strip()
                    events.append(ev)
                    if ev in stop_events:
                        break
    except Exception as e:
        print(f"  [Stream Exception]: {e}")
    return events

def run_accept_scenario():
    t0 = time.time()
    r = client.post("/api/cases/demo", json={
        "vendor_mode": "accept",
        "min_accept_percent": 80.0,
        "autonomous": True,
        "demo_pacing": False
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    events = read_case_stream(case_id, stop_events=("outcome", "error"))
    duration = round(time.time() - t0, 2)
    case_rec = get_db_case(case_id)
    out = json.loads(case_rec.get("transcript_json") or "{}") if case_rec.get("transcript_json") else {}
    
    status_text = out.get("status") or case_rec.get("status", "Unknown")
    recovered = float(case_rec.get("recovered") or out.get("recovered") or 0.0)
    claimed = float(case_rec.get("claimed") or out.get("claimed") or 0.0)
    rounds = out.get("rounds", 1)

    return {
        "scenario": "1. Accept",
        "status": status_text,
        "claimed": claimed,
        "recovered": recovered,
        "rounds": rounds,
        "seconds": duration,
        "pass": "outcome" in events and recovered >= (0.8 * claimed)
    }

def run_partial_50_scenario():
    t0 = time.time()
    r = client.post("/api/cases/demo", json={
        "vendor_mode": "partial_50",
        "min_accept_percent": 80.0,
        "autonomous": True,
        "demo_pacing": False
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    events = read_case_stream(case_id, stop_events=("outcome", "error"))
    duration = round(time.time() - t0, 2)
    case_rec = get_db_case(case_id)
    out = json.loads(case_rec.get("transcript_json") or "{}") if case_rec.get("transcript_json") else {}
    
    status_text = out.get("status") or case_rec.get("status", "Unknown")
    recovered = float(case_rec.get("recovered") or out.get("recovered") or 0.0)
    claimed = float(case_rec.get("claimed") or out.get("claimed") or 0.0)
    rounds = out.get("rounds", 3)

    return {
        "scenario": "2. Partial 50%",
        "status": status_text,
        "claimed": claimed,
        "recovered": recovered,
        "rounds": rounds,
        "seconds": duration,
        "pass": "outcome" in events and "escalat" in status_text.lower()
    }

def run_deny_scenario():
    t0 = time.time()
    r = client.post("/api/cases/demo", json={
        "vendor_mode": "deny",
        "min_accept_percent": 80.0,
        "autonomous": True,
        "demo_pacing": False
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    events = read_case_stream(case_id, stop_events=("outcome", "error"))
    duration = round(time.time() - t0, 2)
    case_rec = get_db_case(case_id)
    out = json.loads(case_rec.get("transcript_json") or "{}") if case_rec.get("transcript_json") else {}
    
    status_text = out.get("status") or case_rec.get("status", "Unknown")
    recovered = float(case_rec.get("recovered") or out.get("recovered") or 0.0)
    claimed = float(case_rec.get("claimed") or out.get("claimed") or 0.0)
    rounds = out.get("rounds", 1)

    return {
        "scenario": "3. Deny",
        "status": status_text,
        "claimed": claimed,
        "recovered": recovered,
        "rounds": rounds,
        "seconds": duration,
        "pass": "outcome" in events and "escalat" in status_text.lower()
    }

def run_approval_scenario():
    import threading
    t0 = time.time()
    r = client.post("/api/cases/demo", json={
        "vendor_mode": "partial_50",
        "min_accept_percent": 80.0,
        "autonomous": False,
        "demo_pacing": False
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]

    events = []
    approval_posted = [False]

    def trigger_approve():
        time.sleep(0.05)
        res = client.post(f"/api/cases/{case_id}/approve", json={
            "edited_subject": "Approved Dispute - Invoice Shortage"
        })
        if res.status_code == 200:
            approval_posted[0] = True

    try:
        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    ev = line.split(":", 1)[1].strip()
                    events.append(ev)
                    if ev == "awaiting_approval":
                        threading.Thread(target=trigger_approve, daemon=True).start()
                    elif ev in ("outcome", "error"):
                        break
    except Exception as e:
        print(f"  [Approval stream exception]: {e}")

    duration = round(time.time() - t0, 2)
    case_rec = get_db_case(case_id)
    out = json.loads(case_rec.get("transcript_json") or "{}") if case_rec.get("transcript_json") else {}

    status_text = out.get("status") or case_rec.get("status", "Unknown")
    recovered = float(case_rec.get("recovered") or out.get("recovered") or 0.0)
    claimed = float(case_rec.get("claimed") or out.get("claimed") or 0.0)
    rounds = out.get("rounds", 3)

    return {
        "scenario": "4. Approval Mode",
        "status": status_text,
        "claimed": claimed,
        "recovered": recovered,
        "rounds": rounds,
        "seconds": duration,
        "pass": "awaiting_approval" in events and "outcome" in events and approval_posted[0]
    }

def main():
    print("=" * 80)
    print(" TASK 3 VERIFICATION: THREE SCENARIOS + APPROVAL MODE ")
    print("=" * 80)

    scenarios = [
        ("Accept", run_accept_scenario),
        ("Partial 50%", run_partial_50_scenario),
        ("Deny", run_deny_scenario),
        ("Approval Mode", run_approval_scenario),
    ]

    results = []
    for name, runner in scenarios:
        print(f"\n[*] Executing scenario: {name}...", flush=True)
        res = runner()
        results.append(res)
        print(f"    Status   : {res['status']}", flush=True)
        print(f"    Recovered: Rs. {res['recovered']} / Rs. {res['claimed']}", flush=True)
        print(f"    Rounds   : {res['rounds']}", flush=True)
        print(f"    Duration : {res['seconds']}s", flush=True)
        print(f"    Pass     : {'YES' if res['pass'] else 'NO'}", flush=True)

    print("\n" + "=" * 80)
    print(" SCENARIO VERIFICATION SUMMARY TABLE ")
    print("=" * 80)
    print(f"{'Scenario':<18} | {'Recovered vs Claimed':<22} | {'Rounds':<6} | {'Seconds':<8} | {'Status Summary':<30}")
    print("-" * 95)
    for r in results:
        rec_claim = f"Rs. {r['recovered']} / Rs. {r['claimed']}"
        print(f"{r['scenario']:<18} | {rec_claim:<22} | {r['rounds']:<6} | {r['seconds']:<7}s | {r['status'][:30]:<30}")
    print("=" * 80)

    all_pass = all(r["pass"] for r in results)
    print(f"FINAL RESULT: {'ALL 4 SCENARIOS VERIFIED' if all_pass else 'SOME SCENARIOS FAILED'}\n")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
