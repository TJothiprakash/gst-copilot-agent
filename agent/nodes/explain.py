import json
from agent.state import GSTState
from agent.gemini import call_gemini
from agent.prompts import EXPLAIN_GST_PROMPT


# ── Explain node ──────────────────────────────────────────────────────────────
async def explain_node(state: GSTState) -> GSTState:
    print(f"[explain] Generating explanation for invoice: {state.get('invoice_number')}")

    gst_breakdown = state.get("gst_breakdown", {})
    invoice_type = state.get("invoice_type", "B2B")
    transaction_type = state.get("transaction_type", "intrastate")

    # ── Call Gemini for plain English explanation ──────────────────────────────
    try:
        prompt = EXPLAIN_GST_PROMPT.format(
            gst_breakdown=json.dumps(gst_breakdown, indent=2),
            invoice_type=invoice_type,
            transaction_type=transaction_type,
        )

        explanation = await call_gemini(
            prompt=prompt,
            temperature=0.3,  # slight creativity for friendlier tone
        )

        print(f"[explain] Explanation generated ({len(explanation)} chars)")

    except Exception as e:
        # Non-blocking — explanation failure shouldn't stop the flow
        explanation = (
            f"GST Summary: Taxable value ₹{gst_breakdown.get('total_taxable_value', 0)}, "
            f"Total tax ₹{gst_breakdown.get('total_tax', 0)}, "
            f"Grand total ₹{gst_breakdown.get('grand_total', 0)}"
        )
        print(f"[explain] Fallback explanation used: {str(e)}")

    return {
        **state,
        "explanation": explanation,
        "current_node": "explain",
        "is_complete": True,
    }