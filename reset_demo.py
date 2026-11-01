import sqlite3
import sys
from pathlib import Path
from drift import init_db, seed_vendor_history, DB_PATH

def reset_demo():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print(" BILLBACK DEMO RESET & HYGIENE ")
    print("=" * 70)

    init_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Wipe all cases
    cur.execute("DELETE FROM cases")
    cases_deleted = cur.rowcount
    print(f"[*] Cleared cases table: {cases_deleted} rows removed.")

    # 2. Wipe item history
    cur.execute("DELETE FROM item_history")
    items_deleted = cur.rowcount
    print(f"[*] Cleared item_history table: {items_deleted} rows removed.")

    # Reset SQLite autoincrement sequence
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('cases', 'item_history')")
    conn.commit()
    conn.close()

    # 3. Re-seed 4 older drift invoices with seeded=true flag
    seed_vendor_history()

    # 4. Verify clean DB state
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cases")
    cases_count = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(recovered), 0) FROM cases")
    total_recovered = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM item_history WHERE seeded = 1")
    seeded_items = cur.fetchone()[0]
    conn.close()

    print("-" * 70)
    print(f"DB State Verification:")
    print(f"  Cases Count          : {cases_count}")
    print(f"  Total Recovered Sum  : Rs. {total_recovered:.2f}")
    print(f"  Seeded Drift Records : {seeded_items} items (seeded=true)")
    print("=" * 70)
    print("RESET COMPLETE: Clean workspace ready for demo.\n")

if __name__ == "__main__":
    reset_demo()

