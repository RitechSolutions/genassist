"""
A CSV upload's leading-zero values ("001", postcodes, product codes) must stay
text when the file is read, instead of pandas turning "001" into 1. Every
other column keeps pandas' own type inference.
"""

import io

import pandas as pd
import pytest

from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.training_file_readers import _csv_rows_frame

CSV = (
    "customer_id,zip,amount,count,name,ratio\n"
    "001,02134,10.5,1,Ann,0.5\n"
    "002,10001,20.0,2,Bob,0.25\n"
    "010,,30.25,3,,0\n"
    "100,90210,,4,Dee,1.0\n"
)


def _write(tmp_path, text=CSV, name="upload.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestUploadsKeepLeadingZeros:
    def test_leading_zero_columns_are_read_as_text(self, tmp_path):
        df = ml_utils.read_csv_with_dtypes(_write(tmp_path), encoding="utf-8")

        assert df["customer_id"].tolist() == ["001", "002", "010", "100"]
        assert df["zip"].tolist()[:2] == ["02134", "10001"]
        assert pd.isna(df["zip"].iloc[2])  # an empty cell stays missing, not "nan"

    def test_other_columns_keep_pandas_inference(self, tmp_path):
        df = ml_utils.read_csv_with_dtypes(_write(tmp_path), encoding="utf-8")

        assert str(df["amount"].dtype) == "float64"
        assert str(df["count"].dtype) == "int64"
        # "0.5" and "0" are ordinary numbers, not leading-zero codes.
        assert str(df["ratio"].dtype) == "float64"

    def test_file_without_leading_zeros_reads_exactly_as_plain_read_csv(self, tmp_path):
        path = _write(tmp_path, "a,b,c\n1,2.5,x\n0,0.1,y\n-3,,z\n")
        pd.testing.assert_frame_equal(
            ml_utils.read_csv_with_dtypes(path), pd.read_csv(path)
        )

    @pytest.mark.parametrize("value", ["007", "0123", "-01", "00.5", " 042 "])
    def test_leading_zero_forms(self, tmp_path, value):
        df = ml_utils.read_csv_with_dtypes(_write(tmp_path, f'code\n"{value}"\n5\n'))
        assert df["code"].tolist() == [value, "5"]

    @pytest.mark.parametrize("value", ["0", "0.5", "-0.25", "10", "0e5"])
    def test_ordinary_numbers_stay_numbers(self, tmp_path, value):
        df = ml_utils.read_csv_with_dtypes(_write(tmp_path, f"n\n{value}\n5\n"))
        assert df["n"].dtype.kind in "if"

    def test_read_options_apply_to_both_reads(self, tmp_path):
        df = ml_utils.read_csv_with_dtypes(_write(tmp_path), encoding="utf-8", nrows=2)
        assert df["customer_id"].tolist() == ["001", "002"]

    def test_load_csv_file_and_analysis_see_text(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
        path = _write(tmp_path)

        assert ml_utils.load_csv_file(str(path))["customer_id"].tolist()[0] == "001"
        analysis = ml_utils.analyze_csv_data(str(path))
        assert analysis["sample_data"][0]["customer_id"] == "001"

    def test_unusable_saved_dtypes_fall_back_and_still_keep_zeros(self, tmp_path):
        path = _write(tmp_path, "code,n\n001,not a number\n")
        ml_utils.dtypes_sidecar_path(path).write_text('{"n": "Int64"}')
        df = ml_utils.read_csv_with_dtypes(path)
        assert df["code"].tolist() == ["001"]
        assert df["n"].tolist() == ["not a number"]

    def test_saved_text_type_still_wins(self, tmp_path):
        path = _write(tmp_path, "code\n001\n")
        ml_utils.dtypes_sidecar_path(path).write_text('{"code": "object"}')
        assert ml_utils.read_csv_with_dtypes(path)["code"].tolist() == ["001"]


class TestTrainDataSourcePreview:
    def test_preview_keeps_leading_zeros(self):
        frame = _csv_rows_frame(["id", "n"], [("001", "1"), ("002", "2")])
        assert frame["id"].tolist() == ["001", "002"]
        assert str(frame["n"].dtype) == "int64"

    def test_buffer_reader_rewinds_between_reads(self):
        df = ml_utils.read_csv_keeping_leading_zeros(io.StringIO("id,n\n001,1\n"))
        assert df.to_dict("records") == [{"id": "001", "n": 1}]


def test_leading_zeros_past_the_first_scan_chunk_are_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_utils, "_LEADING_ZERO_SCAN_CHUNK_ROWS", 2)
    path = _write(tmp_path, "code,n\n1,1\n2,2\n3,3\n004,4\n")
    df = ml_utils.read_csv_with_dtypes(path)
    assert df["code"].tolist() == ["1", "2", "3", "004"]
    assert str(df["n"].dtype) == "int64"


def test_a_buffer_is_read_from_where_it_started():
    buffer = io.StringIO("skip me\ncode\n007\n")
    buffer.readline()
    assert ml_utils.read_csv_keeping_leading_zeros(buffer)["code"].tolist() == ["007"]


def test_saved_types_still_apply_when_a_row_limit_is_passed(tmp_path):
    path = _write(tmp_path, "level,code\nlow,001\nhigh,002\nlow,003\n")
    ml_utils.dtypes_sidecar_path(path).write_text('{"level": "category", "code": "object"}')
    df = ml_utils.read_csv_with_dtypes(path, encoding="utf-8", nrows=2)
    assert isinstance(df["level"].dtype, pd.CategoricalDtype)
    assert df["code"].tolist() == ["001", "002"]
