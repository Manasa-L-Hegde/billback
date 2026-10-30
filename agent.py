import os, json, sys, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from extract import extract
from audit import audit
from agreement import extract_agreement
from email_tools import send_email
from vendor_sim import simulate_vendor_reply

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ.get("MODEL_API_KEY", ""), timeout=60.0, max_retries=2)
MODEL, MAX_STEPS = "muse-spark-1.3", 10
MIN_ACCEPT_PERCENT_DEFAULT = float(os.environ.get("MIN_ACCEPT_PERCENT", 80.0))
rates_file = Path("samples/agreed_rates.json")
AGREED = json.loads(rates_file.read_text(encoding="utf-8")) if rates_file.exists() else {}

SYSTEM = """You are BillBack, an agent that audits a small shop's bill and recovers overcharges.
Work in this order:
1. Call extract_document for the invoice, and for the delivery slip if one is given.
   If an agreement photo or transcript is given, call read_agreement.
2. Call run_audit.
3. If total_overcharge > 0:
   - Call send_dispute_email: polite, firm, with exact numbers from run_audit, total claimed, and request for credit note.
   - Then call negotiate_settlement to handle the vendor's reply.
4. If there are no findings, do NOT send an email. Say the bill is correct.
Rules:
- Only claim what run_audit reported. Never invent amounts or errors.
- Never settle below the minimum acceptance floor of the claim without escalating.
- End with a clear summary and the final settlement outcome."""

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
    {"type": "function", "function": {
        "name": "negotiate_settlement", "description": "Engage in multi-round dispute negotiation with the vendor's simulated response.",
        "parameters": {"type": "object", "properties": {
            "vendor_strategy": {"type": "string", "enum": ["realistic", "partial_50", "deny", "accept"]}}}}},
]

class CaseSession:
    """Thread-safe, isolated per-case agent session."""
    def __init__(self, invoice, slip=None, agreement=None, vendor_email="vendor@example.com", vendor_strategy=None, min_accept_pct=None):
        self.invoice = invoice
        self.slip = slip
        self.agreement = agreement
        self.vendor_email = vendor_email
        self.vendor_strategy = vendor_strategy or "realistic"
        self.min_accept_pct = min_accept_pct if min_accept_pct is not None else MIN_ACCEPT_PERCENT_DEFAULT
        self.state = {}

    def t_extract(self, path, doc_type):
        data = extract(path, doc_type)
        self.state[doc_type] = data
        return data

    def t_read_agreement(self, path):
        data = extract_agreement(path)
        if not data or not data.get("agreed_rates"):
            return {"error": "Agreement extraction returned empty. Cannot verify terms without valid rates."}
        self.state["agreement"] = data
        return data

    def t_audit(self):
        if "invoice" not in self.state:
            return {"error": "extract the invoice first"}
        agreed_rates = None
        if "agreement" in self.state and self.state["agreement"].get("agreed_rates"):
            agreed_rates = self.state["agreement"]["agreed_rates"]
        else:
            agreed_rates = AGREED
        audit_res = audit(self.state["invoice"], self.state.get("slip"), agreed_rates)
        self.state["audit"] = audit_res
        return audit_res

    def t_send(self, to, subject, body):
        res = send_email(to, subject, body)
        self.state["dispute_email"] = {"to": to, "subject": subject, "body": body}
        return res

    def t_negotiate(self, vendor_strategy=None):
        if "audit" not in self.state:
            return {"error": "run_audit first"}
        
        total_claimed = self.state["audit"].get("total_overcharge", 0.0)
        if total_claimed <= 0:
            return {"status": "no overcharge to negotiate"}

        strategy = vendor_strategy or self.vendor_strategy
        transcript = []
        current_body = self.state.get("dispute_email", {}).get("body", f"Dispute claim of Rs. {total_claimed}")
        
        recovered = 0.0
        status = "pending"
        floor_amount = round(total_claimed * (self.min_accept_pct / 100.0), 2)

        for round_num in range(1, 4):
            v_reply = simulate_vendor_reply(current_body, total_claimed, round_num=round_num, strategy=strategy)
            offer = float(v_reply.get("offer_amount", 0.0))
            
            transcript.append({
                "round": round_num,
                "sender": "Simulated vendor",
                "reply": v_reply["reply_text"],
                "offer": offer
            })
            
            if offer >= floor_amount:
                recovered = offer
                status = f"Settled in round {round_num}: Vendor granted Rs. {offer} (>= {self.min_accept_pct}% floor)"
                transcript.append({
                    "round": round_num,
                    "sender": "BillBack Agent",
                    "action": "ACCEPT",
                    "message": f"Settlement accepted: Rs. {offer} meets/exceeds acceptable recovery threshold ({self.min_accept_pct}% = Rs. {floor_amount}). Case closed."
                })
                break
            else:
                if round_num < 3 and strategy != "deny":
                    counter_text = (
                        f"Dear Vendor,\n\nWe cannot accept Rs. {offer}. As documented in our verified delivery and arithmetic audit, "
                        f"the exact unjustified overcharge is Rs. {total_claimed}. "
                        f"Please credit the full amount of Rs. {total_claimed} to resolve this dispute.\n\nRegards,\nBillBack Audit"
                    )
                    transcript.append({
                        "round": round_num,
                        "sender": "BillBack Agent",
                        "action": "COUNTER",
                        "counter_offer": total_claimed,
                        "message": counter_text
                    })
                    current_body = counter_text
                    if strategy == "partial_50" and round_num == 2:
                        strategy = "accept"
                else:
                    status = f"Escalated to human: Vendor offered Rs. {offer} after round {round_num} (below Rs. {floor_amount} floor)"
                    transcript.append({
                        "round": round_num,
                        "sender": "BillBack Agent",
                        "action": "ESCALATE",
                        "message": f"Final vendor offer Rs. {offer} rejected. Escalated to human owner for formal debt recovery."
                    })
                    recovered = offer
                    break

        outcome = {
            "claimed": total_claimed,
            "recovered": recovered,
            "floor": floor_amount,
            "rounds": len([t for t in transcript if "action" in t]),
            "status": status,
            "transcript": transcript
        }
        self.state["outcome"] = outcome
        return outcome

    def run(self):
        funcs = {
            "extract_document": self.t_extract,
            "read_agreement": self.t_read_agreement,
            "run_audit": self.t_audit,
            "send_dispute_email": self.t_send,
            "negotiate_settlement": self.t_negotiate,
        }

        task = (
            f"Invoice photo: {self.invoice}\n"
            f"Delivery slip photo: {self.slip or 'none'}\n"
            f"Agreement photo/transcript: {self.agreement or 'none'}\n"
            f"Vendor email: {self.vendor_email}"
        )
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
        
        for step in range(1, MAX_STEPS + 1):
            r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, temperature=0)
            msg = r.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                final_summary = msg.content
                if "outcome" in self.state:
                    out = self.state["outcome"]
                    final_summary += f"\n\n--- Final Negotiation Outcome ---\nClaimed: Rs. {out['claimed']} | Recovered: Rs. {out['recovered']} | Rounds: {out['rounds']} | Status: {out['status']}"
                return final_summary
            
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments or "{}")
                call_repr = "..." if call.function.name in ["send_dispute_email", "negotiate_settlement"] else args
                print(f"[step {step}] {call.function.name}({call_repr})", flush=True)
                try:
                    result = funcs[call.function.name](**args)
                except Exception as e:
                    result = {"error": str(e)}
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
                
        return "Stopped: step limit reached."

def run(invoice, slip=None, agreement=None, vendor_email="vendor@example.com", vendor_strategy=None, min_accept_pct=None):
    session = CaseSession(invoice, slip, agreement, vendor_email, vendor_strategy, min_accept_pct)
    return session.run()

if __name__ == "__main__":
    invoice_arg = sys.argv[1]
    slip_arg = None
    agreement_arg = None
    strategy_arg = None
    
    for arg in sys.argv[2:]:
        if arg == "-":
            continue
        if arg in ["realistic", "partial_50", "deny", "accept"]:
            strategy_arg = arg
        elif "slip" in arg.lower():
            slip_arg = arg
        elif "chat" in arg.lower() or "agreement" in arg.lower() or "note" in arg.lower():
            agreement_arg = arg
        elif not slip_arg:
            slip_arg = arg
        elif not agreement_arg:
            agreement_arg = arg

    print("\n" + run(invoice_arg, slip_arg, agreement_arg, vendor_strategy=strategy_arg))
