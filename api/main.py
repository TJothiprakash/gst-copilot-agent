import os
import uuid
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from agent.graph import gst_graph
from agent.state import GSTState
from db.client import save_invoice_result, fetch_invoices, fetch_invoice_by_id

load_dotenv()

# ── Prometheus metrics ────────────────────────────────────────────────────────
INVOICES_PROCESSED = Counter(
    "gst_invoices_processed_total",
    "Total number of invoices processed",
    ["status"]  # success, failed, needs_review
)

INVOICE_PROCESSING_TIME = Histogram(
    "gst_invoice_processing_seconds",
    "Time spent processing invoices",
    buckets=[1, 2, 5, 10, 30, 60, 120]
)

GEMINI_CALLS = Counter(
    "gst_gemini_calls_total",
    "Total Gemini API calls",
    ["node"]  # ingest, classify, validate, etc
)

GST_AMOUNTS = Histogram(
    "gst_invoice_amount_rupees",
    "Invoice grand total amounts in rupees",
    buckets=[1000, 5000, 10000, 50000, 100000, 500000]
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GST Copilot API",
    description="AI-powered GST filing assistant for small businesses",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store ───────────────────────────────────────────────────
sessions: dict = {}


# ── Request/Response models ───────────────────────────────────────────────────
class HumanReviewResponse(BaseModel):
    session_id: str
    confirmed: bool
    correction: str = ""


class SessionResponse(BaseModel):
    session_id: str
    status: str
    current_node: str
    message: str


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gst-copilot"}


# ── Prometheus metrics endpoint ───────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Upload invoice ────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_invoice(file: UploadFile = File(...)):
    # Validate file type
    allowed = [".pdf", ".jpg", ".jpeg", ".png"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        INVOICES_PROCESSED.labels(status="failed").inc()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed}"
        )

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        INVOICES_PROCESSED.labels(status="failed").inc()
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    # Create session
    session_id = str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": session_id}}

    # Build initial state
    initial_state: GSTState = {
        "file_bytes": file_bytes,
        "file_name": file.filename,
        "file_type": None,
        "raw_text": None,
        "gstin": None,
        "invoice_number": None,
        "invoice_date": None,
        "supplier_name": None,
        "buyer_name": None,
        "line_items": [],
        "invoice_type": None,
        "transaction_type": None,
        "errors": [],
        "warnings": [],
        "needs_human_review": False,
        "gst_breakdown": None,
        "gstr_draft": None,
        "explanation": None,
        "human_confirmed": False,
        "human_correction": None,
        "current_node": None,
        "is_complete": False,
    }

    # ── Run graph ─────────────────────────────────────────────────────────────
    start_time = time.time()
    try:
        result = await gst_graph.ainvoke(initial_state, config=thread_config)
    except Exception as e:
        INVOICES_PROCESSED.labels(status="failed").inc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    finally:
        INVOICE_PROCESSING_TIME.observe(time.time() - start_time)

    # Store session for human review resume
    sessions[session_id] = thread_config

    # ── Needs human review ────────────────────────────────────────────────────
    if result.get("needs_human_review"):
        INVOICES_PROCESSED.labels(status="needs_review").inc()
        return {
            "session_id": session_id,
            "status": "needs_review",
            "current_node": result.get("current_node"),
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
            "extracted_data": {
                "gstin": result.get("gstin"),
                "invoice_number": result.get("invoice_number"),
                "invoice_date": result.get("invoice_date"),
                "supplier_name": result.get("supplier_name"),
                "buyer_name": result.get("buyer_name"),
                "line_items": result.get("line_items", []),
                "invoice_type": result.get("invoice_type"),
                "transaction_type": result.get("transaction_type"),
            },
            "message": "Please review the errors and confirm to proceed.",
        }

    # ── Complete ──────────────────────────────────────────────────────────────
    if result.get("is_complete"):
        INVOICES_PROCESSED.labels(status="success").inc()

        # Track invoice amount
        grand_total = result.get("gst_breakdown", {}).get("grand_total", 0)
        if grand_total:
            GST_AMOUNTS.observe(grand_total)

        await save_invoice_result(result)

    return {
        "session_id": session_id,
        "status": "complete",
        "current_node": result.get("current_node"),
        "gst_breakdown": result.get("gst_breakdown"),
        "gstr_draft": result.get("gstr_draft"),
        "explanation": result.get("explanation"),
        "warnings": result.get("warnings", []),
        "message": "Invoice processed successfully.",
    }


# ── Human review confirmation ─────────────────────────────────────────────────
@app.post("/review")
async def human_review(response: HumanReviewResponse):
    session_id = response.session_id
    thread_config = sessions.get(session_id)

    if not thread_config:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Resume graph with human decision
    resume_state = {
        "human_confirmed": response.confirmed,
        "human_correction": response.correction,
        "needs_human_review": False,
    }

    start_time = time.time()
    try:
        result = await gst_graph.ainvoke(resume_state, config=thread_config)
    except Exception as e:
        INVOICES_PROCESSED.labels(status="failed").inc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    finally:
        INVOICE_PROCESSING_TIME.observe(time.time() - start_time)

    if not response.confirmed:
        return {
            "session_id": session_id,
            "status": "cancelled",
            "message": "Processing cancelled by user.",
        }

    # Save to DB
    if result.get("is_complete"):
        INVOICES_PROCESSED.labels(status="success").inc()

        grand_total = result.get("gst_breakdown", {}).get("grand_total", 0)
        if grand_total:
            GST_AMOUNTS.observe(grand_total)

        await save_invoice_result(result)

    return {
        "session_id": session_id,
        "status": "complete",
        "gst_breakdown": result.get("gst_breakdown"),
        "gstr_draft": result.get("gstr_draft"),
        "explanation": result.get("explanation"),
        "message": "Invoice processed and saved successfully.",
    }


# ── Get all invoices ──────────────────────────────────────────────────────────
@app.get("/invoices")
async def get_invoices():
    invoices = await fetch_invoices()
    return {"invoices": invoices, "count": len(invoices)}


# ── Get single invoice ────────────────────────────────────────────────────────
@app.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    invoice = await fetch_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice