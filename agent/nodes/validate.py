import re
import json
from agent.state import GSTState
from agent.gemini import call_gemini, extract_json
from agent.prompts import VALIDATE_INVOICE_PROMPT


# ── GSTIN format validator ────────────────────────────────────────────────────
def is_valid_gstin(gstin: str) -> bool:
    if not gstin:
        return False
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    return bool(re.match(pattern, gstin.upper()))


# ── HSN code validator ────────────────────────────────────────────────────────
def is_valid_hsn(hsn: str) -> bool:
    if not hsn:
        return False
    return bool(re.match(r"^\d{4,8}$", str(hsn)))


# ── GST rate validator ────────────────────────────────────────────────────────
def is_valid_gst_rate(rate: float) -> bool:
    return rate in [0, 5, 12, 18, 28]


# ── Local validations (no LLM needed) ────────────────────────────────────────
def run_local_validations(state: GSTState) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []

    # GSTIN check
    gstin = state.get("gstin")
    if not gstin:
        errors.append("Supplier GSTIN is missing")
    elif not is_valid_gstin(gstin):
        errors.append(f"Invalid GSTIN format: {gstin}")

    # Invoice number check
    if not state.get("invoice_number"):
        errors.append("Invoice number is missing")

    # Invoice date check
    if not state.get("invoice_date"):
        errors.append("Invoice date is missing")

    # Line items check
    line_items = state.get("line_items") or []
    if not line_items:
        errors.append("No line items found in invoice")

    for i, item in enumerate(line_items):
        # HSN code
        hsn = item.get("hsn_code")
        if not hsn:
            warnings.append(f"Line item {i+1} ({item.get('description', 'unknown')}): HSN code missing")
        elif not is_valid_hsn(str(hsn)):
            warnings.append(f"Line item {i+1}: Invalid HSN code: {hsn}")

        # GST rate
        rate = item.get("gst_rate", -1)
        if not is_valid_gst_rate(rate):
            errors.append(f"Line item {i+1}: Invalid GST rate: {rate}%. Must be 0, 5, 12, 18, or 28")

        # Amount check
        qty = item.get("quantity", 0)
        unit_price = item.get("unit_price", 0)
        taxable = item.get("taxable_value", 0)
        expected = round(qty * unit_price, 2)
        if taxable and abs(expected - taxable) > 1.0:
            warnings.append(
                f"Line item {i+1}: Taxable value mismatch. "
                f"Expected {expected}, got {taxable}"
            )

    return errors, warnings


# ── Validate node ─────────────────────────────────────────────────────────────
async def validate_node(state: GSTState) -> GSTState:
    print(f"[validate] Validating invoice: {state.get('invoice_number')}")

    # ── Run local rule-based validations first ────────────────────────────────
    local_errors, local_warnings = run_local_validations(state)
    print(f"[validate] Local check: {len(local_errors)} errors, {len(local_warnings)} warnings")

    # ── Run LLM validation for deeper checks ──────────────────────────────────
    invoice_data = {
        "gstin": state.get("gstin"),
        "invoice_number": state.get("invoice_number"),
        "invoice_date": state.get("invoice_date"),
        "invoice_type": state.get("invoice_type"),
        "transaction_type": state.get("transaction_type"),
        "line_items": state.get("line_items", []),
    }

    try:
        prompt = VALIDATE_INVOICE_PROMPT.format(
            invoice_data=json.dumps(invoice_data, indent=2)
        )
        raw_response = await call_gemini(prompt=prompt, temperature=0.0)
        llm_result = extract_json(raw_response)

        llm_errors = llm_result.get("errors", [])
        llm_warnings = llm_result.get("warnings", [])

    except Exception as e:
        llm_errors = []
        llm_warnings = [f"LLM validation skipped: {str(e)}"]

    # ── Merge all errors and warnings ─────────────────────────────────────────
    all_errors = local_errors + llm_errors
    all_warnings = local_warnings + llm_warnings

    # deduplicate
    all_errors = list(dict.fromkeys(all_errors))
    all_warnings = list(dict.fromkeys(all_warnings))

    needs_review = len(all_errors) > 0
    print(f"[validate] Final: {len(all_errors)} errors, {len(all_warnings)} warnings")

    return {
        **state,
        "errors": all_errors,
        "warnings": all_warnings,
        "needs_human_review": needs_review,
        "current_node": "validate",
    }