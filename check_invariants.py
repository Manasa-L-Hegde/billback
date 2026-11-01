import sqlite3
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("billback.db")

def parse_utc_timestamp(ts_str):
    if not ts_str:
        return datetime.now(timezone.utc)
    ts_str = ts_str.replace("T", " ").split(".")[0]
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def run_invariant_checks():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 80)
    print(" BILLBACK INVARIANT CHECKER (SQLite Integrity Audit) ")
    print("=" * 80)

    if not DB_PATH.exists():
        print(f"Database {DB_PATH} not found!")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cases = cur.execute("""
        SELECT id, created_at, vendor, status, claimed, recovered,
               min_accept_percent, email_draft, findings_json, transcript_json
        FROM cases
    """).fetchall()

    print(f"Total cases inspected: {len(cases)}\n")

    violations_a = []
    violations_b = []
    violations_c = []
    violations_d = []

    now_utc = datetime.now(timezone.utc)

    for c in cases:
        case_id = c["id"]
        status = c["status"] or ""
        claimed = float(c["claimed"] or 0.0)
        recovered = float(c["recovered"] or 0.0)
        min_pct = float(c["min_accept_percent"] or 80.0)
        email_draft = c["email_draft"] or ""
        findings_raw = c["findings_json"]
        created_at_dt = parse_utc_timestamp(c["created_at"])
        age_minutes = (now_utc - created_at_dt).total_seconds() / 60.0

        # Invariant (a): Completed with recovered < min_accept_percent * claimed (unless status is escalated)
        floor = round(claimed * (min_pct / 100.0), 2)
        is_escalated = "escalat" in status.lower()

        if status.lower() == "completed" and claimed > 0 and not is_escalated:
            if recovered < (floor - 0.01):
                violations_a.append({
                    "case_id": case_id,
                    "claimed": claimed,
                    "recovered": recovered,
                    "floor": floor,
                    "min_pct": min_pct,
                    "status": status,
                    "reason": f"Status is 'completed' but recovered Rs. {recovered:.2f} < Rs. {floor:.2f} ({min_pct}% floor of claimed Rs. {claimed:.2f}) and DB status is not escalated"
                })

        # Invariant (b): Any email sent/drafted for a case with claimed = 0
        if claimed <= 0.0:
            if email_draft.strip():
                violations_b.append({
                    "case_id": case_id,
                    "claimed": claimed,
                    "email_draft_preview": email_draft[:100].replace("\n", " "),
                    "reason": f"Dispute email drafted/sent for case with claimed = Rs. {claimed:.2f}"
                })

        # Invariant (c): Any rupee amount in sent/drafted email not present in audit findings
        if email_draft.strip() and findings_raw:
            try:
                findings_data = json.loads(findings_raw)
                findings_list = findings_data.get("findings", []) if isinstance(findings_data, dict) else []
                total_overcharge = float(findings_data.get("total_overcharge", claimed) if isinstance(findings_data, dict) else claimed)
                
                valid_numbers = {round(claimed, 2), round(total_overcharge, 2)}
                for f in findings_list:
                    ov = f.get("overcharge")
                    if ov is not None:
                        valid_numbers.add(round(float(ov), 2))
                    # Also include numbers mentioned in the audit finding reason
                    reason_str = str(f.get("reason", ""))
                    for n in re.findall(r"[0-9]+(?:\.[0-9]+)?", reason_str):
                        try:
                            valid_numbers.add(round(float(n), 2))
                        except Exception:
                            pass

                # Extract rupee numbers from email: Rs. 123.45, Rs 123, INR 123, ₹123
                email_rupee_matches = re.findall(r"(?:Rs\.?|INR|₹)\s*([0-9]+(?:\.[0-9]+)?)", email_draft, re.IGNORECASE)
                for amt_str in email_rupee_matches:
                    amt = round(float(amt_str), 2)
                    if amt not in valid_numbers:
                        violations_c.append({
                            "case_id": case_id,
                            "amount": amt,
                            "valid_numbers": sorted(list(valid_numbers)),
                            "reason": f"Email mentions Rs. {amt} which is absent from audit findings"
                        })
            except Exception as ex:
                violations_c.append({
                    "case_id": case_id,
                    "reason": f"Failed to parse findings JSON for validation: {ex}"
                })

        # Invariant (d): Stuck in running / created / awaiting_approval > 10 min
        if status.lower() in ["running", "created", "awaiting_approval"]:
            if age_minutes > 10.0:
                violations_d.append({
                    "case_id": case_id,
                    "status": status,
                    "created_at": c["created_at"],
                    "age_minutes": round(age_minutes, 1)
                })
                # Mark as abandoned
                cur.execute("UPDATE cases SET status = 'abandoned' WHERE id = ?", (case_id,))

    conn.commit()
    conn.close()

    # Reporting
    print("-" * 80)
    print("INVARIANT (a): Completed cases meeting recovery floor")
    if violations_a:
        print(f"FAILED: {len(violations_a)} violation(s) found:")
        for v in violations_a:
            print(f"  [!] Case {v['case_id']}: {v['reason']}")
    else:
        print("  PASS: All completed cases satisfy minimum recovery floor or are marked escalated.")

    print("\nINVARIANT (b): No dispute email sent/drafted when claimed = 0")
    if violations_b:
        print(f"FAILED: {len(violations_b)} violation(s) found:")
        for v in violations_b:
            print(f"  [!] Case {v['case_id']}: {v['reason']}")
    else:
        print("  PASS: Zero emails sent/drafted for zero-overcharge cases.")

    print("\nINVARIANT (c): All rupee amounts in dispute emails match verified audit findings")
    if violations_c:
        print(f"FAILED: {len(violations_c)} violation(s) found:")
        for v in violations_c:
            print(f"  [!] Case {v['case_id']}: {v['reason']}")
    else:
        print("  PASS: Every rupee amount in drafted emails originates from verified audit findings.")

    print("\nINVARIANT (d): Detection of abandoned cases (> 10 min inactivity)")
    if violations_d:
        print(f"FLAGGED: {len(violations_d)} abandoned case(s) detected and updated to 'abandoned':")
        for v in violations_d:
            print(f"  [*] Case {v['case_id']} was stuck in '{v['status']}' for {v['age_minutes']} mins (created {v['created_at']}) -> Marked 'abandoned'")
    else:
        print("  PASS: No stale cases stuck in pending/running states.")

    print("-" * 80)
    total_violations = len(violations_a) + len(violations_b) + len(violations_c)
    if total_violations > 0 or violations_d:
        print(f"RESULT: {total_violations} invariant violation(s) and {len(violations_d)} abandoned case(s) found.")
    else:
        print("RESULT: ALL INVARIANTS SATISFIED (Clean audit pass).")
    print("=" * 80)

    return total_violations

if __name__ == "__main__":
    viols = run_invariant_checks()
    if viols > 0:
        sys.exit(2)
    sys.exit(0)
