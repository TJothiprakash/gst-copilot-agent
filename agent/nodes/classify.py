import json
from agent.state import GSTState
from agent.gemini import call_gemini, extract_json
from agent.prompts import CLASSIFY_INVOICE_PROMPT


# ── Classify node ─────────────────────────────────────────────────────────────
async def classify_node(state: GSTState) -> GSTState:
    print(f"[classify] Classifying invoice: {state.get('invoice_number')}")

    # ── Build invoice summary for prompt ──────────────────────────────────────
    invoice_data = {
        "gstin": state.get("gstin"),
        "invoice_number": state.get("invoice_number"),
        "invoice_date": state.get("invoice_date"),
        "supplier_name": state.get("supplier_name"),
        "buyer_name": state.get("buyer_name"),
        "line_items": state.get("line_items", []),
    }

    prompt = CLASSIFY_INVOICE_PROMPT.format(
        invoice_data=json.dumps(invoice_data, indent=2)
    )

    # ── Call Gemini ───────────────────────────────────────────────────────────
    try:
        raw_response = await call_gemini(
            prompt=prompt,
            temperature=0.0,
        )
        result = extract_json(raw_response)
        print(f"[classify] Type: {result.get('invoice_type')} | Transaction: {result.get('transaction_type')}")

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Classification failed: {str(e)}"],
            "needs_human_review": True,
            "current_node": "classify",
        }

    # ── Validate classification result ────────────────────────────────────────
    invoice_type = result.get("invoice_type")
    transaction_type = result.get("transaction_type")

    valid_invoice_types = ["B2B", "B2C", "export", "RCM"]
    valid_transaction_types = ["intrastate", "interstate"]

    errors = list(state.get("errors", []))

    if invoice_type not in valid_invoice_types:
        errors.append(f"Invalid invoice type returned: {invoice_type}")
        invoice_type = None

    if transaction_type not in valid_transaction_types:
        errors.append(f"Invalid transaction type returned: {transaction_type}")
        transaction_type = None

    needs_review = len(errors) > 0

    # ── Update state ──────────────────────────────────────────────────────────
    return {
        **state,
        "invoice_type": invoice_type,
        "transaction_type": transaction_type,
        "errors": errors,
        "needs_human_review": needs_review,
        "current_node": "classify",
    }