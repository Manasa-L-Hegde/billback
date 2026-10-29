import json, sys
from pathlib import Path
from audit import audit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUTPUTS_DIR = Path("outputs")
TRUTH_DIR = Path("samples/truth")
AGREED_RATES_FILE = Path("samples/agreed_rates.json")

TEST_CASES = [
    {
        "bill": "test_bill1",
        "slip": None,
        "expected_error": "line_math",
        "description": "Qty x Rate != Line Amount (Gel Pens)"
    },
    {
        "bill": "test_bill2",
        "slip": None,
        "expected_error": "subtotal",
        "description": "Line items do not add up to Subtotal"
    },
    {
        "bill": "test_bill3",
        "slip": "test_slip3",
        "expected_error": "delivery_fee",
        "description": "Delivery charge added but slip says free delivery"
    },
    {
        "bill": "test_bill4",
        "slip": None,
        "expected_error": "rate",
        "description": "Rate higher than agreed rate (Rice)"
    },
    {
        "bill": "test_bill5",
        "slip": "test_slip5",
        "expected_error": "not_delivered",
        "description": "Item duplicate billed / not delivered (Cooking Oil)"
    },
    {
        "bill": "test_bill6",
        "slip": None,
        "expected_error": None,
        "description": "Fully correct bill (zero errors expected)"
    },
    {
        "bill": "test_bill4",
        "slip": None,
        "custom_rates": {"rice": 55.0},
        "expected_error": "rate",
        "description": "Token-containment test: Hinglish key 'rice' matches 'Sona Masoori Rice'"
    }
]

def load_json(name):
    # Prefer outputs/ then fallback to samples/truth/
    out_path = OUTPUTS_DIR / f"{name}.json"
    if out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))
    truth_path = TRUTH_DIR / f"{name}.json"
    if truth_path.exists():
        return json.loads(truth_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Neither {out_path} nor {truth_path} found")

def run_audit_eval():
    agreed = json.loads(AGREED_RATES_FILE.read_text(encoding="utf-8")) if AGREED_RATES_FILE.exists() else None

    print(f"\n{'='*75}")
    print(f"{'AUDIT ENGINE EVALUATION (7 TEST CASES)':^75}")
    print(f"{'='*75}\n")

    planted_total = sum(1 for tc in TEST_CASES if tc["expected_error"] is not None)
    planted_caught = 0
    false_alarms = 0

    for idx, tc in enumerate(TEST_CASES, 1):
        bill_data = load_json(tc["bill"])
        slip_data = load_json(tc["slip"]) if tc["slip"] else None
        case_rates = tc.get("custom_rates") or agreed
        
        res = audit(bill_data, slip=slip_data, agreed=case_rates)
        findings = res.get("findings", [])
        expected = tc["expected_error"]

        found_types = [f["type"] for f in findings]
        print(f"[{idx}/{len(TEST_CASES)}] Bill: {tc['bill']} ({tc['description']})")
        if slip_data:
            print(f"      Matched Slip: {tc['slip']}")
        print(f"      Findings ({len(findings)}):")

        for f in findings:
            print(f"        - [{f['type']}] {f['item']}: overcharge Rs. {f['overcharge']} ({f['reason']})")

        if expected is not None:
            if expected in found_types:
                planted_caught += 1
                # Any findings of a different type?
                extras = [t for t in found_types if t != expected]
                false_alarms += len(extras)
                status = "PASS (Planted error caught)"
            else:
                status = "FAIL (Planted error missed)"
        else:
            # Expected zero findings
            if len(findings) == 0:
                status = "PASS (Clean bill verified, 0 findings)"
            else:
                false_alarms += len(findings)
                status = f"FAIL ({len(findings)} false alarms on clean bill)"

        print(f"      Status: {status}\n")

    print(f"{'='*75}")
    print(f"EVALUATION SUMMARY:")
    print(f"  Planted errors caught : {planted_caught} / {planted_total} ({planted_caught/planted_total*100:.1f}%)")
    print(f"  False alarms          : {false_alarms}")
    if planted_caught == planted_total and false_alarms == 0:
        print(f"  RESULT                : PERFECT SCORE (5/5 caught, 0 false alarms)")
    else:
        print(f"  RESULT                : Review discrepancies above")
    print(f"{'='*75}\n")

if __name__ == "__main__":
    run_audit_eval()
