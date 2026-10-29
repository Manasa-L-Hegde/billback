import json, sys, difflib
from pathlib import Path

TOL = 0.5
norm = lambda s: " ".join(str(s).lower().split())

def match(name, keys):
    n = norm(name)
    for k in keys:
        if k in n or n in k:
            return k
    m = difflib.get_close_matches(n, keys, n=1, cutoff=0.6)
    return m[0] if m else None

def audit(bill, slip=None, agreed=None):
    out = []
    def add(kind, item, amt, why):
        out.append({"type": kind, "item": item, "overcharge": round(amt, 2), "reason": why})

    items = bill.get("items", [])

    # 1. line math
    for it in items:
        q, r, a = it.get("qty"), it.get("rate"), it.get("amount")
        if None not in (q, r, a) and abs(q * r - a) > TOL:
            add("line_math", it["name"], a - q * r, f"{q} x {r} = {q*r:.2f}, billed {a}")

    # 2. subtotal and grand total
    line_sum = sum(it.get("amount") or 0 for it in items)
    sub = bill.get("subtotal")
    if sub is not None and sub - line_sum > TOL:
        add("subtotal", "subtotal", sub - line_sum, f"items add to {line_sum:.2f}, subtotal says {sub}")
    gt = bill.get("grand_total")
    if None not in (gt, sub):
        expected = sub + (bill.get("tax_total") or 0) + (bill.get("delivery_charge") or 0)
        if gt - expected > TOL:
            add("grand_total", "grand total", gt - expected, f"parts add to {expected:.2f}, total says {gt}")

    # 3. delivery charge vs slip
    dc = bill.get("delivery_charge") or 0
    if slip and dc > 0:
        free = slip.get("delivery_charge") == 0 or "free" in str(slip.get("notes", "")).lower()
        if free:
            add("delivery_fee", "delivery", dc, "bill charges delivery but the slip says free delivery")

    # 4. rate above agreed
    if agreed:
        keys = list(agreed)
        for it in items:
            k = match(it["name"], keys)
            if k and it.get("rate") and it.get("qty") and it["rate"] > agreed[k] + 0.01:
                add("rate", it["name"], (it["rate"] - agreed[k]) * it["qty"],
                    f"billed {it['rate']}/unit, agreed {agreed[k]}/unit")

    # 5. billed more than delivered (covers duplicates)
    if slip:
        delivered = {}
        for s in slip.get("items", []):
            delivered[norm(s["name"])] = delivered.get(norm(s["name"]), 0) + (s.get("qty") or 0)
        billed, rate_of = {}, {}
        for it in items:
            k = match(it["name"], list(delivered)) or norm(it["name"])
            billed[k] = billed.get(k, 0) + (it.get("qty") or 0)
            rate_of[k] = it.get("rate") or 0
        for k, bq in billed.items():
            dq = delivered.get(k, 0)
            if bq > dq:
                add("not_delivered", k, (bq - dq) * rate_of[k], f"billed {bq}, slip shows {dq} delivered")

    return {"findings": out, "total_overcharge": round(sum(f["overcharge"] for f in out), 2)}

if __name__ == "__main__":
    bill = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    slip = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    agreed = json.loads(Path("samples/agreed_rates.json").read_text(encoding="utf-8")) if Path("samples/agreed_rates.json").exists() else None
    print(json.dumps(audit(bill, slip, agreed), indent=2, ensure_ascii=False))

