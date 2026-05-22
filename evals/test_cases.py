import pytest
import asyncio
from agent.nodes.validate import run_local_validations, is_valid_gstin, is_valid_hsn, is_valid_gst_rate
from agent.nodes.compute import compute_line_item_gst
from agent.parsers import parse_line_items, parse_gst_breakdown
from agent.gemini import extract_json


# ── GSTIN validation tests ────────────────────────────────────────────────────
class TestGSTINValidation:
    def test_valid_gstin(self):
        assert is_valid_gstin("27AAPFU0939F1ZV") == True
        assert is_valid_gstin("33AAPFU0939F1ZV") == True

    def test_invalid_gstin_short(self):
        assert is_valid_gstin("27AAPFU0939F1Z") == False

    def test_invalid_gstin_empty(self):
        assert is_valid_gstin("") == False

    def test_invalid_gstin_none(self):
        assert is_valid_gstin(None) == False

    def test_invalid_gstin_wrong_format(self):
        assert is_valid_gstin("INVALID_GSTIN_123") == False


# ── HSN validation tests ──────────────────────────────────────────────────────
class TestHSNValidation:
    def test_valid_hsn_4_digits(self):
        assert is_valid_hsn("6006") == True

    def test_valid_hsn_8_digits(self):
        assert is_valid_hsn("60063200") == True

    def test_invalid_hsn_too_short(self):
        assert is_valid_hsn("123") == False

    def test_invalid_hsn_letters(self):
        assert is_valid_hsn("600A") == False

    def test_invalid_hsn_empty(self):
        assert is_valid_hsn("") == False


# ── GST rate validation tests ─────────────────────────────────────────────────
class TestGSTRateValidation:
    def test_valid_rates(self):
        for rate in [0, 5, 12, 18, 28]:
            assert is_valid_gst_rate(rate) == True

    def test_invalid_rate(self):
        assert is_valid_gst_rate(10) == False
        assert is_valid_gst_rate(15) == False
        assert is_valid_gst_rate(-1) == False


# ── GST computation tests ─────────────────────────────────────────────────────
class TestGSTComputation:
    def test_intrastate_computation(self):
        item = {
            "description": "Cotton fabric",
            "hsn_code": "5208",
            "quantity": 10,
            "unit_price": 100,
            "taxable_value": 1000,
            "gst_rate": 5,
        }
        result = compute_line_item_gst(item, "intrastate")
        assert result["cgst"] == 25.0
        assert result["sgst"] == 25.0
        assert result["igst"] == 0.0
        assert result["total_gst"] == 50.0
        assert result["total_amount"] == 1050.0

    def test_interstate_computation(self):
        item = {
            "description": "Polyester yarn",
            "hsn_code": "5402",
            "quantity": 5,
            "unit_price": 200,
            "taxable_value": 1000,
            "gst_rate": 12,
        }
        result = compute_line_item_gst(item, "interstate")
        assert result["cgst"] == 0.0
        assert result["sgst"] == 0.0
        assert result["igst"] == 120.0
        assert result["total_gst"] == 120.0
        assert result["total_amount"] == 1120.0

    def test_zero_gst_rate(self):
        item = {
            "description": "Exempted goods",
            "hsn_code": "0101",
            "quantity": 1,
            "unit_price": 500,
            "taxable_value": 500,
            "gst_rate": 0,
        }
        result = compute_line_item_gst(item, "intrastate")
        assert result["total_gst"] == 0.0
        assert result["total_amount"] == 500.0


# ── Parser tests ──────────────────────────────────────────────────────────────
class TestParsers:
    def test_parse_valid_line_items(self):
        raw = [
            {
                "description": "Cotton fabric",
                "hsn_code": "5208",
                "quantity": 10.0,
                "unit_price": 100.0,
                "taxable_value": 1000.0,
                "gst_rate": 5.0,
            }
        ]
        items, errors = parse_line_items(raw)
        assert len(items) == 1
        assert len(errors) == 0
        assert items[0].description == "Cotton fabric"

    def test_parse_invalid_line_items(self):
        raw = [
            {
                "description": "Bad item",
                "quantity": "not_a_number",
                "unit_price": 100,
                "taxable_value": 1000,
                "gst_rate": 5,
            }
        ]
        items, errors = parse_line_items(raw)
        assert len(errors) > 0

    def test_parse_gst_breakdown(self):
        raw = {
            "total_taxable_value": 1000.0,
            "total_cgst": 25.0,
            "total_sgst": 25.0,
            "total_igst": 0.0,
            "total_tax": 50.0,
            "grand_total": 1050.0,
        }
        breakdown, errors = parse_gst_breakdown(raw)
        assert breakdown is not None
        assert len(errors) == 0
        assert breakdown.grand_total == 1050.0


# ── JSON extraction tests ─────────────────────────────────────────────────────
class TestJSONExtraction:
    def test_extract_clean_json(self):
        text = '{"key": "value", "number": 42}'
        result = extract_json(text)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_extract_json_with_markdown(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result["key"] == "value"

    def test_extract_invalid_json(self):
        text = "this is not json"
        with pytest.raises(ValueError):
            extract_json(text)


# ── Local validation integration tests ───────────────────────────────────────
class TestLocalValidations:
    def test_valid_invoice_state(self):
        state = {
            "gstin": "27AAPFU0939F1ZV",
            "invoice_number": "INV-001",
            "invoice_date": "01/05/2026",
            "line_items": [
                {
                    "description": "Cotton fabric",
                    "hsn_code": "5208",
                    "quantity": 10,
                    "unit_price": 100,
                    "taxable_value": 1000,
                    "gst_rate": 5,
                }
            ],
        }
        errors, warnings = run_local_validations(state)
        assert len(errors) == 0

    def test_missing_gstin(self):
        state = {
            "gstin": None,
            "invoice_number": "INV-001",
            "invoice_date": "01/05/2026",
            "line_items": [
                {
                    "description": "Item",
                    "hsn_code": "5208",
                    "quantity": 1,
                    "unit_price": 100,
                    "taxable_value": 100,
                    "gst_rate": 18,
                }
            ],
        }
        errors, warnings = run_local_validations(state)
        assert any("GSTIN" in e for e in errors)

    def test_invalid_gst_rate_in_line_item(self):
        state = {
            "gstin": "27AAPFU0939F1ZV",
            "invoice_number": "INV-001",
            "invoice_date": "01/05/2026",
            "line_items": [
                {
                    "description": "Item",
                    "hsn_code": "5208",
                    "quantity": 1,
                    "unit_price": 100,
                    "taxable_value": 100,
                    "gst_rate": 15,  # invalid
                }
            ],
        }
        errors, warnings = run_local_validations(state)
        assert any("GST rate" in e for e in errors)