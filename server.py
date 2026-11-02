import os, sys, json, time, uuid, asyncio, sqlite3, io, shutil
from pathlib import Path
from typing import Optional
from collections import defaultdict
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Response
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
from reset_demo import reset_demo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PUBLIC_MODE = os.environ.get("PUBLIC_MODE", "0") == "1"

init_db()
seed_vendor_history()

app = FastAPI(title="BillBack API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    """Ensure clean seeded state on server startup (especially Render ephemeral disks)."""
    reset_demo()

# Rate limiting and global caps (Requirement 1)
IP_DEMO_CASE_TIMESTAMPS = defaultdict(list)
IP_CUSTOM_CASE_TIMESTAMPS = defaultdict(list)
IP_CASE_TIMESTAMPS = IP_CUSTOM_CASE_TIMESTAMPS  # backward-compatible alias
GLOBAL_CASE_TIMESTAMPS = []

def clean_timestamps():
    now = time.time()
    one_hour_ago = now - 3600
    one_day_ago = now - 86400
    GLOBAL_CASE_TIMESTAMPS[:] = [t for t in GLOBAL_CASE_TIMESTAMPS if t > one_day_ago]
    for ip in list(IP_DEMO_CASE_TIMESTAMPS.keys()):
        IP_DEMO_CASE_TIMESTAMPS[ip] = [t for t in IP_DEMO_CASE_TIMESTAMPS[ip] if t > one_hour_ago]
        if not IP_DEMO_CASE_TIMESTAMPS[ip]:
            del IP_DEMO_CASE_TIMESTAMPS[ip]
    for ip in list(IP_CUSTOM_CASE_TIMESTAMPS.keys()):
        IP_CUSTOM_CASE_TIMESTAMPS[ip] = [t for t in IP_CUSTOM_CASE_TIMESTAMPS[ip] if t > one_hour_ago]
        if not IP_CUSTOM_CASE_TIMESTAMPS[ip]:
            del IP_CUSTOM_CASE_TIMESTAMPS[ip]

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Key the rate limit on the FIRST X-Forwarded-For value (Render/Nginx proxy)
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"

def check_rate_limits(request_ip: str, is_demo: bool = False):
    clean_timestamps()
    if not PUBLIC_MODE:
        return "ok"
    
    # 1. Global daily cap (150 cases per day)
    if len(GLOBAL_CASE_TIMESTAMPS) >= 150:
        if is_demo:
            return "cached_replay"
        raise HTTPException(
            status_code=429,
            detail="Live demo budget reached. Watch the video or use Try demo case (cached replay, labelled)."
        )
    
    # 2. IP limit: 30 demo cases / hour vs 5 custom cases / hour
    if is_demo:
        if len(IP_DEMO_CASE_TIMESTAMPS[request_ip]) >= 30:
            raise HTTPException(
                status_code=429,
                detail="Rate limit reached: Maximum 30 demo cases per hour per IP. Please try again later or watch the demo video."
            )
    else:
        if len(IP_CUSTOM_CASE_TIMESTAMPS[request_ip]) >= 5:
            raise HTTPException(
                status_code=429,
                detail="Rate limit reached: Maximum 5 cases per hour per IP. Please try again later or watch the demo video."
            )
    return "ok"

def record_case_created(request_ip: str, is_demo: bool = False):
    now = time.time()
    if is_demo:
        IP_DEMO_CASE_TIMESTAMPS[request_ip].append(now)
    else:
        IP_CUSTOM_CASE_TIMESTAMPS[request_ip].append(now)
    GLOBAL_CASE_TIMESTAMPS.append(now)

# Upload validation (Task 1d)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES = {"JPEG", "PNG", "WEBP"}

def validate_image_file(file_bytes: bytes, filename: str):
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File '{filename}' exceeds maximum allowed size of 5 MB."
        )
    is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
    is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = len(file_bytes) > 12 and file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type for '{filename}'. Only JPG, PNG, and WebP images are allowed (verified by file content)."
        )
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
        if img.format not in ALLOWED_IMAGE_TYPES:
            raise ValueError(f"Format not allowed: {img.format}")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or corrupted image content in '{filename}'. Only valid JPG, PNG, and WebP images are permitted."
        )

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
CASE_APPROVED_SET = set()
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
    autonomous: Optional[bool] = True
    demo_pacing: Optional[bool] = True

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/health")
def health_check():
    clean_timestamps()
    return {
        "status": "ok",
        "public_mode": PUBLIC_MODE,
        "cases_today": len(GLOBAL_CASE_TIMESTAMPS),
        "budget_reached": len(GLOBAL_CASE_TIMESTAMPS) >= 150,
        "budget_cap": 150
    }

@app.post("/api/cases/demo")
def create_demo_case(request: Request, response: Response, payload: DemoCasePayload):
    client_ip = get_client_ip(request)
    limit_status = check_rate_limits(client_ip, is_demo=True)
    record_case_created(client_ip, is_demo=True)

    session_id = request.cookies.get("bb_session")
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex}"
        response.set_cookie(key="bb_session", value=session_id, httponly=True, samesite="lax", max_age=30 * 24 * 3600, path="/")

    case_id = f"demo_case_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # Copy bill5, slip5, and chat sample images (Task 2)
    inv_src = Path("samples/test_bill5.jpg")
    slip_src = Path("samples/test_slip5.jpg")
    chat_src = Path("samples/test_chat3.jpg")
    
    inv_dst = case_dir / "test_bill5.jpg"
    slip_dst = case_dir / "test_slip5.jpg"
    chat_dst = case_dir / "test_chat3.jpg"
    
    inv_dst.write_bytes(inv_src.read_bytes())
    slip_dst.write_bytes(slip_src.read_bytes())
    chat_dst.write_bytes(chat_src.read_bytes())

    # In public mode, never use client vendor email
    v_email = "simulated-vendor@example.com" if PUBLIC_MODE else "vendor@example.com"
    force_cache_flag = 1 if (limit_status == "cached_replay" or payload.vendor_mode == "cached") else 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO cases (
        id, invoice_file, slip_file, agreement_file, vendor_email, 
        vendor_mode, min_accept_percent, autonomous, demo_pacing, status, force_cache, session_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_id, str(inv_dst), str(slip_dst), 
        str(chat_dst), v_email,
        payload.vendor_mode or "partial_50", 
        payload.min_accept_percent if payload.min_accept_percent is not None else 80.0, 
        1 if payload.autonomous else 0,
        1 if (payload.demo_pacing is not False) else 0,
        "created",
        force_cache_flag,
        session_id
    ))
    conn.commit()
    conn.close()

    return {"case_id": case_id, "status": "created", "force_cache": bool(force_cache_flag)}

@app.get("/api/cases")
def list_cases(request: Request):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if PUBLIC_MODE:
        session_id = request.cookies.get("bb_session") or ""
        cur.execute("SELECT * FROM cases WHERE session_id = ? ORDER BY created_at DESC", (session_id,))
    else:
        cur.execute("SELECT * FROM cases ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.post("/api/dev/reset")
def dev_reset_cases():
    if PUBLIC_MODE:
        raise HTTPException(status_code=403, detail="Dev reset endpoint is disabled in public mode.")
    from reset_demo import reset_demo
    reset_demo()
    return {"status": "ok", "message": "Demo data wiped and drift history re-seeded"}

@app.get("/api/vendors/{name}/drift")
def get_vendor_drift(name: str):
    return {"vendor": name, "alerts": detect_drift(name)}

@app.get("/api/drift")
def get_all_drift():
    return {"alerts": detect_drift()}

@app.post("/api/cases")
async def create_case(
    request: Request,
    response: Response,
    invoice: UploadFile = File(...),
    slip: Optional[UploadFile] = File(None),
    agreement_file: Optional[UploadFile] = File(None),
    agreement_text: Optional[str] = Form(None),
    vendor_email: str = Form("vendor@example.com"),
    vendor_mode: str = Form("realistic"),
    min_accept_percent: float = Form(80.0),
    autonomous: bool = Form(True),
    demo_pacing: bool = Form(True)
):
    client_ip = get_client_ip(request)
    check_rate_limits(client_ip, is_demo=False)

    # 1. Validate invoice image
    inv_bytes = await invoice.read()
    validate_image_file(inv_bytes, invoice.filename)

    # 2. Validate slip image if provided
    slip_bytes = None
    if slip:
        slip_bytes = await slip.read()
        validate_image_file(slip_bytes, slip.filename)

    # 3. Validate agreement image if provided
    agreed_bytes = None
    if agreement_file:
        agreed_bytes = await agreement_file.read()
        validate_image_file(agreed_bytes, agreement_file.filename)

    record_case_created(client_ip)

    case_id = f"case_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # Save validated uploaded files
    inv_path = case_dir / invoice.filename
    inv_path.write_bytes(inv_bytes)

    slip_path = None
    if slip and slip_bytes:
        slip_path = case_dir / slip.filename
        slip_path.write_bytes(slip_bytes)

    agreed_path = None
    if agreement_file and agreed_bytes:
        agreed_path = case_dir / agreement_file.filename
        agreed_path.write_bytes(agreed_bytes)
    elif agreement_text and agreement_text.strip():
        agreed_path = case_dir / "agreement_transcript.txt"
        agreed_path.write_text(agreement_text.strip(), encoding="utf-8")

    # In public mode, never use user-submitted vendor email
    v_email = "simulated-vendor@example.com" if PUBLIC_MODE else (vendor_email or "vendor@example.com")
    session_id = request.cookies.get("bb_session")
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex}"
        response.set_cookie(key="bb_session", value=session_id, httponly=True, samesite="lax", max_age=30 * 24 * 3600, path="/")

    # Insert case in SQLite
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO cases (
        id, invoice_file, slip_file, agreement_file, vendor_email, 
        vendor_mode, min_accept_percent, autonomous, demo_pacing, status, force_cache, session_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_id, str(inv_path), str(slip_path) if slip_path else None, 
        str(agreed_path) if agreed_path else None, v_email,
        vendor_mode, min_accept_percent, 1 if autonomous else 0, 1 if demo_pacing else 0, "created", 0, session_id
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
    demo_pacing = bool(c_row.get("demo_pacing", 1))

    state = {}
    api_calls = []
    force_cache = bool(c_row.get("force_cache", 0))

    def track_call(step_name, data):
        src = data.get("_source") or data.get("source") or "live"
        lat = data.get("_latency") or data.get("latency") or 0.0
        tok = data.get("_tokens") or data.get("tokens") or 0
        call_info = {"step": step_name, "source": src, "latency": lat, "tokens": tok}
        api_calls.append(call_info)
        return call_info

    async def emit(event_type: str, data: dict):
        if demo_pacing:
            await asyncio.sleep(0.4)
        await _publish_event(case_id, event_type, data)

    try:
        # Fault Injection Simulation (Task 4)
        if os.getenv("FAULT_INJECT") == "timeout":
            await emit("tool_start", {"step": 1, "tool": "extract_document", "doc_type": "invoice", "path": inv_path})
            if demo_pacing:
                await asyncio.sleep(0.4)
            raise TimeoutError("Meta AI API call timed out after 60s (simulated FAULT_INJECT=timeout)")

        # Step 1: Extract Invoice
        await emit("tool_start", {"step": 1, "tool": "extract_document", "doc_type": "invoice", "path": inv_path})
        inv_data = extract(inv_path, "invoice", force_cache=force_cache)
        inv_meta = track_call("extract_invoice", inv_data)
        state["invoice"] = inv_data
        record_invoice_items(inv_data)
        await emit("tool_result", {
            "step": 1,
            "tool": "extract_document",
            "doc_type": "invoice",
            "result": inv_data,
            "source": inv_meta["source"],
            "latency": inv_meta["latency"],
            "tokens": inv_meta["tokens"]
        })

        # Extraction Guard Check
        if inv_data.get("uncertain"):
            reasons = inv_data.get("uncertain_reasons") or ["Extraction validation failed"]
            vendor_name = inv_data.get("vendor") or "Unreadable Vendor"
            inv_no = inv_data.get("invoice_no") or "N/A"
            outcome = {
                "claimed": 0.0,
                "recovered": 0.0,
                "rounds": 0,
                "status": "Needs review: Document extraction uncertain. Review or re-upload clearer image.",
                "reasons": reasons,
                "api_stats": {
                    "calls": len(api_calls),
                    "total_tokens": sum(c["tokens"] for c in api_calls),
                    "calls_detail": api_calls
                }
            }
            await emit("extraction_uncertain", {
                "case_id": case_id,
                "reasons": reasons,
                "message": "Couldn't read this bill reliably",
                "extracted_data": inv_data
            })
            await emit("outcome", outcome)
            _update_db_case(case_id, vendor_name, inv_no, "needs_review", 0.0, 0.0, {"findings": [], "total_overcharge": 0.0, "reasons": reasons}, outcome, "")
            return

        # Step 2: Extract Slip if present
        if slip_path:
            await emit("tool_start", {"step": 2, "tool": "extract_document", "doc_type": "slip", "path": slip_path})
            slip_data = extract(slip_path, "slip", force_cache=force_cache)
            slip_meta = track_call("extract_slip", slip_data)
            state["slip"] = slip_data
            await emit("tool_result", {
                "step": 2,
                "tool": "extract_document",
                "doc_type": "slip",
                "result": slip_data,
                "source": slip_meta["source"],
                "latency": slip_meta["latency"],
                "tokens": slip_meta["tokens"]
            })

        # Step 3: Extract Agreement if present
        if agreed_path:
            await emit("tool_start", {"step": 3, "tool": "read_agreement", "path": agreed_path})
            agreed_data = extract_agreement(agreed_path, force_cache=force_cache)
            agr_meta = track_call("read_agreement", agreed_data)
            state["agreement"] = agreed_data
            await emit("tool_result", {
                "step": 3,
                "tool": "read_agreement",
                "result": agreed_data,
                "source": agr_meta["source"],
                "latency": agr_meta["latency"],
                "tokens": agr_meta["tokens"]
            })

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
        await emit("tool_result", {
            "step": 4,
            "tool": "run_audit",
            "result": audit_res,
            "source": "deterministic_python",
            "latency": 0.0,
            "tokens": 0
        })

        # Update case record with initial audit findings
        vendor_name = state["invoice"].get("vendor") or "Unknown Vendor"
        inv_no = state["invoice"].get("invoice_no") or "INV"
        
        if total_claimed <= 0:
            outcome = {
                "claimed": 0.0,
                "recovered": 0.0,
                "rounds": 0,
                "status": "Verified: Bill is correct with zero discrepancies.",
                "api_stats": {
                    "calls": len(api_calls),
                    "total_tokens": sum(c["tokens"] for c in api_calls),
                    "calls_detail": api_calls
                }
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
            approval_event = asyncio.Event()
            CASE_APPROVAL_EVENTS[case_id] = approval_event
            await emit("awaiting_approval", {"case_id": case_id, "email": draft_payload})
            
            # Wait for approval signal
            if case_id not in CASE_APPROVED_SET:
                await approval_event.wait()
            if case_id in CASE_APPROVAL_EVENTS:
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
            v_reply = simulate_vendor_reply(current_body, total_claimed, round_num=r_num, strategy=vendor_mode, force_cache=force_cache)
            offer = float(v_reply.get("offer_amount", 0.0))
            v_meta = track_call(f"vendor_reply_r{r_num}", v_reply)
            
            v_entry = {
                "round": r_num,
                "sender": "Simulated vendor",
                "reply": v_reply["reply_text"],
                "offer": offer,
                "source": v_meta["source"],
                "latency": v_meta["latency"],
                "tokens": v_meta["tokens"]
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
                    "message": f"Settlement accepted: Rs. {offer} meets recovery floor (Rs. {floor_amount}). Case closed.",
                    "source": "deterministic_policy"
                }
                transcript.append(a_entry)
                await emit("agent_reply", a_entry)
                break
            else:
                if r_num < 3:
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
                        "message": counter_text,
                        "source": "deterministic_policy"
                    }
                    transcript.append(a_entry)
                    await emit("agent_reply", a_entry)
                    current_body = counter_text
                else:
                    final_status = f"Vendor offer Rs. {offer}, awaiting your decision"
                    a_entry = {
                        "round": r_num,
                        "sender": "BillBack Agent",
                        "action": "ESCALATE",
                        "message": f"Final offer Rs. {offer} rejected. Escalated to owner, awaiting your decision.",
                        "source": "deterministic_policy"
                    }
                    transcript.append(a_entry)
                    await emit("agent_reply", a_entry)
                    recovered = 0.0 # Do not count unaccepted offer as recovered
                    break

        is_escalated = "awaiting your decision" in final_status.lower() or "escalat" in final_status.lower()
        actual_recovered = 0.0 if is_escalated else recovered
        outcome = {
            "claimed": total_claimed,
            "recovered": actual_recovered,
            "vendor_offer": offer if is_escalated else recovered,
            "floor": floor_amount,
            "rounds": len([t for t in transcript if t.get("sender") == "BillBack Agent"]),
            "status": final_status,
            "escalated": is_escalated,
            "transcript": transcript,
            "api_stats": {
                "calls": len(api_calls),
                "total_tokens": sum(c["tokens"] for c in api_calls),
                "calls_detail": api_calls
            }
        }
        await emit("outcome", outcome)
        db_status = "escalated" if is_escalated else "completed"
        _update_db_case(case_id, vendor_name, inv_no, db_status, total_claimed, actual_recovered, audit_res, outcome, email_body)

    except Exception as e:
        err_msg = str(e)
        await emit("error", {"message": err_msg})
        _update_db_case(case_id, "Unreadable file", "ERR", "error", 0.0, 0.0, None, {"error": err_msg}, "")
    finally:
        for q in list(CASE_SUBSCRIBERS.get(case_id, [])):
            await q.put(None)
        if PUBLIC_MODE:
            case_dir = UPLOAD_DIR / case_id
            if case_dir.exists():
                shutil.rmtree(case_dir, ignore_errors=True)

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
async def stream_case(case_id: str, request: Request):
    if PUBLIC_MODE:
        session_id = request.cookies.get("bb_session") or ""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM cases WHERE id = ?", (case_id,))
        row = cur.fetchone()
        conn.close()
        if not row or (row[0] and row[0] != session_id):
            raise HTTPException(status_code=403, detail="Access denied: Case belongs to another session.")

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
                try:
                    msg = await asyncio.wait_for(sub_q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

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
async def approve_case(case_id: str, request: Request, payload: Optional[ApprovalPayload] = None):
    if PUBLIC_MODE:
        session_id = request.cookies.get("bb_session") or ""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM cases WHERE id = ?", (case_id,))
        row = cur.fetchone()
        conn.close()
        if not row or (row[0] and row[0] != session_id):
            raise HTTPException(status_code=403, detail="Access denied: Case belongs to another session.")

    if payload:
        CASE_EDITED_EMAILS[case_id] = payload
    CASE_APPROVED_SET.add(case_id)
    if case_id in CASE_APPROVAL_EVENTS:
        ev = CASE_APPROVAL_EVENTS[case_id]
        try:
            ev._loop.call_soon_threadsafe(ev.set)
        except Exception:
            ev.set()
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

