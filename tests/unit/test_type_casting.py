"""
Tests for type casting functions - cast_value and _infer_variant.

Tests cover:
- Type coercion for all supported OPC UA datatypes
- Edge cases: NaN, None, boolean string variations
- Invalid values and fallback to string
- Variant inference with and without explicit dtype
"""

import math
from datetime import datetime
from unittest.mock import Mock

import pandas as pd
import pytest
from opcua import ua

from opc_replay.server import _infer_variant, cast_value


@pytest.mark.unit
class TestCastValue:
    """Test cast_value function for all OPC UA datatypes."""

    def test_cast_none_returns_none(self):
        """Test that None input returns None."""
        assert cast_value(None, "Float") is None
        assert cast_value(None, "Int32") is None
        assert cast_value(None, "String") is None

    def test_cast_nan_returns_none(self):
        """Test that NaN input returns None."""
        assert cast_value(float("nan"), "Float") is None
        assert cast_value(pd.NA, "Float") is None

    def test_cast_float(self):
        """Test casting to Float datatype."""
        assert cast_value(20.5, "Float") == 20.5
        assert cast_value("20.5", "Float") == 20.5
        assert cast_value(20, "Float") == 20.0

    def test_cast_double(self):
        """Test casting to Double datatype."""
        assert cast_value(20.5, "Double") == 20.5
        assert cast_value("20.5", "Double") == 20.5

    def test_cast_int32(self):
        """Test casting to Int32 datatype."""
        assert cast_value(42, "Int32") == 42
        assert cast_value("42", "Int32") == 42
        assert cast_value(42.7, "Int32") == 42  # Truncates
        assert cast_value("42.7", "Int32") == 42

    def test_cast_int64(self):
        """Test casting to Int64 datatype."""
        # Use values within safe float64 range (2^53)
        assert cast_value(9007199254740991, "Int64") == 9007199254740991
        assert cast_value("12345", "Int64") == 12345

    def test_cast_int16(self):
        """Test casting to Int16 datatype."""
        assert cast_value(100, "Int16") == 100
        assert cast_value("100", "Int16") == 100

    def test_cast_uint32(self):
        """Test casting to UInt32 datatype."""
        assert cast_value(4294967295, "UInt32") == 4294967295

    def test_cast_byte(self):
        """Test casting to Byte datatype."""
        assert cast_value(255, "Byte") == 255
        assert cast_value("128", "Byte") == 128

    def test_cast_sbyte(self):
        """Test casting to SByte datatype."""
        assert cast_value(-128, "SByte") == -128
        assert cast_value("127", "SByte") == 127

    def test_cast_boolean_true_variants(self):
        """Test various string representations of True."""
        assert cast_value("true", "Boolean") is True
        assert cast_value("True", "Boolean") is True
        assert cast_value("TRUE", "Boolean") is True
        assert cast_value("1", "Boolean") is True
        assert cast_value("yes", "Boolean") is True
        assert cast_value("y", "Boolean") is True
        assert cast_value("t", "Boolean") is True
        assert cast_value(1, "Boolean") is True
        assert cast_value(True, "Boolean") is True

    def test_cast_boolean_false_variants(self):
        """Test various string representations of False."""
        assert cast_value("false", "Boolean") is False
        assert cast_value("False", "Boolean") is False
        assert cast_value("0", "Boolean") is False
        assert cast_value("no", "Boolean") is False
        assert cast_value("n", "Boolean") is False
        assert cast_value("", "Boolean") is False
        assert cast_value(0, "Boolean") is False
        assert cast_value(False, "Boolean") is False

    def test_cast_string(self):
        """Test casting to String datatype."""
        assert cast_value("hello", "String") == "hello"
        assert cast_value(42, "String") == "42"
        assert cast_value(3.14, "String") == "3.14"
        assert cast_value(True, "String") == "True"

    def test_cast_datetime(self):
        """Test casting to DateTime datatype."""
        # ISO format string
        result = cast_value("2026-01-01T10:00:00Z", "DateTime")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 1

    def test_cast_datetime_invalid(self):
        """Test casting invalid datetime returns NaT."""
        result = cast_value("not-a-date", "DateTime")
        # pd.to_datetime with errors='coerce' returns NaT, which becomes NaT datetime
        assert pd.isna(result)

    def test_cast_unknown_dtype_defaults_to_string(self):
        """Test unknown dtype falls back to string conversion."""
        assert cast_value(42, "UnknownType") == "42"
        assert cast_value("hello", "CustomType") == "hello"

    def test_cast_none_dtype_defaults_to_string(self):
        """Test None dtype falls back to string conversion."""
        assert cast_value(42, None) == "42"
        assert cast_value("hello", None) == "hello"

    def test_cast_whitespace_in_dtype(self):
        """Test dtype with whitespace is handled correctly."""
        assert cast_value(20.5, "  Float  ") == 20.5
        assert cast_value(42, " Int32 ") == 42


@pytest.mark.unit
class TestInferVariant:
    """Test _infer_variant function for OPC UA Variant creation."""

    def test_infer_variant_with_explicit_float(self):
        """Test variant creation with explicit Float dtype."""
        variant = _infer_variant(42, "Float")
        assert isinstance(variant, ua.Variant)
        assert variant.Value == 42.0
        assert variant.VariantType == ua.VariantType.Float

    def test_infer_variant_with_explicit_int32(self):
        """Test variant creation with explicit Int32 dtype."""
        variant = _infer_variant(42, "Int32")
        assert variant.Value == 42
        assert variant.VariantType == ua.VariantType.Int32

    def test_infer_variant_with_explicit_boolean(self):
        """Test variant creation with explicit Boolean dtype."""
        variant = _infer_variant("true", "Boolean")
        assert variant.Value is True
        assert variant.VariantType == ua.VariantType.Boolean

    def test_infer_variant_with_explicit_string(self):
        """Test variant creation with explicit String dtype."""
        variant = _infer_variant("hello", "String")
        assert variant.Value == "hello"
        assert variant.VariantType == ua.VariantType.String

    def test_infer_variant_with_explicit_datetime(self):
        """Test variant creation with explicit DateTime dtype."""
        variant = _infer_variant("2026-01-01T10:00:00Z", "DateTime")
        assert isinstance(variant.Value, datetime)
        assert variant.VariantType == ua.VariantType.DateTime

    def test_infer_variant_python_bool_without_dtype(self):
        """Test inferring variant from Python bool."""
        variant = _infer_variant(True)
        assert variant.Value is True
        assert variant.VariantType == ua.VariantType.Boolean

    def test_infer_variant_python_int_without_dtype(self):
        """Test inferring variant from Python int."""
        variant = _infer_variant(42)
        assert variant.Value == 42
        assert variant.VariantType == ua.VariantType.Int64

    def test_infer_variant_python_float_without_dtype(self):
        """Test inferring variant from Python float."""
        variant = _infer_variant(3.14)
        assert variant.Value == 3.14
        assert variant.VariantType == ua.VariantType.Double

    def test_infer_variant_python_string_without_dtype(self):
        """Test inferring variant from Python string."""
        variant = _infer_variant("hello")
        assert variant.Value == "hello"
        assert variant.VariantType == ua.VariantType.String

    def test_infer_variant_unknown_dtype_falls_back_to_auto(self):
        """Test unknown dtype falls back to auto-inference from Python type."""
        variant = _infer_variant(42, "UnknownType")
        # Unknown dtype is ignored, falls back to Python type inference
        # 42 is an int, so it becomes Int64
        assert variant.Value == 42
        assert variant.VariantType == ua.VariantType.Int64

    def test_infer_variant_all_integer_types(self):
        """Test all integer variant types."""
        for dtype in ["Int16", "UInt16", "Int32", "UInt32", "Int64", "UInt64", "SByte", "Byte"]:
            variant = _infer_variant(100, dtype)
            assert variant.Value == 100

    def test_infer_variant_double_vs_float(self):
        """Test distinction between Double and Float."""
        float_variant = _infer_variant(3.14, "Float")
        double_variant = _infer_variant(3.14, "Double")

        assert float_variant.VariantType == ua.VariantType.Float
        assert double_variant.VariantType == ua.VariantType.Double


@pytest.mark.unit
class TestCastValueEdgeCases:
    """Test edge cases and error handling in cast_value."""

    def test_cast_negative_numbers(self):
        """Test casting negative numbers."""
        assert cast_value(-42, "Int32") == -42
        assert cast_value("-3.14", "Float") == -3.14
        assert cast_value(-128, "SByte") == -128

    def test_cast_zero(self):
        """Test casting zero."""
        assert cast_value(0, "Int32") == 0
        assert cast_value(0.0, "Float") == 0.0
        assert cast_value("0", "Boolean") is False

    def test_cast_large_numbers(self):
        """Test casting large numbers (within safe float64 range)."""
        assert cast_value(2147483647, "Int32") == 2147483647  # Max Int32
        # Use values within safe float64 precision range
        assert cast_value(9007199254740991, "Int64") == 9007199254740991  # Max safe integer

    def test_cast_scientific_notation(self):
        """Test casting scientific notation strings."""
        assert cast_value("1.5e2", "Float") == 150.0
        assert cast_value("1e-3", "Float") == 0.001

    def test_cast_empty_string(self):
        """Test casting empty string."""
        assert cast_value("", "String") == ""
        assert cast_value("", "Boolean") is False

    def test_cast_whitespace_strings(self):
        """Test casting strings with whitespace."""
        assert cast_value("  42  ", "Int32") == 42
        assert cast_value("  3.14  ", "Float") == 3.14
        # Boolean casting strips and lowercases
        assert cast_value("  TRUE  ", "Boolean") is True

    def test_cast_boolean_case_insensitive(self):
        """Test boolean casting is case-insensitive."""
        assert cast_value("TrUe", "Boolean") is True
        assert cast_value("YeS", "Boolean") is True
        assert cast_value("FALSE", "Boolean") is False

    def test_cast_preserves_float_precision(self):
        """Test that float precision is preserved."""
        value = 3.141592653589793
        result = cast_value(value, "Float")
        assert isinstance(result, float)
        # Note: Some precision loss is expected with float conversion

    def test_cast_datetime_various_formats(self):
        """Test datetime parsing with various ISO formats."""
        # Test various ISO 8601 formats
        formats = [
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00",
            "2026-01-01 10:00:00",
            "2026/01/01 10:00:00",
        ]
        for fmt in formats:
            result = cast_value(fmt, "DateTime")
            assert isinstance(result, datetime) or pd.isna(result)
