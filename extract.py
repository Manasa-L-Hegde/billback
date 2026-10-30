import os, sys, json, base64, re, mimetypes
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

def extract(path, doc_type="invoice"):
    for attempt in range(2):  # retry once if the JSON is broken
        r = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": PROMPTS[doc_type]},
                _image_part(path),
            ]}],
        )
        try:
            return _parse_json(r.choices[0].message.content)
        except json.JSONDecodeError:
            if attempt == 1:
                raise

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

