import sqlite3, json
from pathlib import Path

DB_PATH = Path("billback.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS item_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor TEXT NOT NULL,
        invoice_no TEXT,
        date TEXT,
        item_name TEXT NOT NULL,
        item_norm TEXT NOT NULL,
        rate REAL NOT NULL,
        qty REAL,
        unit TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        vendor TEXT,
        invoice_no TEXT,
        invoice_file TEXT,
        slip_file TEXT,
        agreement_file TEXT,
        vendor_email TEXT,
        vendor_mode TEXT,
        min_accept_percent REAL,
        autonomous INTEGER DEFAULT 1,
        status TEXT,
        claimed REAL DEFAULT 0,
        recovered REAL DEFAULT 0,
        findings_json TEXT,
        transcript_json TEXT,
        email_draft TEXT
    )
    """)
    conn.commit()
    conn.close()

def record_invoice_items(invoice_data):
    vendor = invoice_data.get("vendor") or "Unknown Vendor"
    inv_no = invoice_data.get("invoice_no")
    date_str = invoice_data.get("date") or "2026-10-01"
    items = invoice_data.get("items") or []

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for it in items:
        name = it.get("name")
        rate = it.get("rate")
        qty = it.get("qty")
        unit = it.get("unit")
        if name and rate is not None:
            norm_name = " ".join(str(name).lower().split())
            cur.execute("""
            INSERT INTO item_history (vendor, invoice_no, date, item_name, item_norm, rate, qty, unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (vendor, inv_no, date_str, name, norm_name, float(rate), qty, unit))
    conn.commit()
    conn.close()

def detect_drift(vendor=None, threshold=0.05):
    """
    Detects price drift for a vendor across consecutive invoices.
    Flags increases > 5% (threshold=0.05).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    if vendor:
        cur.execute("""
        SELECT * FROM item_history
        WHERE LOWER(vendor) LIKE LOWER(?)
        ORDER BY item_norm, date ASC, id ASC
        """, (f"%{vendor}%",))
    else:
        cur.execute("""
        SELECT * FROM item_history
        ORDER BY vendor, item_norm, date ASC, id ASC
        """)
        
    rows = cur.fetchall()
    conn.close()

    grouped = {}
    for r in rows:
        key = (r["vendor"], r["item_norm"])
        grouped.setdefault(key, []).append(dict(r))

    drifts = []
    for (v_name, item_norm), history in grouped.items():
        if len(history) < 2:
            continue
        for i in range(1, len(history)):
            prev = history[i - 1]
            curr = history[i]
            p_rate = prev["rate"]
            c_rate = curr["rate"]
            
            if p_rate > 0:
                pct_change = ((c_rate - p_rate) / p_rate) * 100.0
                if (c_rate - p_rate) / p_rate > threshold:
                    drifts.append({
                        "vendor": v_name,
                        "item": curr["item_name"],
                        "prev_invoice": prev.get("invoice_no") or "Prev",
                        "prev_date": prev["date"],
                        "prev_rate": p_rate,
                        "curr_invoice": curr.get("invoice_no") or "Curr",
                        "curr_date": curr["date"],
                        "curr_rate": c_rate,
                        "increase_pct": round(pct_change, 1),
                        "reason": f"Rate increased by {pct_change:.1f}% from Rs. {p_rate:.2f} ({prev['date']}) to Rs. {c_rate:.2f} ({curr['date']})"
                    })

    return drifts

def seed_vendor_history():
    """
    Seeds 4 older historical invoices for 'City Wholesale Mart' to demonstrate price drift tracking.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Check if already seeded
    cur.execute("SELECT COUNT(*) FROM item_history WHERE vendor = 'City Wholesale Mart'")
    count = cur.fetchone()[0]
    if count >= 4:
        conn.close()
        return

    history_invoices = [
        {
            "vendor": "City Wholesale Mart",
            "invoice_no": "CWM-7102",
            "date": "2026-08-01",
            "items": [
                {"name": "Cooking Oil 1L", "rate": 110.0, "qty": 10, "unit": "bottle"},
                {"name": "Sugar 5kg", "rate": 190.0, "qty": 4, "unit": "bag"},
                {"name": "Tea Powder 500g", "rate": 150.0, "qty": 5, "unit": "pack"}
            ]
        },
        {
            "vendor": "City Wholesale Mart",
            "invoice_no": "CWM-7840",
            "date": "2026-08-25",
            "items": [
                {"name": "Cooking Oil 1L", "rate": 115.0, "qty": 8, "unit": "bottle"},
                {"name": "Sugar 5kg", "rate": 195.0, "qty": 5, "unit": "bag"},
                {"name": "Tea Powder 500g", "rate": 150.0, "qty": 4, "unit": "pack"}
            ]
        },
        {
            "vendor": "City Wholesale Mart",
            "invoice_no": "CWM-8311",
            "date": "2026-09-15",
            "items": [
                {"name": "Cooking Oil 1L", "rate": 122.0, "qty": 10, "unit": "bottle"},
                {"name": "Sugar 5kg", "rate": 200.0, "qty": 3, "unit": "bag"},
                {"name": "Tea Powder 500g", "rate": 155.0, "qty": 3, "unit": "pack"}
            ]
        },
        {
            "vendor": "City Wholesale Mart",
            "invoice_no": "CWM-8902",
            "date": "2026-10-05",
            "items": [
                {"name": "Cooking Oil 1L", "rate": 125.0, "qty": 12, "unit": "bottle"},
                {"name": "Sugar 5kg", "rate": 210.0, "qty": 4, "unit": "bag"},
                {"name": "Tea Powder 500g", "rate": 160.0, "qty": 4, "unit": "pack"}
            ]
        }
    ]

    for inv in history_invoices:
        for it in inv["items"]:
            norm_name = " ".join(str(it["name"]).lower().split())
            cur.execute("""
            INSERT INTO item_history (vendor, invoice_no, date, item_name, item_norm, rate, qty, unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (inv["vendor"], inv["invoice_no"], inv["date"], it["name"], norm_name, it["rate"], it["qty"], it["unit"]))
    conn.commit()
    conn.close()
    print("Seeded 4 historical invoices for City Wholesale Mart.")

if __name__ == "__main__":
    init_db()
    seed_vendor_history()
    drifts = detect_drift("City Wholesale Mart")
    print(f"Detected {len(drifts)} price drift alerts for City Wholesale Mart:")
    for d in drifts:
        print(f" - {d['item']}: {d['reason']}")

