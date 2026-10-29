import os, sys, json
from pathlib import Path
from extract import extract, check_math

SAMPLES_DIR = Path("samples")
TRUTH_DIR = Path("samples/truth")
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

def normalize_str(s):
    if s is None:
        return ""
    return "".join(c.lower() for c in str(s) if c.isalnum())

def num_equal(a, b, tol=0.5):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except (ValueError, TypeError):
        return False

def match_item(truth_item, extracted_item, doc_type="invoice"):
    """Check if an extracted line item matches the ground truth exactly."""
    # Name match: substring or normalized match
    t_name = normalize_str(truth_item.get("name", ""))
    e_name = normalize_str(extracted_item.get("name", ""))
    name_matched = (t_name in e_name) or (e_name in t_name)
    if not name_matched:
        return False

    # Qty check
    if not num_equal(truth_item.get("qty"), extracted_item.get("qty")):
        return False

    if doc_type == "invoice":
        # Rate check
        if not num_equal(truth_item.get("rate"), extracted_item.get("rate")):
            return False
        # Amount check
        if not num_equal(truth_item.get("amount"), extracted_item.get("amount")):
            return False

    return True

def evaluate():
    truth_files = sorted(list(TRUTH_DIR.glob("*.json")))
    if not truth_files:
        print("No truth files found in samples/truth/")
        return

    total_truth_items = 0
    total_matched_items = 0
    file_results = []

    print(f"\n{'='*70}")
    print(f"{'EVALUATION REPORT: BILL & SLIP EXTRACTION ACCURACY':^70}")
    print(f"{'='*70}\n")

    for tf in truth_files:
        stem = tf.stem
        # Look for matching image
        img_candidates = list(SAMPLES_DIR.glob(f"{stem}.*"))
        img_candidates = [p for p in img_candidates if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
        if not img_candidates:
            continue
        
        img_path = img_candidates[0]
        doc_type = "slip" if "slip" in stem else "invoice"
        truth_data = json.loads(tf.read_text(encoding="utf-8"))
        truth_items = truth_data.get("items", [])
        
        print(f"--> Processing: {img_path.name} ({doc_type.upper()})...")
        try:
            extracted_data = extract(str(img_path), doc_type=doc_type)
        except Exception as e:
            print(f"    [ERROR] Extraction failed: {e}")
            continue

        if doc_type == "invoice":
            extracted_data["math_issues"] = check_math(extracted_data)

        # Save to outputs/
        out_file = OUTPUTS_DIR / f"{stem}.json"
        out_file.write_text(json.dumps(extracted_data, indent=2, ensure_ascii=False), encoding="utf-8")

        extracted_items = extracted_data.get("items", [])

        # Match truth items against extracted items
        matched_flags = []
        used_extracted_idx = set()

        for t_it in truth_items:
            found = False
            for idx, e_it in enumerate(extracted_items):
                if idx not in used_extracted_idx and match_item(t_it, e_it, doc_type=doc_type):
                    found = True
                    used_extracted_idx.add(idx)
                    break
            matched_flags.append(found)

        n_correct = sum(matched_flags)
        n_total = len(truth_items)
        acc = (n_correct / n_total * 100) if n_total > 0 else 100.0

        total_truth_items += n_total
        total_matched_items += n_correct

        notes = []
        if n_correct < n_total:
            missed = [truth_items[i]["name"] for i, m in enumerate(matched_flags) if not m]
            notes.append(f"Missed/Mismatched: {', '.join(missed)}")
        if doc_type == "invoice" and extracted_data.get("math_issues"):
            notes.append(f"Math issues flagged: {len(extracted_data['math_issues'])}")

        note_str = "; ".join(notes) if notes else "All items extracted accurately"
        file_results.append({
            "sample": img_path.name,
            "type": "Invoice" if doc_type == "invoice" else "Delivery Slip",
            "total": n_total,
            "correct": n_correct,
            "accuracy": acc,
            "notes": note_str
        })

        print(f"    Items: {n_correct}/{n_total} matched exactly ({acc:.1f}%)")
        if extracted_data.get("math_issues"):
            for issue in extracted_data["math_issues"]:
                print(f"    [MATH CHECK]: {issue}")
        print()

    # Overall summary
    overall_acc = (total_matched_items / total_truth_items * 100) if total_truth_items > 0 else 0.0
    print(f"{'='*70}")
    print(f"SUMMARY:")
    print(f"  Total items evaluated : {total_truth_items}")
    print(f"  Total items matched   : {total_matched_items}")
    print(f"  Overall Exact Accuracy: {overall_acc:.2f}%")
    print(f"{'='*70}\n")

    # Update accuracy.md
    md_lines = [
        "# Bill Extraction Accuracy Report",
        "",
        f"**Target:** >= 90% of line items extracted correctly.",
        f"**Overall Accuracy:** **{overall_acc:.2f}%** ({total_matched_items}/{total_truth_items} items matched)",
        "",
        "| Sample | Type | Total Items on Bill | Items Correct | Accuracy (%) | Notes / Discrepancies |",
        "| :--- | :--- | :---: | :---: | :---: | :--- |"
    ]
    for r in file_results:
        md_lines.append(f"| `{r['sample']}` | {r['type']} | {r['total']} | {r['correct']} | {r['accuracy']:.1f}% | {r['notes']} |")

    md_lines.extend([
        "",
        "---",
        "### Summary",
        f"- **Total line items evaluated:** {total_truth_items}",
        f"- **Total items correct:** {total_matched_items}",
        f"- **Overall accuracy:** **{overall_acc:.2f}%**",
        ""
    ])
    
    acc_path = SAMPLES_DIR / "accuracy.md"
    acc_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Updated accuracy report at {acc_path}")

if __name__ == "__main__":
    evaluate()

