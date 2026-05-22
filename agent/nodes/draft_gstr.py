import json
from datetime import datetime
from agent.state import GSTState
from agent.gemini import call_gemini, extract_json
from agent.prompts import DRAFT_GSTR_PROMPT


# ── Get current filing period ─────────────────────────────────────────────────
def get_filing_period() -> str:
    now = datetime.now()
    return now.strftime("%B %Y")  # e.g. "May 2026"


# ── Draft GSTR node ───────────────────────────────────────────────────────────
async def draft_gstr_node(state: GSTState) -> GSTState:
    print(f"[draft_gstr] Drafting GSTR for invoice: {state.get('invoice_number')}")

    invoice_data = {
        "gstin": state.get("gstin"),
        "invoice_number": state.get("invoice_number"),
        "invoice_date": state.get("invoice_date"),
        "invoice_type": state.get("invoice_type"),
        "transaction_type": state.get("transaction_type"),
        "supplier_name": state.get("supplier_name"),
        "buyer_name": state.get("buyer_name"),
        "line_items": state.get("line_items", []),
    }

    gst_breakdown = state.get("gst_breakdown", {})

    # ── Call Gemini to draft GSTR ─────────────────────────────────────────────
    try:
        prompt = DRAFT_GSTR_PROMPT.format(
            invoice_data=json.dumps(invoice_data, indent=2),
            gst_breakdown=json.dumps(gst_breakdown, indent=2),
        )

        raw_response = await call_gemini(prompt=prompt, temperature=0.0)
        gstr_draft = extract_json(raw_response)

        # ── Enrich with computed values to ensure accuracy ────────────────────
        gstr_draft["cgst"] = gst_breakdown.get("total_cgst", 0)
        gstr_draft["sgst"] = gst_breakdown.get("total_sgst", 0)
        gstr_draft["igst"] = gst_breakdown.get("total_igst", 0)
        gstr_draft["total_tax"] = gst_breakdown.get("total_tax", 0)
        gstr_draft["grand_total"] = gst_breakdown.get("grand_total", 0)
        gstr_draft["taxable_value"] = gst_breakdown.get("total_taxable_value", 0)
        gstr_draft["filing_period"] = get_filing_period()
        gstr_draft["gstr_type"] = "GSTR-1"

        print(f"[draft_gstr] GSTR draft ready for period: {gstr_draft['filing_period']}")

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"GSTR draft failed: {str(e)}"],
            "needs_human_review": True,
            "current_node": "draft_gstr",
        }

    return {
        **state,
        "gstr_draft": gstr_draft,
        "current_node": "draft_gstr",
    }