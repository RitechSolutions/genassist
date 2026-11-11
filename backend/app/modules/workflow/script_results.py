"""Script results travel from the sandbox child to the backend as plain data that unpickles without globals.

The child runs user code, so any global the backend's unpickler resolved could be made to run code there.
"""

import collections
import contextvars
import datetime
import decimal
import fractions
import json
import pickle
import struct
import uuid
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

_PLAIN_TYPES = (type(None), bool, int, float, str, bytes, bytearray)
# Returned as text, the way workflow state shows them
_TEXT_TYPES = (uuid.UUID, pd.Period, pd.Interval, pd.offsets.BaseOffset, np.dtype, pd.api.extensions.ExtensionDtype)
# Heads tuples for values the parent rebuilds through a constructor, and keys dicts that hold frames
_MARKER = "__genassist__"
# Opcodes the child's pickler writes for plain data, with the size of each argument, or minus the width of its
# length prefix. The C unpickler sizes its memo by a PUT or LONG_BINPUT index, so every other opcode is refused
_OPCODE_ARGUMENTS = {
    pickle.PROTO: 1, pickle.FRAME: 8, pickle.MARK: 0, pickle.MEMOIZE: 0, pickle.BINGET: 1, pickle.LONG_BINGET: 4,
    pickle.NONE: 0, pickle.NEWTRUE: 0, pickle.NEWFALSE: 0, pickle.BININT: 4, pickle.BININT1: 1, pickle.BININT2: 2,
    pickle.LONG1: -1, pickle.LONG4: -4, pickle.BINFLOAT: 8, pickle.SHORT_BINUNICODE: -1, pickle.BINUNICODE: -4,
    pickle.BINUNICODE8: -8, pickle.SHORT_BINBYTES: -1, pickle.BINBYTES: -4, pickle.BINBYTES8: -8,
    pickle.BYTEARRAY8: -8, pickle.EMPTY_TUPLE: 0, pickle.TUPLE1: 0, pickle.TUPLE2: 0, pickle.TUPLE3: 0,
    pickle.TUPLE: 0, pickle.EMPTY_LIST: 0, pickle.APPEND: 0, pickle.APPENDS: 0, pickle.EMPTY_DICT: 0,
    pickle.SETITEM: 0, pickle.SETITEMS: 0, pickle.EMPTY_SET: 0, pickle.ADDITEMS: 0, pickle.FROZENSET: 0,
}
_ARGUMENT_SIZES = [_OPCODE_ARGUMENTS.get(bytes([code])) for code in range(256)]
_STOP, _MARK, _MEMOIZE = pickle.STOP[0], pickle.MARK[0], pickle.MEMOIZE[0]
_GETS = frozenset({pickle.BINGET[0], pickle.LONG_BINGET[0]})
# Opcodes that push text or bytes, the only objects the child's pickler writes more than once
_TEXT_PUSHES = frozenset(opcode[0] for opcode in (
    pickle.SHORT_BINUNICODE, pickle.BINUNICODE, pickle.BINUNICODE8, pickle.SHORT_BINBYTES, pickle.BINBYTES,
    pickle.BINBYTES8, pickle.BYTEARRAY8,
))
# Opcodes that push another object whose hash doesn't recurse: numbers, and unhashable lists, dicts and sets
_FLAT_PUSHES = frozenset(opcode[0] for opcode in (
    pickle.NONE, pickle.NEWTRUE, pickle.NEWFALSE, pickle.BININT, pickle.BININT1, pickle.BININT2, pickle.LONG1,
    pickle.LONG4, pickle.BINFLOAT, pickle.EMPTY_LIST, pickle.EMPTY_DICT, pickle.EMPTY_SET,
))
# Opcodes that pop a number of items, or None for down to the last mark, and whether they push a tuple of them
_POPS = {opcode[0]: effect for opcode, effect in {
    pickle.APPEND: (1, False), pickle.SETITEM: (2, False), pickle.APPENDS: (None, False),
    pickle.SETITEMS: (None, False), pickle.ADDITEMS: (None, False), pickle.EMPTY_TUPLE: (0, True),
    pickle.TUPLE1: (1, True), pickle.TUPLE2: (2, True), pickle.TUPLE3: (3, True), pickle.TUPLE: (None, True),
    pickle.FROZENSET: (None, True),
}.items()}
# Stands for text on the followed stack, where other objects hold how deeply they nest tuples
_TEXT = -1
# Python hashes a nested tuple recursively in C, with no recursion limit
_MAX_TUPLE_DEPTH = 1000
# What the decode in progress may still spend: bytes of column data and decimal text, which a payload from the child
# holds once each, and rows of frames without columns, e.g. df[[]], which it doesn't hold at all
_budget: contextvars.ContextVar[Optional[List[int]]] = contextvars.ContextVar("budget", default=None)
_FREE_ROWS = 1_000_000


# Not safe_pickle's RestrictedUnpickler: that one is pure Python, and results can run to many MiB
class _ResultUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"Script results can't contain {module}.{name}")


class _WholeInput:
    """Gives the C unpickler all the data on its first read, so it parses the bytes straight through, as
    _check_opcodes does. From a file, it drops the rest of a frame when an argument runs past the frame's end"""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, size: int = -1) -> bytes:
        data, self._data = self._data, b""
        return data

    def readline(self) -> bytes:
        return b""


def _plain_offset(value: Union[datetime.datetime, datetime.time]) -> List[Any]:
    """[offset in microseconds, name] of the value's timezone, or [None, None] for a naive value"""
    offset = value.utcoffset()
    if offset is None:
        if value.tzinfo is not None and isinstance(value, datetime.time):
            raise TypeError("Times with a named timezone can't be returned. Return a datetime instead")
        return [None, None]
    name = value.tzname()
    return [offset // datetime.timedelta(microseconds=1), name if isinstance(name, str) else None]


def to_plain(value: Any) -> Any:
    """Copy a script result into types the parent unpickles without globals; frames become column data"""
    if type(value) in _PLAIN_TYPES:
        return value
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return _frame_to_plain(value)
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (np.ndarray, np.generic)):
        return _numpy_to_plain(value)
    if isinstance(value, pd.Timestamp):
        return to_plain(value.to_pydatetime(warn=False))
    if isinstance(value, datetime.datetime):
        fields = (value.year, value.month, value.day, value.hour, value.minute, value.second, value.microsecond)
        return (_MARKER, "datetime", *fields, value.fold, *_plain_offset(value))
    if isinstance(value, datetime.date):
        return (_MARKER, "date", value.year, value.month, value.day)
    if isinstance(value, datetime.time):
        fields = (value.hour, value.minute, value.second, value.microsecond, value.fold)
        return (_MARKER, "time", *fields, *_plain_offset(value))
    if isinstance(value, datetime.timedelta):
        return (_MARKER, "timedelta", value.days, value.seconds, value.microseconds)
    if isinstance(value, decimal.Decimal):
        return (_MARKER, "decimal", str(value))
    if isinstance(value, complex):
        return (_MARKER, "complex", value.real, value.imag)
    if isinstance(value, dict):
        plain = {to_plain(key): to_plain(item) for key, item in value.items()}
        if len(plain) != len(value) or not _stays_unique(list(plain)):
            raise TypeError("Two dict keys become equal when returned, e.g. times that differ in nanoseconds")
        return {_MARKER: "dict", "items": list(plain.items())} if _MARKER in plain else plain
    if isinstance(value, (tuple, range)):  # a range stays hashable as a tuple, e.g. as a key or a name
        items = tuple(to_plain(item) for item in value)
        return (_MARKER, "tuple", *items) if items and items[0] == _MARKER else items
    if isinstance(value, (list, collections.deque, pd.Index, pd.api.extensions.ExtensionArray)):
        return [to_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        members = [to_plain(item) for item in value]
        if not _stays_unique(members):
            raise TypeError("Two set members become equal when returned, e.g. times that differ in nanoseconds")
        return (frozenset if isinstance(value, frozenset) else set)(members)
    if isinstance(value, str):
        return str.__str__(value)
    for base in (int, float, bytes):
        if isinstance(value, base):
            return base(value)
    if isinstance(value, fractions.Fraction):
        return float(value)
    if isinstance(value, _TEXT_TYPES):
        return str(value)
    raise TypeError(
        f"{type(value).__module__}.{type(value).__qualname__} objects can't be returned. "
        "Return plain data, numpy arrays or pandas objects"
    )


def _stays_unique(values: List[Any]) -> bool:
    """Whether distinct plain values stay distinct once the parent rebuilds them, e.g. as aware datetimes"""
    if not any(type(value) in (tuple, frozenset) for value in values):
        return len(set(values)) == len(values)
    return len({_restore(value) for value in values}) == len(values)


def _has_dates(dtype: np.dtype) -> bool:
    """Whether a dtype holds datetime64 or timedelta64 anywhere, including nested and subarray fields"""
    if dtype.fields is not None:
        return any(_has_dates(field[0]) for field in dtype.fields.values())
    if dtype.subdtype is not None:
        return _has_dates(dtype.subdtype[0])
    return dtype.kind in "mM"


def _numpy_to_plain(value: Union[np.ndarray, np.generic]) -> Any:
    """numpy values as Python ones"""
    kind = value.dtype.kind
    if kind == "V" and _has_dates(value.dtype):
        raise TypeError("Structured arrays with date or duration fields can't be returned")
    if kind == "m" and np.datetime_data(value.dtype)[0] in ("Y", "M", "generic"):
        raise TypeError("timedelta64 values in months, in years or without a unit can't be returned")
    if kind in "mM" and np.datetime_data(value.dtype)[0] in ("ns", "ps", "fs", "as"):
        value = value.astype(f"{kind}8[us]")  # the finest unit Python's datetime holds
    elif value.dtype.type in (np.longdouble, np.clongdouble):
        value = value.astype(complex if kind == "c" else float)  # tolist() keeps long double as numpy
    plain = value.tolist()
    if kind in "mM":
        # tolist() gives a bare int for any date or duration Python's types can't hold
        flat = plain if np.ndim(value) == 1 else np.ravel(value).tolist()
        if any(type(item) is int for item in (flat if isinstance(flat, list) else [flat])):
            raise TypeError(f"{value.dtype} values outside Python's date and duration range can't be returned")
    return to_plain(plain) if kind in "OVcmM" else plain


def _arrow_column(column: pd.Series) -> bytes:
    import pyarrow as pa

    frame = column.to_frame(name="c")
    frame.attrs = {}  # travel once with the frame, not in every column's metadata
    table = pa.Table.from_pandas(frame, preserve_index=False).combine_chunks()  # the parent takes one record batch
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _tz_key(tz: Any) -> Any:
    """A zone's name, or its offset, so the pytz, zoneinfo and datetime.timezone forms of a zone compare equal"""
    name = getattr(tz, "key", None) or getattr(tz, "zone", None)
    if name == "UTC":
        return datetime.timedelta(0)
    return name or tz.utcoffset(None)


def _same_dtype(decoded: Any, original: Any) -> bool:
    if isinstance(original, pd.DatetimeTZDtype):
        return (
            isinstance(decoded, pd.DatetimeTZDtype) and decoded.unit == original.unit
            and _tz_key(decoded.tz) == _tz_key(original.tz)
        )
    return decoded == original


def _arrow_mapper(dtype: Any) -> Any:
    """How a pyarrow-backed column decodes, since Arrow's default mapping picks NumPy-backed dtypes"""
    if isinstance(dtype, pd.ArrowDtype):
        return "arrow"
    if isinstance(dtype, pd.StringDtype) and dtype.storage == "pyarrow" and dtype.na_value is pd.NA:
        return "pyarrow_string"
    return None


def _column_to_plain(column: pd.Series) -> Union[bytes, List[Any], Dict[str, Any]]:
    """Typed columns go as one-column Arrow data, which keeps their dtype; object columns as plain values"""
    import pyarrow  # noqa: F401  # required: without it every typed column would silently lose its dtype

    categorical = isinstance(column.dtype, pd.CategoricalDtype)
    if column.dtype != object and not categorical:
        try:
            spec: Any = _arrow_column(column)
            mapper = _arrow_mapper(column.dtype)
            if mapper:
                spec = {"arrow": spec, "mapper": mapper}
            # Some columns don't survive Arrow unchanged, e.g. sparse ones, and the parent refuses some, e.g. intervals
            decoded = pd.Series(_column_from_plain(spec, may_stay_in_arrow=True), copy=False)
            if _same_dtype(decoded.dtype, column.dtype):
                return spec
        except Exception:
            pass  # e.g. complex numbers, which Arrow has no type for
    if categorical:
        # Codes plus categories, since one plain value per row can be many times larger
        categories = _numpy_or_plain(column.cat.categories)
        try:
            unique = type(categories) is not list or _stays_unique(categories)
        except TypeError:  # a category whose plain form is a list
            unique = False
        if unique:
            codes = _column_to_plain(pd.Series(column.cat.codes))
            return {"codes": codes, "categories": categories, "ordered": bool(column.cat.ordered)}
    return to_plain(column.tolist())


def _numpy_or_plain(values: pd.Index) -> Union[bytes, List[Any], Dict[str, Any]]:
    """Levels and categories without ArrowDtype data, since the parent checks them value by value"""
    if isinstance(values.dtype, pd.ArrowDtype):
        return to_plain(values.tolist())
    return _column_to_plain(pd.Series(values, dtype=values.dtype))


def _index_to_plain(index: pd.Index) -> Dict[str, Any]:
    names = to_plain(list(index.names))
    if isinstance(index, pd.RangeIndex):
        return {"range": [index.start, index.stop, index.step], "names": names}
    if isinstance(index, pd.MultiIndex):
        levels = []
        for level in index.levels:
            plain_level = _numpy_or_plain(level)
            if isinstance(plain_level, list) and not _stays_unique(plain_level):
                raise TypeError("Two index level values become equal when returned, e.g. times in nanoseconds")
            levels.append(plain_level)
        return {"levels": levels, "codes": [codes.tolist() for codes in index.codes], "names": names}
    return {"values": _column_to_plain(pd.Series(index, dtype=index.dtype)), "names": names}


def _frame_to_plain(value: Union[pd.DataFrame, pd.Series]) -> Dict[str, Any]:
    """DataFrames and Series travel column by column, so the parent never unpickles pandas internals"""
    is_series = isinstance(value, pd.Series)
    frame = (value.to_frame() if is_series else value).copy(deep=False)
    frame.attrs = {}  # pandas deep-copies attrs into every column taken from the frame
    return {
        _MARKER: "series" if is_series else "frame",
        "name": to_plain(value.name) if is_series else None,
        "attrs": to_plain(dict(value.attrs)),
        "data": [_column_to_plain(frame.iloc[:, position]) for position in range(frame.shape[1])],
        "index": _index_to_plain(frame.index),
        "columns": _index_to_plain(frame.columns),
    }


def _strings(value: Any) -> Iterator[str]:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def _arrow_timezones(data_type: Any) -> Iterator[str]:
    import pyarrow as pa

    if pa.types.is_timestamp(data_type) and data_type.tz:
        yield data_type.tz
    if isinstance(data_type, pa.BaseExtensionType):
        yield from _arrow_timezones(data_type.storage_type)
    if pa.types.is_dictionary(data_type):
        yield from _arrow_timezones(data_type.value_type)
    for position in range(data_type.num_fields):
        yield from _arrow_timezones(data_type.field(position).type)


def _column_from_plain(column: Any, rows: Optional[int] = None, may_stay_in_arrow: bool = False) -> Any:
    """A column the child sent, as an array that keeps its dtype"""
    if type(column) is dict and "codes" in column:
        # np.asarray would expand codes of any other kind, e.g. a categorical, into one value per row
        if type(column["codes"]) is not bytes or type(column["categories"]) is dict and "codes" in column["categories"]:
            raise ValueError("Categorical codes must be an Arrow column, and categories can't be categorical")
        codes = _column_from_plain(column["codes"], rows)
        if codes.dtype.kind not in "iu":
            raise ValueError("Categorical codes must be integers")
        categories = _as_index(_column_from_plain(column["categories"]))
        # from_codes checks every code against the categories
        return pd.Categorical.from_codes(np.asarray(codes), categories=categories, ordered=column["ordered"] is True)
    if type(column) is dict:
        # Levels, codes and categories get checked value by value, so only frame columns and index values stay in Arrow
        if column["mapper"] == "arrow" and not may_stay_in_arrow:
            raise ValueError("Only frame columns and index values can stay in Arrow")
        return _arrow_values(column["arrow"], column["mapper"], rows)
    if type(column) is list:
        if rows is not None and len(column) != rows:
            raise ValueError("Column and index lengths differ")
        values = np.empty(len(column), dtype=object)
        if any(type(item) in (dict, list, tuple, set, frozenset) for item in column):
            for position, item in enumerate(column):
                values[position] = _restore(item)
        else:
            values[:] = column
        return values
    return _arrow_values(column, None, rows)


def _flatbuffer_field(buffer: Any, table: int, field: int) -> Optional[int]:
    """Where a flatbuffer table's field starts, or None when it is unset"""
    vtable = table - struct.unpack_from("<i", buffer, table)[0]
    entry = 4 + 2 * field
    if entry >= struct.unpack_from("<H", buffer, vtable)[0]:
        return None
    offset = struct.unpack_from("<H", buffer, vtable + entry)[0]
    return table + offset if offset else None


def _flatbuffer_target(buffer: Any, position: int) -> int:
    """The table or vector that the offset at this position points to"""
    return position + struct.unpack_from("<I", buffer, position)[0]


def _flatbuffer_pairs(buffer: Any, table: int, field: int) -> Tuple[int, ...]:
    """A table's vector of two-long structs, e.g. RecordBatch.nodes, as one flat tuple"""
    position = _flatbuffer_field(buffer, table, field)
    if position is None:
        return ()
    vector = _flatbuffer_target(buffer, position)
    count = struct.unpack_from("<I", buffer, vector)[0]
    return struct.unpack_from(f"<{2 * count}Q", buffer, vector + 4)


def _check_messages(data: bytes) -> None:
    """Refuse compressed bodies, which Arrow inflates while reading, buffers that overlap, which validation reads once
    each, and streams that declare more values than bits"""
    import pyarrow as pa

    values = batches = 0
    for message in pa.ipc.MessageReader.open_stream(data):
        if message.type not in ("dictionary", "record batch"):
            continue
        metadata = message.metadata
        batch = _flatbuffer_target(metadata, _flatbuffer_field(metadata, _flatbuffer_target(metadata, 0), 2))
        if message.type == "dictionary":
            batch = _flatbuffer_target(metadata, _flatbuffer_field(metadata, batch, 1))
        else:
            batches += 1
        if _flatbuffer_field(metadata, batch, 3) is not None:  # RecordBatch.compression
            raise ValueError("Column data is compressed")
        values += sum(_flatbuffer_pairs(metadata, batch, 1)[::2])  # RecordBatch.nodes: a length and null count
        if sum(_flatbuffer_pairs(metadata, batch, 2)[1::2]) > message.body.size:  # RecordBatch.buffers: offset, length
            raise ValueError("Column buffers add up to more than the column's data")
    if batches > 1:  # each record batch rebuilds the dictionaries that deltas extend
        raise ValueError("Column data has more than one record batch")
    if values > 8 * len(data):  # other values take a bit at least, so this caps nulls and nested types
        raise ValueError("Column data declares more values than it holds")


def _decodable(data_type: Any, stays_in_arrow: bool, nested: bool = False) -> bool:
    """Types whose decoding costs what their bytes do; nested, null and dictionary values only stay in Arrow"""
    import pyarrow as pa

    types = pa.types
    if isinstance(data_type, pa.BaseExtensionType):
        return _decodable(data_type.storage_type, stays_in_arrow, nested)
    flat = (types.is_integer, types.is_floating, types.is_boolean, types.is_timestamp, types.is_duration,
            types.is_string, types.is_large_string)
    if any(check(data_type) for check in flat):
        return True
    if not stays_in_arrow:
        return False
    # View types are left out: their values can share bytes, which full validation reads once per value
    arrow_flat = (types.is_null, types.is_date, types.is_time, types.is_interval, types.is_decimal,
                  types.is_binary, types.is_large_binary, types.is_fixed_size_binary)
    if any(check(data_type) for check in arrow_flat):
        return True
    if types.is_dictionary(data_type):
        # Only as the column's own type: fields that share a dictionary would each validate it
        return not nested and _decodable(data_type.value_type, True, True)
    containers = (types.is_list, types.is_large_list, types.is_fixed_size_list, types.is_struct, types.is_map)
    if any(check(data_type) for check in containers):
        children = (data_type.field(position).type for position in range(data_type.num_fields))
        return all(_decodable(child, True, True) for child in children)
    return False


def _spend(size: int = 0, rows: int = 0) -> None:
    budget = _budget.get()
    if budget is not None:
        budget[0] -= size
        budget[1] -= rows
        if budget[0] < 0 or budget[1] < 0:
            raise ValueError("Script result asks for more decoding than its size pays for")


def _column_metadata(metadata: Any) -> Dict[str, Any]:
    """The pandas metadata of the one column, with only what restores its dtype: to_pandas rebuilds column labels and
    an index from the rest through astype, and pandas parses dtype names with regexes that take time squared"""
    columns = metadata["columns"]
    if type(columns) is not list or len(columns) != 1 or type(columns[0]) is not dict:
        raise ValueError("Column metadata isn't what the child writes")
    column = columns[0]
    kept = {key: column.get(key) for key in ("name", "field_name", "pandas_type", "numpy_type")}
    extra = column.get("metadata")
    if extra is not None and not (type(extra) is dict and all(type(key) is str for key in extra)):
        raise ValueError("Column metadata isn't what the child writes")
    for value in (*kept.values(), *(extra or {}).values()):
        if not (value is None or type(value) in (bool, int) or type(value) is str and len(value) <= 1024):
            raise ValueError("Column metadata isn't what the child writes")
    return {"columns": [{**kept, "metadata": extra}], "column_indexes": [], "index_columns": []}


def _dtype_fits(data_type: Any, numpy_type: Any) -> bool:
    """Whether an extension dtype the column metadata names, which to_pandas casts the column to, keeps its width"""
    import pyarrow as pa

    dtype = pd.api.types.pandas_dtype(numpy_type)
    if not isinstance(dtype, pd.api.extensions.ExtensionDtype):
        return True  # to_pandas follows the Arrow type then
    if isinstance(dtype, pd.ArrowDtype):
        return False  # only columns sent with the "arrow" mapper stay in Arrow
    if isinstance(data_type, pa.BaseExtensionType):
        data_type = data_type.storage_type
    if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
        return isinstance(dtype, pd.StringDtype)
    if isinstance(dtype, pd.PeriodDtype):
        return pa.types.is_int64(data_type)
    numpy_dtype = getattr(dtype, "numpy_dtype", None)
    return numpy_dtype is not None and not pa.types.is_temporal(data_type) and numpy_dtype == np.dtype(
        data_type.to_pandas_dtype()
    )


def _arrow_values(data: Any, mapper: Any, rows: Optional[int] = None) -> Any:
    if type(data) is not bytes:  # pyarrow would open a str as a file path
        raise ValueError("Column data must be bytes or a list")
    _spend(len(data))
    import pyarrow as pa

    if mapper is None:
        types_mapper = None
    elif mapper == "arrow":
        types_mapper = pd.ArrowDtype
    elif mapper == "pyarrow_string":
        types_mapper = {pa.string(): pd.StringDtype("pyarrow"), pa.large_string(): pd.StringDtype("pyarrow")}.get
    else:
        raise ValueError("Unknown column mapper")
    _check_messages(data)
    reader = pa.ipc.open_stream(data)
    if len(reader.schema) != 1:
        raise ValueError("Column data must hold one column")
    data_type = reader.schema.field(0).type
    if not _decodable(data_type, mapper == "arrow"):
        raise ValueError("Column type can't be decoded")
    metadata = reader.schema.pandas_metadata
    kept = None if metadata is None else _column_metadata(metadata)
    if any("dateutil" in name for name in (*_strings(kept), *_arrow_timezones(data_type))):
        raise ValueError("Column timezone names a dateutil file")  # pandas would open the file
    # The "arrow" mapper overrides whatever dtype the metadata names
    if kept is not None and mapper != "arrow" and not _dtype_fits(data_type, kept["columns"][0]["numpy_type"]):
        raise ValueError("Column metadata names a dtype the column can't take")
    table = reader.read_all()
    # Checks every offset and dictionary index, so a crafted column can't make pandas read out of bounds
    table.validate(full=True)
    if rows is not None and table.num_rows != rows:
        raise ValueError("Column and index lengths differ")
    column = table.column(0)
    if isinstance(data_type, pa.BaseExtensionType):
        # to_pandas would build a dtype from the extension's own metadata, so the column metadata names it instead
        column = pa.chunked_array([chunk.storage for chunk in column.chunks], type=data_type.storage_type)
    table = pa.Table.from_arrays([column], names=table.column_names)
    if kept is not None:
        table = table.replace_schema_metadata({b"pandas": json.dumps(kept).encode()})
    return table.to_pandas(types_mapper=types_mapper).iloc[:, 0].array


def _as_index(values: Any, name: Any = None) -> pd.Index:
    # An explicit object dtype stops pandas from turning object datetimes into a DatetimeIndex
    return pd.Index(values, dtype=object if values.dtype == object else None, name=name, tupleize_cols=False)


def _index_from_plain(plain: Dict[str, Any]) -> pd.Index:
    names = _restore(plain["names"])
    if "range" in plain:
        start, stop, step = plain["range"]
        return pd.RangeIndex(start, stop, step, name=names[0])
    if "levels" in plain:
        levels = [_as_index(_column_from_plain(level)) for level in plain["levels"]]
        # pandas reports a repeated level value by printing the whole level
        if not all(level.is_unique for level in levels):
            raise ValueError("Index level values must be unique")
        codes = plain["codes"]
        # numpy would read text or bytes it was given as codes once per use, and text can repeat
        if type(codes) is not list or not all(type(level) is list and all(type(code) is int for code in level)
                                              for level in codes):
            raise ValueError("Index codes must be lists of integers")
        # verify_integrity bounds-checks the codes, which pandas otherwise indexes the levels with unchecked
        return pd.MultiIndex(levels=levels, codes=codes, names=names, verify_integrity=True)
    return _as_index(_column_from_plain(plain["values"], may_stay_in_arrow=True), name=names[0])


def _frame_from_plain(plain: Dict[str, Any]) -> Union[pd.DataFrame, pd.Series]:
    index = _index_from_plain(plain["index"])
    if not plain["data"] and "range" in plain["index"]:
        _spend(rows=len(index))  # a range index claims any number of rows for free
    columns = {}
    for position, column in enumerate(plain["data"]):
        values = _column_from_plain(column, rows=len(index), may_stay_in_arrow=True)
        # An explicit object dtype stops pandas from turning object datetimes into datetime64
        columns[position] = pd.Series(values, dtype=object if values.dtype == object else None, copy=False)
    if plain[_MARKER] == "series":
        result = columns[0]
        result.index = index
        result.name = _restore(plain["name"])
    else:
        result = pd.DataFrame(columns, index=pd.RangeIndex(len(index)), copy=False)
        result.index = index
        result.columns = _index_from_plain(plain["columns"])
    result.attrs = _restore(plain["attrs"])
    return result


def _restore_tz(offset: Any, name: Any) -> Any:
    if offset is None:
        return None
    delta = datetime.timedelta(microseconds=offset)
    return datetime.timezone(delta) if name is None else datetime.timezone(delta, name)


def _restore_value(value: tuple) -> Any:
    """A marked tuple, rebuilt through a constructor that checks every field"""
    kind, fields = value[1], value[2:]
    if kind == "datetime":
        *parts, fold, offset, name = fields
        return datetime.datetime(*parts, tzinfo=_restore_tz(offset, name), fold=fold)
    if kind == "date":
        return datetime.date(*fields)
    if kind == "time":
        *parts, fold, offset, name = fields
        return datetime.time(*parts, tzinfo=_restore_tz(offset, name), fold=fold)
    if kind == "timedelta":
        return datetime.timedelta(*fields)
    if kind == "decimal":
        if len(fields) != 1 or type(fields[0]) is not str:
            raise ValueError("A decimal must arrive as its text")
        _spend(len(fields[0]))
        with decimal.localcontext():  # Decimal signals on the current context, which the event loop shares
            return decimal.Decimal(fields[0])
    if kind == "complex":
        if not all(type(field) is float for field in fields):
            raise ValueError("A complex number must arrive as two floats")  # complex() would parse text
        return complex(*fields)
    if kind == "tuple":
        return tuple(_restore(item) for item in fields)
    raise ValueError("Unknown marked value")


def _restore(value: Any) -> Any:
    """Rebuild marked values and frames; the unpickled containers are new, so lists and dicts change in place"""
    kind = type(value)
    if kind is tuple:
        if value and value[0] == _MARKER:
            return _restore_value(value)
        return tuple(_restore(item) for item in value)
    if kind is list:
        for position, item in enumerate(value):
            value[position] = _restore(item)
        return value
    if kind is dict:
        if _MARKER in value:
            if value[_MARKER] == "dict":
                return {_restore(key): _restore(item) for key, item in value["items"]}
            return _frame_from_plain(value)
        if any(type(key) in (tuple, frozenset) for key in value):
            return {_restore(key): _restore(item) for key, item in value.items()}
        for key, item in value.items():
            value[key] = _restore(item)
        return value
    if kind in (set, frozenset):
        return kind(_restore(item) for item in value)
    return value


def _check_opcodes(data: bytes) -> None:
    """Refuse what the child's pickler never writes, before the C unpickler, which hashes keys and set members as it
    loads them, acts on it: other opcodes, a MEMOIZE that doesn't follow a new object, tuples nested too deeply, and
    repeats of anything but text and bytes. It follows the unpickler's stack, keeping how deeply each object nests
    tuples, or _TEXT"""
    sizes, flat, text, gets, pops, position = _ARGUMENT_SIZES, _FLAT_PUSHES, _TEXT_PUSHES, _GETS, _POPS, 0
    depths: List[int] = []
    marks: List[int] = []
    memo: List[bool] = []  # whether each memo entry holds text
    push = depths.append
    fresh = False  # whether the last opcode, FRAME aside, made a new object
    try:
        while (code := data[position]) != _STOP:
            size = sizes[code]
            if size is None:
                raise pickle.UnpicklingError(f"Script results can't contain pickle opcode {code:#04x}")
            position += 1
            if size < 0:
                size = int.from_bytes(data[position:position - size], "little") - size
            if code in flat:
                push(0)
                fresh = True
            elif code in text:
                push(_TEXT)
                fresh = True
            elif code == _MEMOIZE:
                if not fresh:
                    raise pickle.UnpicklingError("Script results can only memoize an object as it is made")
                memo.append(depths[-1] == _TEXT)
                fresh = False
            elif code in gets:
                if not memo[int.from_bytes(data[position:position + size], "little")]:
                    raise pickle.UnpicklingError("Script results can only repeat text and bytes")
                push(_TEXT)
                fresh = False
            elif code == _MARK:
                # Each open mark is a container being built, so they nest no deeper than tuples may
                if len(marks) >= _MAX_TUPLE_DEPTH:
                    raise pickle.UnpicklingError("Script result nests containers too deeply")
                marks.append(len(depths))
                fresh = False
            elif code in pops:
                count, builds_tuple = pops[code]
                start = marks.pop() if count is None else len(depths) - count
                if builds_tuple:
                    depth = max([0, *depths[start:]]) + 1
                    if depth > _MAX_TUPLE_DEPTH:
                        raise pickle.UnpicklingError("Script result nests tuples too deeply")
                    depths[start:] = [depth]
                else:
                    del depths[start:]
                fresh = builds_tuple
            position += size
    except IndexError:
        raise pickle.UnpicklingError("Script result is truncated or malformed") from None
    if position != len(data) - 1:
        raise pickle.UnpicklingError("Script result continues past its end")


def decode_result(data: bytes) -> Dict[str, Any]:
    """Unpickle a child's payload: plain data only, with frames rebuilt from validated Arrow columns"""
    _check_opcodes(data)
    payload = _ResultUnpickler(_WholeInput(data)).load()
    if not isinstance(payload, dict):
        raise pickle.UnpicklingError("Script result payload is not a dict")
    if any(type(key) is not str or (key != "result" and type(value) is not str) for key, value in payload.items()):
        raise pickle.UnpicklingError("Script result payload fields other than the result must be text")
    if "result" in payload and _MARKER.encode() in data:  # results without markers need no second pass
        token = _budget.set([len(data), _FREE_ROWS])
        try:
            payload["result"] = _restore(payload["result"])
        finally:
            _budget.reset(token)
    return payload
