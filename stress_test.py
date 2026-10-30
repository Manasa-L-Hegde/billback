import time, json
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

print("="*70)
print("RELIABILITY STRESS TEST: 10 CONSECUTIVE DEMO CASE RUNS")
print("="*70)

runs = 10
completed = 0
durations = []
failures = []

for i in range(1, runs + 1):
    t0 = time.time()
    print(f"\n[Run {i}/{runs}] Launching demo case...", end=" ", flush=True)
    try:
        r = client.post("/api/cases/demo", json={"vendor_mode": "partial_50", "min_accept_percent": 80.0, "autonomous": True})
        if r.status_code != 200:
            raise Exception(f"POST /api/cases/demo failed with status {r.status_code}")
        
        case_id = r.json()["case_id"]
        
        # Read stream
        events = []
        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            for line in resp.iter_lines():
                if time.time() - t0 > 75.0:
                    raise TimeoutError("SSE Stream exceeded 75 seconds")
                if not line:
                    continue
                if line.startswith("event:"):
                    ev = line.split(":", 1)[1].strip()
                    events.append(ev)
                    if ev in ("outcome", "error"):
                        break
        
        elapsed = round(time.time() - t0, 2)
        durations.append(elapsed)
        if "outcome" in events:
            completed += 1
            print(f"SUCCESS in {elapsed}s (Events: {len(events)})")
        else:
            failures.append((i, f"No outcome event. Events: {events}"))
            print(f"FAILED in {elapsed}s (No outcome)")
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        durations.append(elapsed)
        failures.append((i, str(e)))
        print(f"FAILED in {elapsed}s: {e}")

avg_dur = round(sum(durations) / len(durations), 2) if durations else 0
print("\n" + "="*70)
print("RELIABILITY SUMMARY:")
print(f"  Total Runs Completed: {completed}/{runs} ({(completed/runs)*100:.1f}%)")
print(f"  Average Run Time    : {avg_dur}s")
if durations:
    print(f"  Min / Max Run Time  : {min(durations)}s / {max(durations)}s")
if failures:
    print(f"  Failures Encountered:")
    for f in failures:
        print(f"    - Run {f[0]}: {f[1]}")
else:
    print("  Zero Failures: 100% Reliable Execution!")
print("="*70)

