import streamlit as st
import httpx
import json

API_URL = "http://127.0.0.1:8000"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GST Copilot",
    page_icon="🧾",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧾 GST Copilot")
st.caption("AI-powered GST filing assistant for small businesses")
st.divider()

# ── Session state init ────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "result" not in st.session_state:
    st.session_state.result = None
if "status" not in st.session_state:
    st.session_state.status = None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("About")
    st.info(
        "Upload your invoice (PDF or image) and GST Copilot will:\n\n"
        "✅ Extract all invoice data\n\n"
        "✅ Classify invoice type\n\n"
        "✅ Validate GSTIN & HSN codes\n\n"
        "✅ Compute CGST / SGST / IGST\n\n"
        "✅ Generate GSTR-1 draft\n\n"
        "✅ Explain in plain English"
    )
    st.divider()
    st.caption("Supported formats: PDF, JPG, PNG")
    st.caption("Max file size: 10MB")


# ── File upload section ───────────────────────────────────────────────────────
st.subheader("📤 Upload Invoice")
uploaded_file = st.file_uploader(
    "Choose your invoice file",
    type=["pdf", "jpg", "jpeg", "png"],
    help="Upload a GST invoice in PDF or image format"
)

if uploaded_file and st.button("🚀 Process Invoice", type="primary"):
    with st.spinner("Analyzing invoice with AI..."):
        try:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            response = httpx.post(f"{API_URL}/upload", files=files, timeout=120)
            result = response.json()

            st.session_state.result = result
            st.session_state.status = result.get("status")
            st.session_state.session_id = result.get("session_id")

        except Exception as e:
            st.error(f"Failed to process invoice: {str(e)}")


# ── Show results ──────────────────────────────────────────────────────────────
if st.session_state.result:
    result = st.session_state.result
    status = st.session_state.status

    st.divider()

    # ── Needs human review ────────────────────────────────────────────────────
    if status == "needs_review":
        st.subheader("⚠️ Review Required")
        st.warning("The AI found some issues. Please review before proceeding.")

        # Show errors
        errors = result.get("errors", [])
        if errors:
            st.error("**Errors (must fix):**")
            for e in errors:
                st.write(f"❌ {e}")

        # Show warnings
        warnings = result.get("warnings", [])
        if warnings:
            st.warning("**Warnings (review recommended):**")
            for w in warnings:
                st.write(f"⚠️ {w}")

        # Show extracted data
        extracted = result.get("extracted_data", {})
        if extracted:
            st.subheader("📋 Extracted Invoice Data")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("GSTIN", extracted.get("gstin") or "Not found")
                st.metric("Invoice No.", extracted.get("invoice_number") or "Not found")
                st.metric("Invoice Date", extracted.get("invoice_date") or "Not found")
            with col2:
                st.metric("Supplier", extracted.get("supplier_name") or "Not found")
                st.metric("Buyer", extracted.get("buyer_name") or "Not found")
                st.metric("Type", extracted.get("invoice_type") or "Not classified")

            line_items = extracted.get("line_items", [])
            if line_items:
                st.subheader("📦 Line Items")
                st.dataframe(line_items, use_container_width=True)

        # Human correction input
        correction = st.text_area(
            "Add corrections or notes (optional)",
            placeholder="e.g. GSTIN is correct, HSN code for item 2 is 6006"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm & Proceed", type="primary"):
                with st.spinner("Processing..."):
                    try:
                        review_response = httpx.post(
                            f"{API_URL}/review",
                            json={
                                "session_id": st.session_state.session_id,
                                "confirmed": True,
                                "correction": correction,
                            },
                            timeout=120,
                        )
                        new_result = review_response.json()
                        st.session_state.result = new_result
                        st.session_state.status = new_result.get("status")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        with col2:
            if st.button("❌ Cancel", type="secondary"):
                st.session_state.result = None
                st.session_state.status = None
                st.session_state.session_id = None
                st.rerun()

    # ── Complete ──────────────────────────────────────────────────────────────
    elif status == "complete":
        st.success("✅ Invoice processed successfully!")

        # Explanation
        explanation = result.get("explanation")
        if explanation:
            st.subheader("💬 Plain English Summary")
            st.info(explanation)

        # GST Breakdown
        gst_breakdown = result.get("gst_breakdown", {})
        if gst_breakdown:
            st.subheader("🧮 GST Breakdown")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Taxable Value", f"₹{gst_breakdown.get('total_taxable_value', 0):,.2f}")
            with col2:
                st.metric("CGST", f"₹{gst_breakdown.get('total_cgst', 0):,.2f}")
            with col3:
                st.metric("SGST", f"₹{gst_breakdown.get('total_sgst', 0):,.2f}")
            with col4:
                st.metric("IGST", f"₹{gst_breakdown.get('total_igst', 0):,.2f}")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Tax", f"₹{gst_breakdown.get('total_tax', 0):,.2f}")
            with col2:
                st.metric("Grand Total", f"₹{gst_breakdown.get('grand_total', 0):,.2f}")

        # GSTR Draft
        gstr_draft = result.get("gstr_draft", {})
        if gstr_draft:
            st.subheader("📄 GSTR-1 Draft")
            st.json(gstr_draft)

            # Download button
            st.download_button(
                label="⬇️ Download GSTR Draft (JSON)",
                data=json.dumps(gstr_draft, indent=2),
                file_name=f"GSTR1_{gstr_draft.get('invoice_number', 'draft')}.json",
                mime="application/json",
            )

        # Warnings
        warnings = result.get("warnings", [])
        if warnings:
            st.subheader("⚠️ Warnings")
            for w in warnings:
                st.warning(w)

        # Reset button
        if st.button("🔄 Process Another Invoice"):
            st.session_state.result = None
            st.session_state.status = None
            st.session_state.session_id = None
            st.rerun()

    # ── Cancelled ─────────────────────────────────────────────────────────────
    elif status == "cancelled":
        st.warning("Processing was cancelled.")
        if st.button("🔄 Start Over"):
            st.session_state.result = None
            st.session_state.status = None
            st.session_state.session_id = None
            st.rerun()