import os, json, sys, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from extract import extract
from audit import audit
from agreement import extract_agreement

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
MODEL, MAX_STEPS = "muse-spark-1.3", 8
rates = Path("samples/agreed_rates.json")
AGREED = json.loads(rates.read_text(encoding="utf-8")) if rates.exists() else {}
STATE = {}

SYSTEM = """You are BillBack, an agent that audits a small shop's bill and recovers overcharges.
Work in this order:
1. Call extract_document for the invoice, and for the delivery slip if one is given.
   If an agreement photo or transcript is given, call read_agreement.
2. Call run_audit.
3. If total_overcharge > 0, call send_dispute_email: polite, firm, one line per finding with the
   exact numbers from run_audit, the total claimed, and a request for a corrected invoice or credit note.
4. If there are no findings, do NOT send an email. Say the bill is correct.
Rules: only claim what run_audit reported. Never invent amounts or errors.
End with a 2-3 line summary of what you found and did."""

def t_extract(path, doc_type):
    data = extract(path, doc_type)
    STATE[doc_type] = data
    return data

def t_read_agreement(path):
    data = extract_agreement(path)
    STATE["agreement"] = data
    return data

def t_audit():
    if "invoice" not in STATE:
        return {"error": "extract the invoice first"}
    agreed_rates = None
    if "agreement" in STATE and STATE["agreement"].get("agreed_rates"):
        agreed_rates = STATE["agreement"]["agreed_rates"]
    else:
        agreed_rates = AGREED
    return audit(STATE["invoice"], STATE.get("slip"), agreed_rates)

def t_send(to, subject, body):
    Path("outbox").mkdir(exist_ok=True)
    f = Path("outbox") / f"{int(time.time())}_{os.getpid()}.txt"
    f.write_text(f"To: {to}\nSubject: {subject}\n\n{body}", encoding="utf-8")
    return {"status": "saved (dry run)", "file": str(f)}

FUNCS = {
    "extract_document": t_extract,
    "read_agreement": t_read_agreement,
    "run_audit": t_audit,
    "send_dispute_email": t_send,
}

TOOLS = [
    {"type": "function", "function": {
        "name": "extract_document", "description": "Read a photo of an invoice or delivery slip into structured data.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "doc_type": {"type": "string", "enum": ["invoice", "slip"]}},
            "required": ["path", "doc_type"]}}},
    {"type": "function", "function": {
        "name": "read_agreement", "description": "Extract agreed prices, rates, and delivery terms from a chat screenshot or transcript.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_audit", "description": "Audit the extracted invoice against the slip and agreed rates. Returns findings and total overcharge.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "send_dispute_email", "description": "Send a dispute email to the vendor.",
        "parameters": {"type": "object", "properties": {
            "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
            "required": ["to", "subject", "body"]}}},
]

def run(invoice, slip=None, agreement=None, vendor_email="vendor@example.com"):
    STATE.clear()
    task = (
        f"Invoice photo: {invoice}\n"
        f"Delivery slip photo: {slip or 'none'}\n"
        f"Agreement photo/transcript: {agreement or 'none'}\n"
        f"Vendor email: {vendor_email}"
    )
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    for step in range(1, MAX_STEPS + 1):
        r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, temperature=0)
        msg = r.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return msg.content
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            print(f"[step {step}] {call.function.name}({args if call.function.name != 'send_dispute_email' else '...'})", flush=True)
            try:
                result = FUNCS[call.function.name](**args)
            except Exception as e:
                result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    return "Stopped: step limit reached."

if __name__ == "__main__":
    invoice_arg = sys.argv[1]
    slip_arg = None
    agreement_arg = None
    
    # Simple CLI argument parsing
    for arg in sys.argv[2:]:
        if arg == "-":
            continue
        if "slip" in arg.lower():
            slip_arg = arg
        elif "chat" in arg.lower() or "agreement" in arg.lower() or "note" in arg.lower():
            agreement_arg = arg
        elif not slip_arg:
            slip_arg = arg
        elif not agreement_arg:
            agreement_arg = arg

    print("\n" + run(invoice_arg, slip_arg, agreement_arg))
