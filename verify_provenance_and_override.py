import sys, time, json
from pathlib import Path
from extract import extract
from agreement import extract_agreement
from audit import audit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=" * 80)
    print(" TASK 2 PROVENANCE & AGREEMENT OVERRIDE VERIFICATION ")
    print("=" * 80)

    # 1. State how test_chat3.json was created
    chat3_path = Path("outputs/test_chat3.json")
    print("[1] PROVENANCE OF test_chat3.json:")
    print("    Deleted pre-existing test_chat3.json and regenerated LIVE using muse-spark-1.3.")
    if chat3_path.exists():
        chat3_data = json.loads(chat3_path.read_text(encoding="utf-8"))
        print(f"    Source       : {chat3_data.get('_source')}")
        print(f"    Latency      : {chat3_data.get('_latency')}s")
        print(f"    Tokens       : {chat3_data.get('_tokens')}")
        print(f"    Agreed Rates : {chat3_data.get('agreed_rates')}")
        print(f"    Free Delivery: {chat3_data.get('free_delivery')}")
        print(f"    Source Quote : {chat3_data.get('source_quote')}")
    else:
        print("    [!] Error: test_chat3.json not found!")

    # 2. Extract bill4 and chat1 live
    print("\n[2] EXTRACTING bill4 + chat1 (Sona Masoori Rice rate dispute):")
    t0 = time.time()
    inv_data = extract("samples/test_bill4.jpg", "invoice")
    print(f"    Invoice Extracted : {inv_data.get('vendor')}, items: {len(inv_data.get('items', []))} (Source: {inv_data.get('_source')}, {inv_data.get('_latency')}s)")

    chat_data = extract_agreement("samples/test_chat1.jpg")
    print(f"    Chat Extracted    : {chat_data.get('agreed_rates')} (Source: {chat_data.get('_source')}, {chat_data.get('_latency')}s)")

    # Baseline audit with chat agreement
    baseline_audit = audit(inv_data, None, chat_data.get("agreed_rates"))
    baseline_overcharge = baseline_audit["total_overcharge"]
    print(f"    Baseline Claim    : Rs. {baseline_overcharge} (Findings: {[f['item'] + ': ' + str(f['overcharge']) for f in baseline_audit['findings']]})")

    # 3. Modify agreed_rates.json to rice=99
    agreed_file = Path("samples/agreed_rates.json")
    original_agreed_text = agreed_file.read_text(encoding="utf-8")
    try:
        rates = json.loads(original_agreed_text)
        rates["sona masoori rice"] = 99.0
        rates["rice"] = 99.0
        agreed_file.write_text(json.dumps(rates, indent=2), encoding="utf-8")
        print("\n[3] MUTATING agreed_rates.json:")
        print(f"    Temporarily set 'sona masoori rice' = 99.0 in samples/agreed_rates.json")

        # Rerun audit with chat agreement: specific chat rate must take precedence
        override_audit = audit(inv_data, None, chat_data.get("agreed_rates"))
        override_overcharge = override_audit["total_overcharge"]
        print(f"    Rerun Audit Claim : Rs. {override_overcharge}")
        print(f"    Findings          : {[f['item'] + ': ' + str(f['overcharge']) for f in override_audit['findings']]}")

        assert override_overcharge == baseline_overcharge, f"Overcharge changed! {override_overcharge} != {baseline_overcharge}"
        print(f"\n[+] VERIFICATION RESULT: PASS - Overcharge remained exactly Rs. {override_overcharge} despite agreed_rates.json having rice=99.0.")
    finally:
        # Restore original agreed_rates.json
        agreed_file.write_text(original_agreed_text, encoding="utf-8")
        print("    Restored original samples/agreed_rates.json.")

    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())

