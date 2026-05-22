from agent.state import GSTState


# ── Compute GST for a single line item ───────────────────────────────────────
def compute_line_item_gst(
    item: dict,
    transaction_type: str,
) -> dict:
    taxable_value = float(item.get("taxable_value", 0))
    gst_rate = float(item.get("gst_rate", 0))
    total_gst = round(taxable_value * gst_rate / 100, 2)

    if transaction_type == "intrastate":
        # Split equally between CGST and SGST
        cgst = round(total_gst / 2, 2)
        sgst = round(total_gst / 2, 2)
        igst = 0.0
    else:
        # Interstate → only IGST
        cgst = 0.0
        sgst = 0.0
        igst = total_gst

    return {
        **item,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_gst": total_gst,
        "total_amount": round(taxable_value + total_gst, 2),
    }


# ── Compute node ──────────────────────────────────────────────────────────────
async def compute_node(state: GSTState) -> GSTState:
    print(f"[compute] Computing GST for invoice: {state.get('invoice_number')}")

    line_items = state.get("line_items") or []
    transaction_type = state.get("transaction_type", "intrastate")
    invoice_type = state.get("invoice_type", "B2B")

    # ── Compute GST per line item ─────────────────────────────────────────────
    computed_items = []
    for item in line_items:
        computed = compute_line_item_gst(item, transaction_type)
        computed_items.append(computed)

    # ── Aggregate totals ──────────────────────────────────────────────────────
    total_taxable = round(sum(i.get("taxable_value", 0) for i in computed_items), 2)
    total_cgst = round(sum(i.get("cgst", 0) for i in computed_items), 2)
    total_sgst = round(sum(i.get("sgst", 0) for i in computed_items), 2)
    total_igst = round(sum(i.get("igst", 0) for i in computed_items), 2)
    total_tax = round(total_cgst + total_sgst + total_igst, 2)
    grand_total = round(total_taxable + total_tax, 2)

    gst_breakdown = {
        "total_taxable_value": total_taxable,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_igst": total_igst,
        "total_tax": total_tax,
        "grand_total": grand_total,
        "transaction_type": transaction_type,
        "invoice_type": invoice_type,
        "line_items": computed_items,
    }

    print(f"[compute] Grand total: ₹{grand_total} | Tax: ₹{total_tax}")

    return {
        **state,
        "line_items": computed_items,
        "gst_breakdown": gst_breakdown,
        "current_node": "compute",
    }