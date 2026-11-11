import collections
import datetime
import decimal
import enum
import fractions
import json
import pickle
import struct
import uuid
import zoneinfo

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

from app.modules.workflow.script_results import _MARKER, _flatbuffer_field, _flatbuffer_target, decode_result
from app.modules.workflow.utils import _encode_result, _execute_python_code_sync


def _round_trip(value):
    return decode_result(_encode_result({"result": value, "output": "", "errors": ""}))


def _global_pickle(module, name, then=b""):
    """A protocol 4 pickle that loads the global module.name, then runs the extra opcodes"""
    module_bytes, name_bytes = module.encode(), name.encode()
    return (
        b"\x80\x04\x8c" + bytes([len(module_bytes)]) + module_bytes
        + b"\x8c" + bytes([len(name_bytes)]) + name_bytes + b"\x93" + then + b"."
    )


def _arrow_bytes(array_or_table, options=None):
    sink = pa.BufferOutputStream()
    table = array_or_table if isinstance(array_or_table, pa.Table) else pa.table({"c": array_or_table})
    with pa.ipc.new_stream(sink, table.schema, options=options) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _overlapping_buffers(data):
    """The stream with every buffer of its record batch pointing at the whole body"""
    data = bytearray(data)
    position = 0
    while size := struct.unpack_from("<i", data, position + 4)[0]:
        metadata = memoryview(data)[position + 8:position + 8 + size]
        message = _flatbuffer_target(metadata, 0)
        body_field = _flatbuffer_field(metadata, message, 3)
        body = struct.unpack_from("<q", metadata, body_field)[0] if body_field else 0
        if metadata[_flatbuffer_field(metadata, message, 1)] == 3:  # a record batch
            batch = _flatbuffer_target(metadata, _flatbuffer_field(metadata, message, 2))
            buffers = _flatbuffer_target(metadata, _flatbuffer_field(metadata, batch, 2))
            for entry in range(struct.unpack_from("<I", metadata, buffers)[0]):
                struct.pack_into("<qq", metadata, buffers + 4 + 16 * entry, 0, body)
        position += 8 + size + body
    return bytes(data)


def _crafted_frame(column, index=None):
    return {
        _MARKER: "frame", "name": None, "attrs": {}, "data": [column],
        "index": index or {"range": [0, 2, 1], "names": [None]}, "columns": {"values": ["c"], "names": [None]},
    }


class _Level(enum.IntEnum):
    HIGH = 3


@pytest.mark.parametrize(
    "value",
    [
        {"a": 1, "b": [1.5, "x", None, True], "c": (1, 2), "d": {1, 2}, "e": frozenset({3}), "f": b"by", "g": 1 + 2j},
        [datetime.datetime(2024, 1, 2, 3, 4), datetime.date(2024, 1, 2), datetime.time(1, 2), datetime.timedelta(1)],
        [datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc), decimal.Decimal("1.5"), np.complex128(1j)],
        {datetime.date(2024, 1, 1): {datetime.datetime(2024, 1, 1, 9)}, (1, datetime.timedelta(1)): 2},
        {frozenset({datetime.date(2024, 1, 1)}): 1},
        {_MARKER: 1, "x": [2], "y": (_MARKER, "tuple"), "z": (_MARKER,)},
        [2**70, -(2**70), 2**2100, bytearray(b"ba"), "x" * 300, b"y" * 300, (1,), (1, 2, 3, 4), [b"ab"] * 2],
        [str(number) for number in range(300)] * 2,
    ],
)
def test_plain_values_come_back_unchanged(value):
    assert _round_trip(value)["result"] == value


def test_datetimes_whose_zone_has_no_offset_come_back_naive():
    class NoOffset(datetime.tzinfo):
        def utcoffset(self, dt):
            return None

    result = _round_trip(datetime.datetime(2024, 1, 1, tzinfo=NoOffset()))["result"]

    assert result == datetime.datetime(2024, 1, 1) and result.tzinfo is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (collections.OrderedDict(a=1), {"a": 1}),
        (collections.defaultdict(list, a=[1]), {"a": [1]}),
        (collections.Counter("aab"), {"a": 2, "b": 1}),
        (collections.deque([1, 2]), [1, 2]),
        ([np.int64(1), np.float64(1.5), np.bool_(True), np.longdouble(2.5)], [1, 1.5, True, 2.5]),
        (np.datetime64("2024-01-01"), datetime.date(2024, 1, 1)),
        (np.array(["2024-01-01T00:00:00.000000001"], dtype="datetime64[ns]"), [datetime.datetime(2024, 1, 1)]),
        (np.array([[1, 2], [3, 4]]), [[1, 2], [3, 4]]),
        (pd.Timedelta(1, "D"), datetime.timedelta(days=1)),
        ([pd.NaT, pd.NA, np.datetime64("NaT")], [None, None, None]),
        ([pd.Period("2024-01", freq="M"), pd.Interval(0, 1)], ["2024-01", "(0, 1]"]),
        ([fractions.Fraction(1, 4), _Level.HIGH], [0.25, 3]),
        (uuid.UUID(int=1), "00000000-0000-0000-0000-000000000001"),
        ({range(2): [range(3)]}, {(0, 1): [(0, 1, 2)]}),
    ],
)
def test_library_values_come_back_as_plain_values(value, expected):
    result = _round_trip(value)["result"]

    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    "value",
    [
        pd.Timestamp("2024-07-01 12:00", tz="Europe/Berlin"),
        datetime.datetime(2024, 1, 1, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")),
    ],
)
def test_named_timezones_become_fixed_offsets(value):
    result = _round_trip(value)["result"]

    assert result == value
    assert type(result) is datetime.datetime and type(result.tzinfo) is datetime.timezone


def test_dataframes_and_series_keep_dtypes_and_index():
    frame = pd.DataFrame({
        "i": [1, 2], "f": [1.5, None], "b": [True, False], "s": ["a", "b"],
        "dt": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "utc": pd.to_datetime(["2024-01-01", "2024-01-02"]).tz_localize("UTC"),
        "berlin": pd.to_datetime(["2024-01-01", "2024-01-02"]).tz_localize("Europe/Berlin"),
        "td": pd.to_timedelta([1, 2], unit="D"), "cat": pd.Categorical(["x", "y"]), "ci": pd.Categorical([1, 2]),
        "I64": pd.array([1, None], dtype="Int64"), "U8": pd.array([1, None], dtype="UInt8"),
        "B": pd.array([True, None], dtype="boolean"), "S": pd.array(["a", None], dtype="string"),
        "F64": pd.array([1.5, None], dtype="Float64"), "p": pd.period_range("2024-01-01", periods=2, freq="D"),
    })
    frames = [frame, frame.set_index("dt"), frame.set_index(["i", "s"]), frame.set_index("td"),
              frame.set_index("cat"), frame.groupby("s").agg({"i": "sum", "f": "mean"}), frame[["i", "f"]].describe(),
              pd.DataFrame({True: [1], False: [2]}), pd.DataFrame([[1, 2]], columns=[1, "a"]),
              pd.DataFrame([[1, 2]], columns=["a", "a"]), pd.DataFrame({"x": [1]}, index=pd.Index([5], name=0)),
              pd.DataFrame([[1, 2]], columns=pd.MultiIndex.from_tuples([("a", "x"), ("a", "y")], names=["l", "m"])),
              pd.DataFrame([[1, 2]], columns=pd.period_range("2024-01", periods=2, freq="M")),
              pd.DataFrame([[1, 2]], columns=pd.CategoricalIndex(["a", "b"])),
              pd.DataFrame({"x": [1, 2]}, index=["a", "a"]), pd.DataFrame(), pd.DataFrame(index=range(30)), frame[[]],
              pd.DataFrame(index=pd.Index(np.arange(1_200_000) * 2)),
              pd.DataFrame({"x": [1]}, index=pd.Index([1], name=datetime.date(2024, 1, 1)))]
    for value in frames:
        pd.testing.assert_frame_equal(_round_trip(value)["result"], value)
    filtered = frame.set_index(["i", "s"]).iloc[:1]
    assert _round_trip(filtered)["result"].index.levels[1].tolist() == ["a", "b"]
    series = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"), name="n")
    pd.testing.assert_series_equal(_round_trip(series)["result"], series, check_freq=False)
    row = pd.DataFrame({"x": [1.5], "y": [2.5]}, index=pd.to_datetime(["2024-01-01"])).iloc[0]
    assert _round_trip(row)["result"].name == pd.Timestamp("2024-01-01")
    nested = _round_trip({"frames": [frame[["i"]]]})["result"]
    pd.testing.assert_frame_equal(nested["frames"][0], frame[["i"]])


def test_columns_arrow_cannot_round_trip_come_back_as_plain_values():
    frame = pd.DataFrame({"age": [10, 25, 40], "span": pd.arrays.IntervalArray.from_breaks([0, 1, 2, 3])})
    frame["band"] = pd.cut(frame["age"], bins=3)
    frame.attrs = {"note": "dates parsed with dateutil"}

    result = _round_trip(frame)["result"]

    pd.testing.assert_series_equal(result["age"], frame["age"])
    assert result["span"].tolist() == ["(0, 1]", "(1, 2]", "(2, 3]"]
    assert result["band"].tolist() == [str(band) for band in frame["band"]]
    assert isinstance(result["band"].dtype, pd.CategoricalDtype)
    assert result.attrs == frame.attrs
    banded = pd.DataFrame({"band": pd.cut(np.arange(100_000), bins=5)})
    assert len(_encode_result({"result": banded, "output": "", "errors": ""})) < 500_000
    assert _round_trip(frame.dtypes.to_dict())["result"] == {name: str(dtype) for name, dtype in frame.dtypes.items()}
    zoned = pd.Series(pd.date_range("2020-01-01", periods=2, tz="Europe/Berlin")).astype("category")
    assert _round_trip(zoned)["result"].tolist() == zoned.tolist()
    vectors = pd.Series([[1.0, 2.0], [3.0, 4.0]], dtype=pd.ArrowDtype(pa.list_(pa.float32(), 2)))
    assert [list(item) for item in _round_trip(vectors)["result"]] == [[1.0, 2.0], [3.0, 4.0]]


def test_pyarrow_backed_columns_keep_their_dtype():
    columns = [
        pd.Series([decimal.Decimal("1.50"), None], dtype=pd.ArrowDtype(pa.decimal128(5, 2))),
        pd.Series(["a", "b"], dtype=pd.ArrowDtype(pa.dictionary(pa.int32(), pa.string()))),
        pd.Series(["x", None], dtype=pd.StringDtype("pyarrow")),
        pd.concat([pd.Series([1], dtype="int64[pyarrow]"), pd.Series([2], dtype="int64[pyarrow]")], ignore_index=True),
    ]
    for column in columns:
        pd.testing.assert_series_equal(_round_trip(column)["result"], column)
    assert _round_trip(pd.Series([1, 2], name=range(2)))["result"].name == (0, 1)


def test_offset_and_zoneinfo_timestamps_stay_timezone_aware():
    frame = pd.DataFrame({
        "offset": pd.to_datetime(["2020-01-01T00:00:00+02:00", "2020-01-02T00:00:00+02:00"]),
        "zoned": pd.date_range("2024-01-01", periods=2, tz=zoneinfo.ZoneInfo("Europe/Berlin")),
    })

    result = _round_trip(frame)["result"]

    for column in frame:
        assert isinstance(result[column].dtype, pd.DatetimeTZDtype)
        assert result[column].tolist() == frame[column].tolist()


def test_object_columns_keep_their_exact_values():
    when = datetime.datetime(2024, 1, 1)
    frame = pd.DataFrame({
        "mixed": pd.Series(["a", np.nan, None, 1], dtype=object),
        "nested": pd.Series([{"a": 1}, {"b": "x"}, None, [1, 2]], dtype=object),
        "ints": pd.Series([1, None, 3, 4], dtype=object),
        "dates": pd.Series([when, None, when, when], dtype=object),
    })
    frame.index = pd.Index([when, when, "x", 1], dtype=object)

    result = _round_trip(frame)["result"]

    pd.testing.assert_frame_equal(result, frame)
    assert result["mixed"].iloc[2] is None and np.isnan(result["mixed"].iloc[1])
    assert result["nested"].tolist() == [{"a": 1}, {"b": "x"}, None, [1, 2]]
    assert result["ints"].dtype == object and result["dates"].dtype == object and result.index.dtype == object
    stamps = pd.Series([1, 2], index=pd.Index([pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")], dtype=object))
    assert _round_trip(stamps)["result"].index.dtype == object


@pytest.mark.parametrize(
    "value, reason",
    [
        ((i for i in range(3)), "builtins.generator objects can't be returned"),
        ({"model": object()}, "builtins.object objects can't be returned"),
        (datetime.time(1, 2, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")), "Times with a named timezone"),
        ({pd.Timestamp("2024-01-01 00:00:00.000000001"): 1, pd.Timestamp("2024-01-01"): 2}, "Two dict keys"),
        (
            {
                pd.Timestamp("2020-01-01 12:00:00.000000001", tz="UTC"): "a",
                datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone(datetime.timedelta(hours=1))): "b",
            },
            "Two dict keys",
        ),
        (np.datetime64("10000-01-01"), "outside Python's date and duration range"),
        (np.timedelta64(1, "M"), "in months, in years or without a unit"),
        (np.timedelta64(5), "in months, in years or without a unit"),
        (
            pd.Series([1, 2], index=pd.MultiIndex.from_arrays(
                [pd.Index([pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01 00:00:00.000000001")], dtype=object),
                 [1, 1]],
            )),
            "Two index level values become equal",
        ),
        (np.zeros(1, dtype=[("t", "M8[ns]")]), "Structured arrays with date or duration fields"),
        (np.zeros(1, dtype=[("s", [("t", "M8[ns]")])]), "Structured arrays with date or duration fields"),
    ],
)
def test_values_the_parent_cannot_take_are_refused_in_the_child(value, reason):
    response = decode_result(_encode_result({"result": value, "output": "printed\n", "errors": ""}))

    assert "result" not in response
    assert response["error"].startswith("Result could not be serialized: ")
    assert reason in response["error"]
    assert response["output"] == "printed\n"


def test_a_refusal_keeps_its_message_short():
    class Loud(datetime.tzinfo):
        def utcoffset(self, dt):
            raise ValueError("x" * 100_000)

    response = decode_result(_encode_result({"result": datetime.datetime(2024, 1, 1, tzinfo=Loud()), "output": ""}))

    assert response["error"].startswith("Result could not be serialized: ") and len(response["error"]) < 5000


@pytest.mark.parametrize(
    "module, name",
    [("os", "system"), ("builtins", "eval"), ("numpy", "dtype"), ("pandas.core.frame", "DataFrame"),
     ("uuid", "UUID"), ("builtins", "complex"), ("datetime", "datetime"), ("decimal", "Decimal")],
)
def test_parent_refuses_every_global(module, name):
    with pytest.raises(pickle.UnpicklingError):
        decode_result(_global_pickle(module, name))


def test_parent_validates_columns_before_pandas_reads_them():
    bad_codes = pa.DictionaryArray.from_arrays(pa.array([0, 100], pa.int8()), pa.array([10, 20]), safe=False)
    dateutil_tz = pa.array([0], pa.timestamp("ns", tz="dateutil//etc/passwd"))
    table = pa.Table.from_pandas(pd.DataFrame({"c": pd.to_datetime(["2024-01-01"])}), preserve_index=False)
    escaped = b'"datetime64[ns, dateutil\\/\\/etc\\/hosts]"'
    metadata = table.schema.metadata[b"pandas"].replace(b'"datetime64[ns]"', escaped)
    escaped_tz = table.replace_schema_metadata({b"pandas": metadata})
    assert b"dateutil/" not in metadata and "dateutil//etc/hosts" in json.dumps(escaped_tz.schema.pandas_metadata)
    bad_level = {"levels": [["a"]], "codes": [[0, 5]], "names": [None]}

    with pytest.raises(pa.ArrowInvalid):
        decode_result(pickle.dumps({"result": _crafted_frame({"arrow": _arrow_bytes(bad_codes), "mapper": "arrow"})}))
    for crafted in (dateutil_tz, escaped_tz):
        with pytest.raises(ValueError, match="dateutil"):
            decode_result(pickle.dumps({"result": _crafted_frame(_arrow_bytes(crafted))}))
    with pytest.raises(ValueError, match="bytes or a list"):
        decode_result(pickle.dumps({"result": _crafted_frame("/etc/passwd")}))
    with pytest.raises(ValueError):
        decode_result(pickle.dumps({"result": _crafted_frame([1, 2], index=bad_level)}))
    for codes in ([bytearray(2)], [[" 0", " 1"]], [(0, 1)]):
        index = {"levels": [["a", "b"]], "codes": codes, "names": [None]}
        with pytest.raises(ValueError, match="lists of integers"):
            decode_result(pickle.dumps({"result": _crafted_frame([1, 2], index=index)}, protocol=5))


@pytest.mark.parametrize(
    "opcodes", [b"}r\x01\x00\x00\x00.", b"}p1\n.", b"}2.", b"}\x94\x94.", b"}" + b"(" * 1001 + b".", b"}", b"}.."]
)
def test_parent_reads_only_the_opcodes_the_child_writes(opcodes):
    with pytest.raises(pickle.UnpicklingError):
        decode_result(b"\x80\x04" + opcodes)


def test_parent_unpickles_the_bytes_it_checked():
    hidden = b"}\x8c\x06result\x8c\x06hiddens"
    # BININT's argument runs past the 3-byte frame, so a reader that refills there would run `hidden` as opcodes
    crossing = b"\x80\x05\x95" + (3).to_bytes(8, "little") + b"Jxyab" + b"C" + bytes([len(hidden)]) + hidden + b"."

    with pytest.raises(pickle.UnpicklingError, match="not a dict"):
        decode_result(crossing)


def test_parent_refuses_a_payload_that_repeats_anything_but_text():
    shared, cycle, doubling = [1], [], ()
    cycle.append(cycle)
    for _ in range(30):
        doubling = (doubling, doubling)
    repeated_int = b"\x80\x05}\x8c\x06result](\x8a\x01\x05\x94h\x00es."

    for value in ([shared, shared], {"a": shared, "b": shared}, ((shared,), (shared,)), cycle, [doubling]):
        with pytest.raises(pickle.UnpicklingError, match="only repeat text and bytes"):
            decode_result(pickle.dumps({"result": value}))
    with pytest.raises(pickle.UnpicklingError, match="only repeat text and bytes"):
        decode_result(repeated_int)
    assert _round_trip(["word"] * 3 + [b"by"] * 3)["result"] == ["word"] * 3 + [b"by"] * 3


def test_parent_refuses_tuples_nested_too_deeply_to_hash():
    nested = ()
    for _ in range(100):
        nested = (nested,)
    one_tuples = b"\x80\x05}\x8c\x06result)" + b"\x85" * 1000 + b"s."
    pairs = b"\x80\x05}\x8c\x06result)" + b"N\x86" * 1000 + b"s."

    assert _round_trip({nested: 1})["result"] == {nested: 1}
    for data in (one_tuples, pairs):
        with pytest.raises(pickle.UnpicklingError, match="nests tuples too deeply"):
            decode_result(data)


def test_parent_refuses_frames_that_decode_to_more_than_they_hold():
    two_batches = pa.Table.from_batches([pa.record_batch([pa.array([1])], names=["c"])] * 2)
    many_nulls = {"arrow": _arrow_bytes(pa.nulls(100_000)), "mapper": "arrow"}
    column = _arrow_bytes(pa.array([1, 2]))
    read_twice = {**_crafted_frame(column), "data": [column, column], "columns": {"values": [1, 2], "names": [None]}}
    no_columns = {**_crafted_frame(None, index={"range": [0, 10**18, 1], "names": [None]}), "data": [],
                  "columns": {"range": [0, 0, 1], "names": [None]}}
    cases = [
        (_crafted_frame(_arrow_bytes(pa.array([1, 2]), pa.ipc.IpcWriteOptions(compression="zstd"))), "compressed"),
        (_crafted_frame(_arrow_bytes(two_batches)), "more than one record batch"),
        (_crafted_frame(many_nulls, index={"range": [0, 100_000, 1], "names": [None]}), "more values than it holds"),
        (read_twice, "more decoding than its size"),
        (no_columns, "more decoding than its size"),
        (_crafted_frame(_overlapping_buffers(_arrow_bytes(pa.array([1, 2])))), "add up to more than"),
        (_crafted_frame(_arrow_bytes(pa.array([1, 2, 3]))), "lengths differ"),
        (_crafted_frame([1, 2, 3]), "lengths differ"),
    ]

    for frame, reason in cases:
        with pytest.raises(ValueError, match=reason):
            decode_result(pickle.dumps({"result": frame}))


@pytest.mark.parametrize(
    "column, mapper",
    [
        (pa.nulls(2), None), (pa.array([{"a": 1}, {"a": 2}]), None), (pa.array([[1], [2]]), None),
        (pa.array(["a", "b"]).dictionary_encode(), None), (pa.array(["a", "b"], pa.string_view()), "arrow"),
        (pa.StructArray.from_arrays([pa.array(["a", "b"]).dictionary_encode()], names=["a"]), "arrow"),
    ],
)
def test_parent_converts_only_flat_column_types(column, mapper):
    spec = {"arrow": _arrow_bytes(column), "mapper": mapper}

    with pytest.raises(ValueError, match="type can't be decoded"):
        decode_result(pickle.dumps({"result": _crafted_frame(spec)}))


def test_parent_reads_only_the_column_dtype_from_pandas_metadata():
    table = pa.Table.from_pandas(pd.DataFrame({"c": [1, 2]}), preserve_index=False)
    metadata = table.schema.pandas_metadata
    label_dtype = {"name": None, "field_name": None, "pandas_type": "unicode", "numpy_type": "S20000000"}
    labels = {**metadata, "column_indexes": [{**label_dtype, "metadata": None}]}
    long_name = {**metadata, "columns": [{**metadata["columns"][0], "numpy_type": "(" * 2000 + "[pyarrow]"}]}
    two_columns = {**metadata, "columns": metadata["columns"] * 2}
    flags = pa.Table.from_pandas(pd.DataFrame({"c": [True, False]}), preserve_index=False)
    flag_column = flags.schema.pandas_metadata["columns"][0]

    def crafted(pandas_metadata, source=table):
        column = _arrow_bytes(source.replace_schema_metadata({b"pandas": json.dumps(pandas_metadata).encode()}))
        return pickle.dumps({"result": _crafted_frame(column)})

    assert decode_result(crafted(labels))["result"]["c"].tolist() == [1, 2]
    for pandas_metadata in (long_name, two_columns):
        with pytest.raises(ValueError, match="isn't what the child writes"):
            decode_result(crafted(pandas_metadata))
    for numpy_type in ("large_string[pyarrow]", "string", "Int64"):
        widened = {**metadata, "columns": [{**flag_column, "numpy_type": numpy_type}]}
        with pytest.raises(ValueError, match="dtype the column can.t take"):
            decode_result(crafted(widened, flags))


def test_parent_ignores_an_extension_type_s_own_metadata():
    period_type = type(pa.array(pd.period_range("2024-01-01", periods=1, freq="D")).type)
    column = pa.ExtensionArray.from_storage(period_type("1" * 10_000), pa.array([1, 2], pa.int64()))

    result = decode_result(pickle.dumps({"result": _crafted_frame(_arrow_bytes(column))}))["result"]

    assert result["c"].tolist() == [1, 2]


def test_only_frame_columns_and_index_values_stay_in_arrow():
    arrow = {"arrow": _arrow_bytes(pa.array([1, 2])), "mapper": "arrow"}
    codes = _arrow_bytes(pa.array([0, 1], pa.int8()))
    levels = {"levels": [arrow], "codes": [[0, 1]], "names": [None]}
    categories = {"codes": codes, "categories": arrow, "ordered": False}
    arrow_level = pd.MultiIndex.from_arrays([pd.array([1, 2], dtype="int64[pyarrow]"), ["a", "b"]])

    for frame in (_crafted_frame([1, 2], index=levels), _crafted_frame(categories)):
        with pytest.raises(ValueError, match="Only frame columns and index values"):
            decode_result(pickle.dumps({"result": frame}))
    assert _round_trip(pd.DataFrame({"x": [1, 2]}, index=arrow_level))["result"].index.tolist() == [(1, "a"), (2, "b")]


def test_parent_takes_category_codes_only_as_integers():
    codes = _arrow_bytes(pa.array([0, 0], pa.int8()))
    inner = {"codes": codes, "categories": ["x" * 100], "ordered": False}
    nested = {"codes": inner, "categories": [0], "ordered": False}
    cases = [
        (nested, "must be an Arrow column"),
        ({"codes": [0, 0], "categories": ["a"], "ordered": False}, "must be an Arrow column"),
        ({"codes": codes, "categories": {"codes": codes, "categories": ["a"], "ordered": False}, "ordered": False},
         "can't be categorical"),
        ({"codes": _arrow_bytes(pa.array([0.0, 0.0])), "categories": ["a"], "ordered": False}, "must be integers"),
    ]

    for column, reason in cases:
        with pytest.raises(ValueError, match=reason):
            decode_result(pickle.dumps({"result": _crafted_frame(column)}))


def test_parent_rebuilds_marked_values_through_checking_constructors():
    day_zero = (_MARKER, "datetime", 2024, 1, 0, 99, 0, 0, 0, 0, None, None)
    flags_before = dict(decimal.getcontext().flags)

    with pytest.raises(ValueError):
        decode_result(pickle.dumps({"result": [day_zero]}))
    with pytest.raises(decimal.InvalidOperation):
        decode_result(pickle.dumps({"result": (_MARKER, "decimal", "not a number")}))
    with pytest.raises(ValueError, match="Unknown marked value"):
        decode_result(pickle.dumps({"result": (_MARKER, "eval", "1")}))
    assert dict(decimal.getcontext().flags) == flags_before


def test_parent_parses_each_text_once():
    digits = "1" * 1000
    cases = [
        ([(_MARKER, "decimal", digits), (_MARKER, "decimal", digits)], "more decoding than its size"),
        ((_MARKER, "decimal", 10**1000), "as its text"),
        ((_MARKER, "complex", "1e999", 0.0), "two floats"),
        (_crafted_frame([1, 2], index={"levels": [[digits, digits]], "codes": [[0, 1]], "names": [None]}), "unique"),
    ]

    for value, reason in cases:
        with pytest.raises(ValueError, match=reason):
            decode_result(pickle.dumps({"result": value}))
    with pytest.raises(pickle.UnpicklingError, match="must be text"):
        decode_result(pickle.dumps({"result": 1, "output": [digits, digits]}))


def test_parent_refuses_a_tampered_child_result():
    code = (
        "class Calls:\n"
        "    def __reduce__(self):\n"
        "        return (math.factorial, (5,))\n"
        "traceback.sys.modules['app.modules.workflow.utils'].to_plain = lambda value: value\n"
        "result = Calls()\n"
    )

    response = _execute_python_code_sync(code, {}, wrap_code=False)

    assert response["error"] == "Script result could not be decoded: UnpicklingError"


def test_undecodable_column_data_is_reported_as_a_decode_error():
    frame = _crafted_frame(b"\xff\xff\xff\xff\x10\x00\x00\x00")
    code = (
        "modules = traceback.sys.modules\n"
        f"data = modules['pickle'].dumps({{'result': {frame!r}}})\n"
        "modules['app.modules.workflow.utils']._encode_result = lambda payload, limit=0: data\n"
        "result = 1\n"
    )

    response = _execute_python_code_sync(code, {}, wrap_code=False)

    assert response["error"].startswith("Script result could not be decoded: ")


def test_dataframe_result_comes_back_from_the_sandbox():
    code = (
        "result = pandas.DataFrame({'a': [1, 2], 'c': pandas.Categorical(['x', 'y']),\n"
        "    't': pandas.to_datetime(['2024-01-01', '2024-01-02']).tz_localize('Europe/Berlin')})\n"
    )
    expected = pd.DataFrame({
        "a": [1, 2], "c": pd.Categorical(["x", "y"]),
        "t": pd.to_datetime(["2024-01-01", "2024-01-02"]).tz_localize("Europe/Berlin"),
    })

    response = _execute_python_code_sync(code, {}, wrap_code=False)

    assert "error" not in response
    pd.testing.assert_frame_equal(response["result"], expected)
