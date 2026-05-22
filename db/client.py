import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


# ── Supabase client singleton ─────────────────────────────────────────────────
def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("Supabase credentials missing in .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


supabase: Client = get_supabase_client()


# ── Save invoice result to DB ─────────────────────────────────────────────────
async def save_invoice_result(state: dict) -> dict:
    data = {
        "gstin": state.get("gstin"),
        "invoice_number": state.get("invoice_number"),
        "invoice_date": state.get("invoice_date"),
        "invoice_type": state.get("invoice_type"),
        "transaction_type": state.get("transaction_type"),
        "supplier_name": state.get("supplier_name"),
        "buyer_name": state.get("buyer_name"),
        "gst_breakdown": state.get("gst_breakdown"),
        "gstr_draft": state.get("gstr_draft"),
        "explanation": state.get("explanation"),
        "errors": state.get("errors", []),
        "warnings": state.get("warnings", []),
    }

    response = supabase.table("invoices").insert(data).execute()
    return response.data[0] if response.data else {}


# ── Fetch all invoices ────────────────────────────────────────────────────────
async def fetch_invoices(limit: int = 50) -> list:
    response = (
        supabase.table("invoices")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


# ── Fetch single invoice ──────────────────────────────────────────────────────
async def fetch_invoice_by_id(invoice_id: str) -> dict:
    response = (
        supabase.table("invoices")
        .select("*")
        .eq("id", invoice_id)
        .single()
        .execute()
    )
    return response.data or {}