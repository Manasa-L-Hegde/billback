import sys, time, json
from fastapi.testclient import TestClient
from server import app

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = TestClient(app)

def read_sse(case_id, max_seconds=150, stop_events=("outcome", "awaiting_approval", "error", "end")):
    """Read SSE stream with safety timeout and immediate break on terminal events."""
    start_t = time.time()
    events = []
    data_payloads = []

    try:
        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            for line in resp.iter_lines():
                if time.time() - start_t > max_seconds:
                    print(f"  [TIMEOUT] SSE stream exceeded {max_seconds}s limit!")
                    break
                
                if not line:
                    continue
                
                if line.startswith("event:"):
                    ev = line.split(":", 1)[1].strip()
                    events.append(ev)
                    # Stop if terminal event reached
                    if ev in stop_events:
                        break
                elif line.startswith("data:"):
                    try:
                        d = json.loads(line[5:].strip())
                        data_payloads.append(d)
                    except Exception:
                        pass
    except Exception as e:
        print(f"  [STREAM ERROR]: {e}")

    return events, data_payloads

def run_scenario(name, func):
    print(f"\nSTART {name}")
    t0 = time.time()
    try:
        func()
        duration = round(time.time() - t0, 2)
        print(f"END {name} {duration}s")
        return True, duration
    except Exception as e:
        duration = round(time.time() - t0, 2)
        print(f"FAIL {name} {duration}s: {e}")
        return False, duration

# Scenario 1: Autonomous Demo Case
def scenario_1_autonomous():
    r = client.post("/api/cases/demo", json={"vendor_mode": "partial_50", "min_accept_percent": 80.0, "autonomous": True})
    assert r.status_code == 200, f"Status {r.status_code}"
    case_id = r.json()["case_id"]
    events, _ = read_sse(case_id, max_seconds=150, stop_events=("outcome", "error"))
    print(f"  Captured events: {events}")
    assert "outcome" in events, f"Expected 'outcome' in {events}"
    assert "awaiting_approval" not in events

# Scenario 2: Human Approval Mode (halts at awaiting_approval)
def scenario_2_approval():
    r = client.post("/api/cases/demo", json={"vendor_mode": "partial_50", "min_accept_percent": 80.0, "autonomous": False})
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    
    # First stream should pause at awaiting_approval
    events, _ = read_sse(case_id, max_seconds=150, stop_events=("awaiting_approval", "error"))
    print(f"  Stage 1 events (pre-approval): {events}")
    assert "awaiting_approval" in events, f"Expected awaiting_approval in {events}"

    # Now approve the case
    print("  Triggering POST /approve ...")
    app_res = client.post(f"/api/cases/{case_id}/approve", json={"edited_subject": "Approved Dispute Subject"})
    assert app_res.status_code == 200, f"Approval status {app_res.status_code}"
    print(f"  Approval result: {app_res.json()}")

    # Continue reading stream to outcome
    events2, _ = read_sse(case_id, max_seconds=150, stop_events=("outcome", "error"))
    print(f"  Stage 2 events (post-approval): {events2}")
    assert "outcome" in events2, f"Expected outcome in {events2}"

# Scenario 3: Vendor Deny Behaviour (Escalates to Human after 3 rounds)
def scenario_3_deny():
    r = client.post("/api/cases/demo", json={"vendor_mode": "deny", "min_accept_percent": 80.0, "autonomous": True})
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    events, payloads = read_sse(case_id, max_seconds=150, stop_events=("outcome", "error"))
    print(f"  Captured events: {events}")
    assert "outcome" in events

# Scenario 4: Clean Bill (test_bill6.jpg - zero overcharge, zero emails drafted)
def scenario_4_clean():
    with open("samples/test_bill6.jpg", "rb") as f:
        r = client.post("/api/cases", files={"invoice": ("test_bill6.jpg", f, "image/jpeg")}, data={"autonomous": "true"})
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    events, _ = read_sse(case_id, max_seconds=150, stop_events=("outcome", "error"))
    print(f"  Captured events: {events}")
    assert "email_draft" not in events
    assert "outcome" in events

# Scenario 5: Bad / Corrupted File Upload (Graceful error handling)
def scenario_5_bad_file():
    corrupted = b"this is not an image"
    r = client.post("/api/cases", files={"invoice": ("corrupt.jpg", corrupted, "image/jpeg")}, data={"autonomous": "true"})
    assert r.status_code == 200
    case_id = r.json()["case_id"]
    events, _ = read_sse(case_id, max_seconds=150, stop_events=("error", "end"))
    print(f"  Captured events: {events}")
    assert "error" in events

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"

    scenarios = [
        ("scenario_1_autonomous", scenario_1_autonomous),
        ("scenario_2_approval", scenario_2_approval),
        ("scenario_3_deny", scenario_3_deny),
        ("scenario_4_clean", scenario_4_clean),
        ("scenario_5_bad_file", scenario_5_bad_file)
    ]

    for name, fn in scenarios:
        if which == "all" or which == name:
            run_scenario(name, fn)
