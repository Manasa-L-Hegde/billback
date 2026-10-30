import os, sys, json, time, uuid, asyncio, sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from drift import init_db, DB_PATH, record_invoice_items, detect_drift, seed_vendor_history
from extract import extract
from audit import audit
from agreement import extract_agreement
from email_tools import send_email
from vendor_sim import simulate_vendor_reply

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

init_db()
seed_vendor_history()

app = FastAPI(title="BillBack API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Active running cases state & pub-sub queues for SSE
CASE_EVENT_HISTORY = {} # case_id -> list of {"event": ..., "data": ...}
CASE_SUBSCRIBERS = {}    # case_id -> list of asyncio.Queue
CASE_RUNNING_TASKS = {}
CASE_APPROVAL_EVENTS = {}
CASE_EDITED_EMAILS = {}

async def _publish_event(case_id: str, event_type: str, data: dict):
    msg = {"event": event_type, "data": data}
    CASE_EVENT_HISTORY.setdefault(case_id, []).append(msg)
    subs = CASE_SUBSCRIBERS.get(case_id, [])
    for q in list(subs):
        await q.put(msg)

class ApprovalPayload(BaseModel):
    edited_subject: Optional[str] = None
    edited_body: Optional[str] = None

class DemoCasePayload(BaseModel):
    vendor_mode: Optional[str] = "partial_50"
    min_accept_percent: Optional[float] = 80.0
    autonomous: Optional[bool] = False

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.post("/api/cases/demo")
def create_demo_case(payload: DemoCasePayload):
    case_id = f"demo_case_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # Copy bill5 and slip5 sample images
    inv_src = Path("samples/test_bill5.jpg")
    slip_src = Path("samples/test_slip5.jpg")
    
    inv_dst = case_dir / "test_bill5.jpg"
    slip_dst = case_dir / "test_slip5.jpg"
    
    inv_dst.write_bytes(inv_src.read_bytes())
    slip_dst.write_bytes(slip_src.read_bytes())

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO cases (
        id, invoice_file, slip_file, agreement_file, vendor_email, 
        vendor_mode, min_accept_percent, autonomous, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_id, str(inv_dst), str(slip_dst), 
        None, "vendor@example.com",
        payload.vendor_mode or "partial_50", 
        payload.min_accept_percent or 80.0, 
        1 if payload.autonomous else 0, "created"
    ))
    conn.commit()
    conn.close()

    return {"case_id": case_id, "status": "created"}

@app.get("/api/cases")
def list_cases():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM cases ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.get("/api/vendors/{name}/drift")
def get_vendor_drift(name: str):
    return {"vendor": name, "alerts": detect_drift(name)}

@app.get("/api/drift")
def get_all_drift():
    return {"alerts": detect_drift()}

@app.post("/api/cases")
async def create_case(
    invoice: UploadFile = File(...),
    slip: Optional[UploadFile] = File(None),
    agreement_file: Optional[UploadFile] = File(None),
    agreement_text: Optional[str] = Form(None),
    vendor_email: str = Form("vendor@example.com"),
    vendor_mode: str = Form("realistic"),
    min_accept_percent: float = Form(80.0),
    autonomous: bool = Form(True)
):
    case_id = f"case_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    inv_path = case_dir / invoice.filename
    inv_bytes = await invoice.read()
    inv_path.write_bytes(inv_bytes)

    slip_path = None
    if slip:
        slip_path = case_dir / slip.filename
        slip_path.write_bytes(await slip.read())

    agreed_path = None
    if agreement_file:
        agreed_path = case_dir / agreement_file.filename
        agreed_path.write_bytes(await agreement_file.read())
    elif agreement_text and agreement_text.strip():
        agreed_path = case_dir / "agreement_transcript.txt"
        agreed_path.write_text(agreement_text.strip(), encoding="utf-8")

    # Insert case in SQLite
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO cases (
        id, invoice_file, slip_file, agreement_file, vendor_email, 
        vendor_mode, min_accept_percent, autonomous, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_id, str(inv_path), str(slip_path) if slip_path else None, 
        str(agreed_path) if agreed_path else None, vendor_email,
        vendor_mode, min_accept_percent, 1 if autonomous else 0, "created"
    ))
    conn.commit()
    conn.close()

    return {"case_id": case_id, "status": "created"}

async def execute_case_workflow(case_id: str):
    """Orchestrates agent execution and yields SSE event payloads."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    c_row = dict(cur.fetchone())
    conn.close()

    inv_path = c_row["invoice_file"]
    slip_path = c_row["slip_file"]
    agreed_path = c_row["agreement_file"]
    vendor_email = c_row["vendor_email"]
    vendor_mode = c_row["vendor_mode"] or "realistic"
    min_accept_pct = float(c_row["min_accept_percent"] or 80.0)
    autonomous = bool(c_row["autonomous"])

    state = {}

    async def emit(event_type: str, data: dict):
        await _publish_event(case_id, event_type, data)

    try:
        # Step 1: Extract Invoice
        await emit("tool_start", {"step": 1, "tool": "extract_document", "doc_type": "invoice", "path": inv_path})
        inv_data = extract(inv_path, "invoice")
        state["invoice"] = inv_data
        record_invoice_items(inv_data)
        await emit("tool_result", {"step": 1, "tool": "extract_document", "doc_type": "invoice", "result": inv_data})

        # Step 2: Extract Slip if present
        if slip_path:
            await emit("tool_start", {"step": 2, "tool": "extract_document", "doc_type": "slip", "path": slip_path})
            slip_data = extract(slip_path, "slip")
            state["slip"] = slip_data
            await emit("tool_result", {"step": 2, "tool": "extract_document", "doc_type": "slip", "result": slip_data})

        # Step 3: Extract Agreement if present
        if agreed_path:
            await emit("tool_start", {"step": 3, "tool": "read_agreement", "path": agreed_path})
            agreed_data = extract_agreement(agreed_path)
            state["agreement"] = agreed_data
            await emit("tool_result", {"step": 3, "tool": "read_agreement", "result": agreed_data})

        # Step 4: Run Audit
        await emit("tool_start", {"step": 4, "tool": "run_audit"})
        agreed_rates = None
        if "agreement" in state and state["agreement"].get("agreed_rates"):
            agreed_rates = state["agreement"]["agreed_rates"]
        else:
            rates_file = Path("samples/agreed_rates.json")
            agreed_rates = json.loads(rates_file.read_text(encoding="utf-8")) if rates_file.exists() else None

        audit_res = audit(state["invoice"], state.get("slip"), agreed_rates)
        state["audit"] = audit_res
        total_claimed = audit_res.get("total_overcharge", 0.0)
        await emit("tool_result", {"step": 4, "tool": "run_audit", "result": audit_res})

        # Update case record with initial audit findings
        vendor_name = state["invoice"].get("vendor") or "Unknown Vendor"
        inv_no = state["invoice"].get("invoice_no") or "INV"
        
        if total_claimed <= 0:
            outcome = {
                "claimed": 0.0,
                "recovered": 0.0,
                "rounds": 0,
                "status": "Verified: Bill is correct with zero discrepancies."
            }
            await emit("outcome", outcome)
            _update_db_case(case_id, vendor_name, inv_no, "completed", 0.0, 0.0, audit_res, outcome, "")
            await queue.put(None)
            return

        # Step 5: Draft Dispute Email
        vendor_team = vendor_name
        findings_bullets = "\n".join([f"- {f['item']} [{f['type']}]: overcharge Rs. {f['overcharge']} ({f['reason']})" for f in audit_res.get("findings", [])])
        email_subj = f"Billing Dispute - Invoice {inv_no} - Overcharge Rs. {total_claimed}"
        email_body = (
            f"Dear {vendor_team} Accounts Team,\n\n"
            f"Regarding Invoice {inv_no} dated {state['invoice'].get('date')}, our automated audit identified the following billing discrepancy:\n\n"
            f"{findings_bullets}\n\n"
            f"Total Overcharge Claimed: Rs. {total_claimed}\n\n"
            f"Please issue a corrected invoice or credit note for Rs. {total_claimed}.\n\n"
            f"Regards,\nBillBack Audit System"
        )
        
        draft_payload = {"to": vendor_email, "subject": email_subj, "body": email_body}
        await emit("email_draft", draft_payload)

        # Human Approval Check if non-autonomous
        if not autonomous:
            _update_db_case(case_id, vendor_name, inv_no, "awaiting_approval", total_claimed, 0.0, audit_res, None, email_body)
            await emit("awaiting_approval", {"case_id": case_id, "email": draft_payload})
            
            # Wait for approval signal
            approval_event = asyncio.Event()
            CASE_APPROVAL_EVENTS[case_id] = approval_event
            await approval_event.wait()
            del CASE_APPROVAL_EVENTS[case_id]

            if case_id in CASE_EDITED_EMAILS:
                ed = CASE_EDITED_EMAILS.pop(case_id)
                if ed.edited_subject:
                    email_subj = ed.edited_subject
                if ed.edited_body:
                    email_body = ed.edited_body

        # Step 6: Send Email
        send_res = send_email(vendor_email, email_subj, email_body)
        await emit("tool_result", {"tool": "send_dispute_email", "result": send_res})

        # Step 7: Negotiation Loop
        current_body = email_body
        floor_amount = round(total_claimed * (min_accept_pct / 100.0), 2)
        recovered = 0.0
        final_status = "pending"
        transcript = []

        for r_num in range(1, 4):
            v_reply = simulate_vendor_reply(current_body, total_claimed, round_num=r_num, strategy=vendor_mode)
            offer = float(v_reply.get("offer_amount", 0.0))
            
            v_entry = {
                "round": r_num,
                "sender": "Simulated vendor",
                "reply": v_reply["reply_text"],
                "offer": offer
            }
            transcript.append(v_entry)
            await emit("vendor_reply", v_entry)

            if offer >= floor_amount:
                recovered = offer
                final_status = f"Settled in round {r_num}: Vendor granted Rs. {offer} (>= {min_accept_pct}% floor)"
                a_entry = {
                    "round": r_num,
                    "sender": "BillBack Agent",
                    "action": "ACCEPT",
                    "message": f"Settlement accepted: Rs. {offer} meets recovery floor (Rs. {floor_amount}). Case closed."
                }
                transcript.append(a_entry)
                await emit("agent_reply", a_entry)
                break
            else:
                if r_num < 3 and vendor_mode != "deny":
                    counter_text = (
                        f"Dear {vendor_team},\n\nWe cannot accept Rs. {offer}. As documented in our arithmetic and goods receipt audit, "
                        f"the exact overcharge is Rs. {total_claimed}. "
                        f"Please approve credit note of Rs. {total_claimed} to resolve this dispute.\n\nRegards,\nBillBack Audit"
                    )
                    a_entry = {
                        "round": r_num,
                        "sender": "BillBack Agent",
                        "action": "COUNTER",
                        "counter_offer": total_claimed,
                        "message": counter_text
                    }
                    transcript.append(a_entry)
                    await emit("agent_reply", a_entry)
                    current_body = counter_text
                else:
                    final_status = f"Escalated to human: Vendor offered Rs. {offer} after round {r_num} (below Rs. {floor_amount} floor)"
                    a_entry = {
                        "round": r_num,
                        "sender": "BillBack Agent",
                        "action": "ESCALATE",
                        "message": f"Final offer Rs. {offer} rejected. Escalated to human owner for manual collection."
                    }
                    transcript.append(a_entry)
                    await emit("agent_reply", a_entry)
                    recovered = offer
                    break

        outcome = {
            "claimed": total_claimed,
            "recovered": recovered,
            "floor": floor_amount,
            "rounds": len([t for t in transcript if t["sender"] == "BillBack Agent"]),
            "status": final_status,
            "transcript": transcript
        }
        await emit("outcome", outcome)
        _update_db_case(case_id, vendor_name, inv_no, "completed", total_claimed, recovered, audit_res, outcome, email_body)

    except Exception as e:
        err_msg = str(e)
        await emit("error", {"message": err_msg})
        _update_db_case(case_id, "Unknown", "ERR", "error", 0.0, 0.0, None, {"error": err_msg}, "")
    finally:
        for q in list(CASE_SUBSCRIBERS.get(case_id, [])):
            await q.put(None)

def _update_db_case(case_id, vendor, inv_no, status, claimed, recovered, audit_res, outcome, email_draft):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    UPDATE cases SET 
        vendor = ?, invoice_no = ?, status = ?, claimed = ?, recovered = ?,
        findings_json = ?, transcript_json = ?, email_draft = ?
    WHERE id = ?
    """, (
        vendor, inv_no, status, claimed, recovered,
        json.dumps(audit_res, ensure_ascii=False) if audit_res else None,
        json.dumps(outcome, ensure_ascii=False) if outcome else None,
        email_draft,
        case_id
    ))
    conn.commit()
    conn.close()

@app.get("/api/cases/{case_id}/stream")
async def stream_case(case_id: str):
    if case_id not in CASE_RUNNING_TASKS:
        CASE_RUNNING_TASKS[case_id] = asyncio.create_task(execute_case_workflow(case_id))

    sub_q = asyncio.Queue()
    CASE_SUBSCRIBERS.setdefault(case_id, []).append(sub_q)

    # Replay historical events for this case
    past_events = list(CASE_EVENT_HISTORY.get(case_id, []))

    async def event_generator():
        try:
            for ev in past_events:
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
                if ev['event'] in ("outcome", "error"):
                    yield "event: end\ndata: {}\n\n"
                    return

            while True:
                msg = await sub_q.get()
                if msg is None:
                    yield "event: end\ndata: {}\n\n"
                    break
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                if msg['event'] in ("outcome", "error"):
                    yield "event: end\ndata: {}\n\n"
                    break
        finally:
            if case_id in CASE_SUBSCRIBERS and sub_q in CASE_SUBSCRIBERS[case_id]:
                CASE_SUBSCRIBERS[case_id].remove(sub_q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/cases/{case_id}/approve")
def approve_case(case_id: str, payload: Optional[ApprovalPayload] = None):
    if payload:
        CASE_EDITED_EMAILS[case_id] = payload
    if case_id in CASE_APPROVAL_EVENTS:
        CASE_APPROVAL_EVENTS[case_id].set()
        return {"status": "approved", "case_id": case_id}
    
    # Check if case exists in db
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT status FROM cases WHERE id = ?", (case_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"status": "already_processed_or_running", "case_id": case_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)

