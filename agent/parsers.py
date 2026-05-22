import json
import re
from pydantic import BaseModel, ValidationError
from agent.state import LineItem, GSTBreakdown, GSTRDraft


# ── Strip markdown code fences from LLM response ──────────────────────────────
def clean_llm_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return text.strip()


# ── Parse and validate line items ─────────────────────────────────────────────
def parse_line_items(raw_items: list[dict]) -> tuple[list[LineItem], list[str]]:
    items = []
    errors = []

    for i, item in enumerate(raw_items):
        try:
            line_item = LineItem(
                description=item.get("description", "Unknown"),
                hsn_code=item.get("hsn_code"),
                quantity=float(item.get("quantity", 0)),
                unit_price=float(item.get("unit_price", 0)),
                taxable_value=float(item.get("taxable_value", 0)),
                gst_rate=float(item.get("gst_rate", 0)),
                cgst=float(item.get("cgst", 0)),
                sgst=float(item.get("sgst", 0)),
                igst=float(item.get("igst", 0)),
            )
            items.append(line_item)
        except (ValidationError, ValueError) as e:
            errors.append(f"Line item {i+1} parse error: {str(e)}")

    return items, errors


# ── Parse GST breakdown ───────────────────────────────────────────────────────
def parse_gst_breakdown(raw: dict) -> tuple[GSTBreakdown | None, list[str]]:
    try:
        breakdown = GSTBreakdown(
            total_taxable_value=float(raw.get("total_taxable_value", 0)),
            total_cgst=float(raw.get("total_cgst", 0)),
            total_sgst=float(raw.get("total_sgst", 0)),
            total_igst=float(raw.get("total_igst", 0)),
            total_tax=float(raw.get("total_tax", 0)),
            grand_total=float(raw.get("grand_total", 0)),
        )
        return breakdown, []
    except (ValidationError, ValueError) as e:
        return None, [f"GST breakdown parse error: {str(e)}"]


# ── Parse full GSTR draft ─────────────────────────────────────────────────────
def parse_gstr_draft(raw: dict) -> tuple[GSTRDraft | None, list[str]]:
    try:
        line_items, errors = parse_line_items(raw.get("line_items", []))
        if errors:
            return None, errors

        breakdown_raw = {
            "total_taxable_value": raw.get("taxable_value", 0),
            "total_cgst": raw.get("cgst", 0),
            "total_sgst": raw.get("sgst", 0),
            "total_igst": raw.get("igst", 0),
            "total_tax": raw.get("total_tax", 0),
            "grand_total": raw.get("grand_total", 0),
        }
        breakdown, errors = parse_gst_breakdown(breakdown_raw)
        if errors:
            return None, errors

        draft = GSTRDraft(
            gstin=raw.get("gstin", ""),
            invoice_number=raw.get("invoice_number", ""),
            invoice_date=raw.get("invoice_date", ""),
            invoice_type=raw.get("invoice_type", "B2B"),
            supplier_name=raw.get("supplier_name"),
            buyer_name=raw.get("buyer_name"),
            line_items=line_items,
            gst_breakdown=breakdown,
            filing_period=raw.get("filing_period"),
        )
        return draft, []

    except (ValidationError, ValueError) as e:
        return None, [f"GSTR draft parse error: {str(e)}"]


# ── Safe JSON parse with fallback ─────────────────────────────────────────────
def safe_parse_json(text: str) -> tuple[dict | None, str | None]:
    try:
        cleaned = clean_llm_response(text)
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse failed: {str(e)}"