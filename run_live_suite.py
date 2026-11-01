import sys, time, json, os, threading
from pathlib import Path
from fastapi.testclient import TestClient
from server import app

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = TestClient(app)

def run_single_case(vendor_mode="partial_50", autonomous=True, max_seconds=120):
    t0 = time.time()
    r = client.post("/api/cases/demo", json={
        "vendor_mode": vendor_mode,
        "min_accept_percent": 80.0,
        "autonomous": autonomous,
        "demo_pacing": False
    })
    if r.status_code != 200:
        return {
            "success": False,
            "seconds": round(time.time() - t0, 2),
            "status": f"HTTP {r.status_code}",
            "api_stats": {}
        }

    case_id = r.json()["case_id"]
    events = []
    payloads = {}

    def trigger_approval():
        time.sleep(0.05)
        client.post(f"/api/cases/{case_id}/approve", json={"edited_subject": "Approved Dispute"})

    try:
        with client.stream("GET", f"/api/cases/{case_id}/stream") as resp:
            current_ev = None
            for line in resp.iter_lines():
                if time.time() - t0 > max_seconds:
                    break
                if not line:
                    continue
                if line.startswith("event:"):
                    current_ev = line.split(":", 1)[1].strip()
                    events.append(current_ev)
                    if current_ev == "awaiting_approval" and not autonomous:
                        threading.Thread(target=trigger_approval, daemon=True).start()
                elif line.startswith("data:") and current_ev:
                    try:
                        payloads[current_ev] = json.loads(line[5:].strip())
                    except Exception:
                        payloads[current_ev] = line[5:].strip()
                    if current_ev in ("outcome", "error"):
                        break
    except Exception as e:
        return {
            "success": False,
            "seconds": round(time.time() - t0, 2),
            "status": f"Stream exception: {e}",
            "api_stats": {}
        }

    dur = round(time.time() - t0, 2)
    outcome_data = payloads.get("outcome", {})
    success = "outcome" in events
    return {
        "case_id": case_id,
        "success": success,
        "seconds": dur,
        "claimed": outcome_data.get("claimed", 0.0),
        "recovered": outcome_data.get("recovered", 0.0),
        "vendor_offer": outcome_data.get("vendor_offer", 0.0),
        "status": outcome_data.get("status", "No status"),
        "rounds": outcome_data.get("rounds", 0),
        "api_stats": outcome_data.get("api_stats", {})
    }

def main():
    print("=" * 85)
    print(" ITEM 1: LIVE VS CACHE TRUTH & RELIABILITY VERIFICATION ")
    print("=" * 85)

    # -------------------------------------------------------------
    # PART 1: Run Demo Case 3x LIVE (Unsandboxed, Real Network)
    # -------------------------------------------------------------
    print("\n[PART 1] Running Demo Case 3 Times LIVE (Real Network to muse-spark-1.3):")
    print("-" * 85)
    live_3x_results = []
    for i in range(1, 4):
        print(f"[*] Starting Live Run {i}/3...", flush=True)
        res = run_single_case(vendor_mode="partial_50", autonomous=True)
        live_3x_results.append(res)
        stats = res.get("api_stats", {})
        calls = stats.get("calls_detail", [])
        live_calls = [c for c in calls if c.get("source") == "live"]
        print(f"    Run {i}/3 Complete in {res['seconds']}s | Status: {res['status'][:35]} | Calls: {len(calls)} (Live: {len(live_calls)}) | Tokens: {stats.get('total_tokens', 0)}", flush=True)
        for c in calls:
            print(f"      - {c['step']:<16} : {c['source']} ({c['latency']}s, {c['tokens']} tok)")

    print("\n" + "=" * 85)
    print(" DEMO CASE 3x LIVE RESULTS SUMMARY ")
    print("=" * 85)
    print(f"{'Run':<6} | {'Seconds':<9} | {'API Calls':<10} | {'Tokens':<8} | {'Recovered':<10} | {'Status Summary'}")
    print("-" * 85)
    for idx, r in enumerate(live_3x_results, 1):
        st = r.get("api_stats", {})
        print(f"Run #{idx:<3} | {r['seconds']:<7}s | {st.get('calls', 0):<10} | {st.get('total_tokens', 0):<8} | Rs. {r.get('recovered', 0):<6} | {r['status'][:30]}")
    print("=" * 85)

    # -------------------------------------------------------------
    # PART 2: Reliability Suite (10x Demo, 3x Deny, 3x Approval)
    # -------------------------------------------------------------
    print("\n[PART 2] Running Reliability Suite (10x Demo, 3x Deny, 3x Approval):")
    print("-" * 85)
    reliability_runs = []

    # 1. 10x Demo
    print("[Section 2.1] 10x Demo Cases (partial 50%, autonomous):")
    for i in range(1, 11):
        res = run_single_case(vendor_mode="partial_50", autonomous=True)
        st_name = f"Demo #{i}"
        dur = res["seconds"]
        stats = res.get("api_stats", {})
        calls = stats.get("calls_detail", [])
        skipped_explanation = ""
        if dur < 5.0:
            cached_steps = [c["step"] for c in calls if c.get("source") == "cache"]
            skipped_explanation = f"Cached replay used for: {', '.join(cached_steps) if cached_steps else 'live API bypassed'}"
        status_label = "COMPLETED" if res["success"] else "FAILED"
        print(f"  {st_name:<10}: {status_label:<9} in {dur:>5.2f}s | Calls: {stats.get('calls', 0)} | Tokens: {stats.get('total_tokens', 0)}" + (f" | Note: {skipped_explanation}" if skipped_explanation else ""))
        reliability_runs.append({
            "name": st_name,
            "status": status_label,
            "seconds": dur,
            "calls": stats.get('calls', 0),
            "tokens": stats.get('total_tokens', 0),
            "note": skipped_explanation or "Full live API calls"
        })

    # 2. 3x Deny
    print("\n[Section 2.2] 3x Deny Cases (deny mode, autonomous):")
    for i in range(1, 4):
        res = run_single_case(vendor_mode="deny", autonomous=True)
        st_name = f"Deny #{i}"
        dur = res["seconds"]
        stats = res.get("api_stats", {})
        calls = stats.get("calls_detail", [])
        skipped_explanation = ""
        if dur < 5.0:
            cached_steps = [c["step"] for c in calls if c.get("source") == "cache"]
            skipped_explanation = f"Cached replay used for: {', '.join(cached_steps) if cached_steps else 'live API bypassed'}"
        status_label = "COMPLETED" if res["success"] else "FAILED"
        print(f"  {st_name:<10}: {status_label:<9} in {dur:>5.2f}s | Calls: {stats.get('calls', 0)} | Tokens: {stats.get('total_tokens', 0)}" + (f" | Note: {skipped_explanation}" if skipped_explanation else ""))
        reliability_runs.append({
            "name": st_name,
            "status": status_label,
            "seconds": dur,
            "calls": stats.get('calls', 0),
            "tokens": stats.get('total_tokens', 0),
            "note": skipped_explanation or "Full live API calls"
        })

    # 3. 3x Approval
    print("\n[Section 2.3] 3x Approval Mode Cases (partial 50%, autonomous=False):")
    for i in range(1, 4):
        res = run_single_case(vendor_mode="partial_50", autonomous=False)
        st_name = f"Approval #{i}"
        dur = res["seconds"]
        stats = res.get("api_stats", {})
        calls = stats.get("calls_detail", [])
        skipped_explanation = ""
        if dur < 5.0:
            cached_steps = [c["step"] for c in calls if c.get("source") == "cache"]
            skipped_explanation = f"Cached replay used for: {', '.join(cached_steps) if cached_steps else 'live API bypassed'}"
        status_label = "COMPLETED" if res["success"] else "FAILED"
        print(f"  {st_name:<10}: {status_label:<9} in {dur:>5.2f}s | Calls: {stats.get('calls', 0)} | Tokens: {stats.get('total_tokens', 0)}" + (f" | Note: {skipped_explanation}" if skipped_explanation else ""))
        reliability_runs.append({
            "name": st_name,
            "status": status_label,
            "seconds": dur,
            "calls": stats.get('calls', 0),
            "tokens": stats.get('total_tokens', 0),
            "note": skipped_explanation or "Full live API calls"
        })

    # Summary table
    print("\n" + "=" * 85)
    print(" RELIABILITY SUITE RESULTS SUMMARY TABLE ")
    print("=" * 85)
    print(f"{'Run Name':<12} | {'Status':<9} | {'Duration':<9} | {'Calls':<6} | {'Tokens':<8} | {'Execution Details'}")
    print("-" * 85)
    for r in reliability_runs:
        print(f"{r['name']:<12} | {r['status']:<9} | {r['seconds']:<7}s | {r['calls']:<6} | {r['tokens']:<8} | {r['note'][:30]}")
    print("=" * 85)

    comp_rate = sum(1 for r in reliability_runs if r["status"] == "COMPLETED")
    print(f"Completion Rate: {comp_rate}/16 ({comp_rate/16*100:.1f}%)\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())

