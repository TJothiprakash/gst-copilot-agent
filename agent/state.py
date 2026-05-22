from typing import TypedDict, Optional, Literal
from pydantic import BaseModel


# ── Line item inside an invoice ───────────────────────────────────────────────
class LineItem(BaseModel):
    description: str
    hsn_code: Optional[str] = None
    quantity: float
    unit_price: float
    taxable_value: float
    gst_rate: float  # e.g. 5.0, 12.0, 18.0, 28.0
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0


# ── GST breakdown summary ─────────────────────────────────────────────────────
class GSTBreakdown(BaseModel):
    total_taxable_value: float
    total_cgst: float
    total_sgst: float
    total_igst: float
    total_tax: float
    grand_total: float


# ── GSTR draft ────────────────────────────────────────────────────────────────
class GSTRDraft(BaseModel):
    gstin: str
    invoice_number: str
    invoice_date: str
    invoice_type: str
    supplier_name: Optional[str] = None
    buyer_name: Optional[str] = None
    line_items: list[LineItem]
    gst_breakdown: GSTBreakdown
    filing_period: Optional[str] = None  # e.g. "April 2025"


# ── Main LangGraph state ──────────────────────────────────────────────────────
class GSTState(TypedDict):
    # Input
    file_bytes: Optional[bytes]
    file_name: Optional[str]
    file_type: Optional[str]          # "pdf" or "image"

    # Extracted
    raw_text: Optional[str]
    gstin: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    supplier_name: Optional[str]
    buyer_name: Optional[str]
    line_items: Optional[list[dict]]

    # Classification
    invoice_type: Optional[Literal["B2B", "B2C", "export", "RCM"]]
    transaction_type: Optional[Literal["intrastate", "interstate"]]

    # Validation
    errors: list[str]
    warnings: list[str]
    needs_human_review: bool

    # Computation
    gst_breakdown: Optional[dict]

    # Generation
    gstr_draft: Optional[dict]
    explanation: Optional[str]

    # Human in the loop
    human_confirmed: bool
    human_correction: Optional[str]

    # Metadata
    current_node: Optional[str]
    is_complete: bool