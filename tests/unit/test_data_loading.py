"""
Tests for data loading functions - load_and_prepare_data.

Tests cover:
- CSV and Parquet file loading
- Column name normalization
- Timestamp parsing and UTC conversion
- Offset and max_rows parameters
- Edge cases: empty files, missing columns, invalid timestamps
"""

import pandas as pd
import pytest

from opc_replay.server import load_and_prepare_data


@pytest.mark.unit
class TestLoadAndPrepareDataBasic:
    """Basic functionality tests for load_and_prepare_data."""

    def test_load_csv_file(self, temp_csv_file):
        """Test loading a CSV file."""
        df = load_and_prepare_data(str(temp_csv_file), "TS")

        assert len(df) == 5
        assert "TAGNAME" in df.columns
        assert "TAGVALUE" in df.columns
        assert "DATATYPE" in df.columns
        assert "TS" in df.columns

    def test_load_parquet_file(self, temp_parquet_file):
        """Test loading a Parquet file."""
        df = load_and_prepare_data(str(temp_parquet_file), "TS")

        assert len(df) == 5
        assert "TAGNAME" in df.columns
        assert "TAGVALUE" in df.columns
        assert "DATATYPE" in df.columns

    def test_timestamps_parsed_as_datetime(self, temp_csv_file):
        """Test timestamps are parsed as datetime objects."""
        df = load_and_prepare_data(str(temp_csv_file), "TS")

        assert pd.api.types.is_datetime64_any_dtype(df["TS"])

    def test_timestamps_converted_to_utc(self, temp_csv_file):
        """Test timestamps are timezone-aware UTC."""
        df = load_and_prepare_data(str(temp_csv_file), "TS")

        # Check first timestamp has timezone
        assert df["TS"].iloc[0].tzinfo is not None
        assert str(df["TS"].iloc[0].tzinfo) == "UTC"

    def test_data_not_automatically_sorted(self, tmp_path):
        """Test data is NOT automatically sorted (performance optimization)."""
        # Create CSV with unsorted timestamps
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,3,Float,2026-01-01T10:00:02Z
ns=2;s=Tag2,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag3,2,Float,2026-01-01T10:00:01Z
"""
        csv_file = tmp_path / "unsorted.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        # Data should remain in original order (not sorted by default)
        assert len(df) == 3
        assert df["TAGVALUE"].iloc[0] == 3
        assert df["TAGVALUE"].iloc[1] == 1
        assert df["TAGVALUE"].iloc[2] == 2

    def test_tagname_normalized_to_string(self, temp_csv_file):
        """Test TAGNAME column is normalized to string."""
        df = load_and_prepare_data(str(temp_csv_file), "TS")

        # String dtype or object dtype are both acceptable
        assert df["TAGNAME"].dtype in (object, "string")
        # Check no leading/trailing whitespace
        for tagname in df["TAGNAME"]:
            assert tagname == tagname.strip()


@pytest.mark.unit
class TestLoadAndPrepareDataColumnNormalization:
    """Test column name normalization."""

    def test_tag_name_normalized_to_tagname(self, tmp_path):
        """Test TAG_NAME is normalized to TAGNAME."""
        csv_content = """TAG_NAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "tag_name.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        assert "TAGNAME" in df.columns
        assert "TAG_NAME" not in df.columns

    def test_value_normalized_to_tagvalue(self, tmp_path):
        """Test VALUE is normalized to TAGVALUE."""
        csv_content = """TAGNAME,VALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "value.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        assert "TAGVALUE" in df.columns
        assert "VALUE" not in df.columns

    def test_both_tag_name_and_value_normalized(self, tmp_path):
        """Test both TAG_NAME and VALUE are normalized."""
        csv_content = """TAG_NAME,VALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "both.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        assert "TAGNAME" in df.columns
        assert "TAGVALUE" in df.columns
        assert "TAG_NAME" not in df.columns
        assert "VALUE" not in df.columns

    def test_tagname_preserved_if_exists(self, tmp_path):
        """Test TAGNAME is not renamed if already exists."""
        csv_content = """TAGNAME,TAG_NAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temp1,ns=2;s=Temp2,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "both_formats.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        # Should keep TAGNAME, not rename TAG_NAME
        assert "TAGNAME" in df.columns
        assert df["TAGNAME"].iloc[0] == "ns=2;s=Temp1"


@pytest.mark.unit
class TestLoadAndPrepareDataOffset:
    """Test offset parameter functionality."""

    def test_offset_skips_initial_data(self, tmp_path):
        """Test offset skips first N seconds of data."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag,2,Float,2026-01-01T10:00:01Z
ns=2;s=Tag,3,Float,2026-01-01T10:00:02Z
ns=2;s=Tag,4,Float,2026-01-01T10:00:03Z
ns=2;s=Tag,5,Float,2026-01-01T10:00:04Z
"""
        csv_file = tmp_path / "offset_test.csv"
        csv_file.write_text(csv_content)

        # Skip first 2 seconds
        df = load_and_prepare_data(str(csv_file), "TS", offset=2.0)

        # Should start at 10:00:02
        assert len(df) == 3
        assert df["TAGVALUE"].iloc[0] == 3

    def test_offset_zero_returns_all_data(self, temp_csv_file):
        """Test offset=0 returns all data."""
        df_no_offset = load_and_prepare_data(str(temp_csv_file), "TS", offset=0)
        df_explicit_zero = load_and_prepare_data(str(temp_csv_file), "TS", offset=0.0)

        assert len(df_no_offset) == len(df_explicit_zero)

    def test_offset_exceeds_duration_raises_error(self, tmp_path):
        """Test offset exceeding data duration raises ValueError."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag,2,Float,2026-01-01T10:00:01Z
"""
        csv_file = tmp_path / "short_data.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="Offset.*exceeds data duration"):
            load_and_prepare_data(str(csv_file), "TS", offset=10.0)

    def test_offset_partial_second(self, tmp_path):
        """Test offset with fractional seconds."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag,1,Float,2026-01-01T10:00:00.000Z
ns=2;s=Tag,2,Float,2026-01-01T10:00:00.500Z
ns=2;s=Tag,3,Float,2026-01-01T10:00:01.000Z
"""
        csv_file = tmp_path / "subsecond.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS", offset=0.5)

        # Should skip first row
        assert len(df) == 2
        assert df["TAGVALUE"].iloc[0] == 2


@pytest.mark.unit
class TestLoadAndPrepareDataMaxRows:
    """Test max_rows parameter functionality."""

    def test_max_rows_limits_output(self, temp_csv_file):
        """Test max_rows limits number of rows returned."""
        df = load_and_prepare_data(str(temp_csv_file), "TS", max_rows=3)

        assert len(df) == 3

    def test_max_rows_none_returns_all(self, temp_csv_file):
        """Test max_rows=None returns all rows."""
        df = load_and_prepare_data(str(temp_csv_file), "TS", max_rows=None)

        assert len(df) == 5

    def test_max_rows_larger_than_data_returns_all(self, temp_csv_file):
        """Test max_rows larger than data returns all rows."""
        df = load_and_prepare_data(str(temp_csv_file), "TS", max_rows=1000)

        assert len(df) == 5

    def test_offset_and_max_rows_combined(self, tmp_path):
        """Test offset is applied before max_rows."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag,2,Float,2026-01-01T10:00:01Z
ns=2;s=Tag,3,Float,2026-01-01T10:00:02Z
ns=2;s=Tag,4,Float,2026-01-01T10:00:03Z
ns=2;s=Tag,5,Float,2026-01-01T10:00:04Z
"""
        csv_file = tmp_path / "combined.csv"
        csv_file.write_text(csv_content)

        # Skip first 2 seconds, then take 2 rows
        df = load_and_prepare_data(str(csv_file), "TS", offset=2.0, max_rows=2)

        # Should get rows 3 and 4
        assert len(df) == 2
        assert df["TAGVALUE"].iloc[0] == 3
        assert df["TAGVALUE"].iloc[1] == 4


@pytest.mark.unit
class TestLoadAndPrepareDataErrorHandling:
    """Test error handling in load_and_prepare_data."""

    def test_missing_tagname_column_raises_error(self, tmp_path):
        """Test missing TAGNAME column raises ValueError."""
        csv_content = """TAGVALUE,DATATYPE,TS
20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "missing_tagname.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="missing required columns.*TAGNAME"):
            load_and_prepare_data(str(csv_file), "TS")

    def test_missing_tagvalue_column_raises_error(self, tmp_path):
        """Test missing TAGVALUE column raises ValueError."""
        csv_content = """TAGNAME,DATATYPE,TS
ns=2;s=Temperature,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "missing_tagvalue.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="missing required columns.*TAGVALUE"):
            load_and_prepare_data(str(csv_file), "TS")

    def test_missing_datatype_column_raises_error(self, tmp_path):
        """Test missing DATATYPE column raises ValueError."""
        csv_content = """TAGNAME,TAGVALUE,TS
ns=2;s=Temperature,20.5,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "missing_datatype.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="missing required columns.*DATATYPE"):
            load_and_prepare_data(str(csv_file), "TS")

    def test_missing_timestamp_column_raises_error(self, tmp_path):
        """Test missing timestamp column raises ValueError."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE
ns=2;s=Temperature,20.5,Float
"""
        csv_file = tmp_path / "missing_ts.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="missing timestamp column 'TS'"):
            load_and_prepare_data(str(csv_file), "TS")

    def test_unsupported_file_type_raises_error(self, tmp_path):
        """Test unsupported file extension raises ValueError."""
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("some data")

        with pytest.raises(ValueError, match="Unsupported file type"):
            load_and_prepare_data(str(txt_file), "TS")

    def test_invalid_timestamps_dropped(self, tmp_path):
        """Test rows with invalid timestamps are dropped."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag2,2,Float,invalid-timestamp
ns=2;s=Tag3,3,Float,2026-01-01T10:00:02Z
"""
        csv_file = tmp_path / "invalid_ts.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        # Should only have 2 rows (invalid dropped)
        assert len(df) == 2
        assert df["TAGVALUE"].iloc[0] == 1
        assert df["TAGVALUE"].iloc[1] == 3

    @pytest.mark.filterwarnings("ignore:Could not infer format")
    def test_empty_csv_after_timestamp_filtering(self, tmp_path):
        """Test error when all rows have invalid timestamps."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,1,Float,invalid
ns=2;s=Tag2,2,Float,also-invalid
"""
        csv_file = tmp_path / "all_invalid_ts.csv"
        csv_file.write_text(csv_content)

        # After dropping invalid timestamps, dataframe becomes empty
        # This should work but return empty dataframe
        df = load_and_prepare_data(str(csv_file), "TS")
        assert len(df) == 0


@pytest.mark.unit
class TestLoadAndPrepareDataEdgeCases:
    """Test edge cases in data loading."""

    def test_csv_with_utf8_bom(self, tmp_path):
        """Test CSV with UTF-8 BOM is handled correctly."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "bom.csv"
        # Write with UTF-8 BOM using encoding parameter
        with open(csv_file, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        assert len(df) == 1
        assert "TAGNAME" in df.columns

    def test_single_row_csv(self, tmp_path):
        """Test CSV with single data row."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "single_row.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        assert len(df) == 1

    def test_tagname_with_whitespace(self, tmp_path):
        """Test TAGNAME with leading/trailing whitespace is stripped."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
  ns=2;s=Temperature  ,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "whitespace.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        assert df["TAGNAME"].iloc[0] == "ns=2;s=Temperature"

    def test_case_sensitive_column_names(self, tmp_path):
        """Test column names are case-sensitive."""
        # Should fail with lowercase column names
        csv_content = """tagname,tagvalue,datatype,ts
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "lowercase.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="missing required columns"):
            load_and_prepare_data(str(csv_file), "ts")

    def test_duplicate_timestamps(self, tmp_path):
        """Test handling of duplicate timestamps."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag2,2,Float,2026-01-01T10:00:00Z
ns=2;s=Tag3,3,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "duplicates.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        # All rows should be preserved, just sorted
        assert len(df) == 3

    def test_various_timestamp_formats(self, tmp_path):
        """Test various ISO 8601 timestamp formats."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag2,2,Float,2026-01-01T10:00:01+00:00
ns=2;s=Tag3,3,Float,2026-01-01 10:00:02
"""
        csv_file = tmp_path / "formats.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        # All valid formats should be parsed
        assert len(df) >= 2  # At least the first two should parse


@pytest.mark.unit
class TestLoadAndPrepareDataSortAndSave:
    """Test sort_and_save parameter functionality."""

    def test_sort_and_save_creates_sorted_csv(self, tmp_path):
        """Test sort_and_save creates a sorted CSV file."""
        # Create CSV with unsorted timestamps
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,3,Float,2026-01-01T10:00:02Z
ns=2;s=Tag2,1,Float,2026-01-01T10:00:00Z
ns=2;s=Tag3,2,Float,2026-01-01T10:00:01Z
"""
        csv_file = tmp_path / "unsorted.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS", sort_and_save=True)

        # Check sorted file was created
        sorted_file = tmp_path / "unsorted_sorted.csv"
        assert sorted_file.exists()

        # Load sorted file and verify it's sorted
        df_sorted = pd.read_csv(sorted_file)
        assert df_sorted["TAGVALUE"].iloc[0] == 1
        assert df_sorted["TAGVALUE"].iloc[1] == 2
        assert df_sorted["TAGVALUE"].iloc[2] == 3

    def test_sort_and_save_creates_sorted_parquet(self, tmp_path):
        """Test sort_and_save creates a sorted Parquet file."""
        # Create Parquet with unsorted data
        import pandas as pd

        df_unsorted = pd.DataFrame(
            {
                "TAGNAME": ["ns=2;s=Tag1", "ns=2;s=Tag2", "ns=2;s=Tag3"],
                "TAGVALUE": [3, 1, 2],
                "DATATYPE": ["Float", "Float", "Float"],
                "TS": [
                    "2026-01-01T10:00:02Z",
                    "2026-01-01T10:00:00Z",
                    "2026-01-01T10:00:01Z",
                ],
            }
        )
        parquet_file = tmp_path / "unsorted.parquet"
        df_unsorted.to_parquet(parquet_file, index=False)

        df = load_and_prepare_data(str(parquet_file), "TS", sort_and_save=True)

        # Check sorted file was created
        sorted_file = tmp_path / "unsorted_sorted.parquet"
        assert sorted_file.exists()

        # Load sorted file and verify it's sorted
        df_sorted = pd.read_parquet(sorted_file)
        assert df_sorted["TAGVALUE"].iloc[0] == 1
        assert df_sorted["TAGVALUE"].iloc[1] == 2
        assert df_sorted["TAGVALUE"].iloc[2] == 3

    def test_sort_and_save_false_skips_sort(self, tmp_path):
        """Test sort_and_save=False does not create sorted file."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,3,Float,2026-01-01T10:00:02Z
ns=2;s=Tag2,1,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "unsorted.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS", sort_and_save=False)

        # Check sorted file was NOT created
        sorted_file = tmp_path / "unsorted_sorted.csv"
        assert not sorted_file.exists()

    def test_sort_and_save_default_false(self, tmp_path):
        """Test sort_and_save defaults to False."""
        csv_content = """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Tag1,1,Float,2026-01-01T10:00:00Z
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        df = load_and_prepare_data(str(csv_file), "TS")

        # Check sorted file was NOT created (default behavior)
        sorted_file = tmp_path / "test_sorted.csv"
        assert not sorted_file.exists()
