import os
from pathlib import Path
from agent.state import GSTState
from agent.gemini import call_gemini_with_file, extract_json
from agent.prompts import EXTRACT_INVOICE_PROMPT


# ── Supported file types ──────────────────────────────────────────────────────
SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def get_mime_type(file_name: str) -> str:
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {list(SUPPORTED_TYPES.keys())}")
    return SUPPORTED_TYPES[ext]


# ── Ingest node ───────────────────────────────────────────────────────────────
async def ingest_node(state: GSTState) -> GSTState:
    print(f"[ingest] Processing file: {state.get('file_name')}")

    file_bytes = state.get("file_bytes")
    file_name = state.get("file_name", "invoice.pdf")

    # ── Validate file exists ──────────────────────────────────────────────────
    if not file_bytes:
        return {
            **state,
            "errors": ["No file provided. Please upload an invoice."],
            "needs_human_review": True,
            "current_node": "ingest",
            "is_complete": False,
        }

    # ── Detect mime type ──────────────────────────────────────────────────────
    try:
        mime_type = get_mime_type(file_name)
        file_type = "pdf" if mime_type == "application/pdf" else "image"
    except ValueError as e:
        return {
            **state,
            "errors": [str(e)],
            "needs_human_review": True,
            "current_node": "ingest",
            "is_complete": False,
        }

    # ── Call Gemini with file ─────────────────────────────────────────────────
    try:
        print(f"[ingest] Sending to Gemini ({mime_type})...")
        raw_response = await call_gemini_with_file(
            prompt=EXTRACT_INVOICE_PROMPT,
            file_bytes=file_bytes,
            mime_type=mime_type,
            temperature=0.0,
        )

        extracted = extract_json(raw_response)
        print(f"[ingest] Extracted {len(extracted.get('line_items', []))} line items")

    except Exception as e:
        return {
            **state,
            "errors": [f"Failed to extract invoice data: {str(e)}"],
            "needs_human_review": True,
            "current_node": "ingest",
            "is_complete": False,
        }

    # ── Update state ──────────────────────────────────────────────────────────
    return {
        **state,
        "file_type": file_type,
        "raw_text": str(extracted),
        "gstin": extracted.get("gstin"),
        "invoice_number": extracted.get("invoice_number"),
        "invoice_date": extracted.get("invoice_date"),
        "supplier_name": extracted.get("supplier_name"),
        "buyer_name": extracted.get("buyer_name"),
        "line_items": extracted.get("line_items", []),
        "errors": [],
        "warnings": [],
        "needs_human_review": False,
        "current_node": "ingest",
        "is_complete": False,
    }