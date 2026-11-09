"""Script results travel from the sandbox child to the backend as plain data that unpickles without globals.

The child runs user code, so any global the backend's unpickler resolved could be made to run code there.
"""

import collections
import datetime
import decimal
import fractions
import io
import pickle
import uuid
from typing import Any, Dict, Iterator, List, Union

import numpy as np
import pandas as pd

_PLAIN_TYPES = (type(None), bool, int, float, str, bytes, bytearray)
# Returned as text, the way workflow state shows them
_TEXT_TYPES = (uuid.UUID, pd.Period, pd.Interval, pd.offsets.BaseOffset, np.dtype, pd.api.extensions.ExtensionDtype)
# Heads tuples for values the parent rebuilds through a constructor, and keys dicts that hold frames
_MARKER = "__genassist__"


# Not safe_pickle's RestrictedUnpickler: that one is pure Python, and results can run to many MiB
class _ResultUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"Script results can't contain {module}.{name}")


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
    table = pa.Table.from_pandas(frame, preserve_index=False)
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
    if isinstance(original, pd.CategoricalDtype):
        return (
            isinstance(decoded, pd.CategoricalDtype) and decoded.ordered == original.ordered
            and _same_dtype(decoded.categories.dtype, original.categories.dtype)
            and decoded.categories.equals(original.categories)
        )
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

    if column.dtype != object:
        try:
            spec: Any = _arrow_column(column)
            mapper = _arrow_mapper(column.dtype)
            if mapper:
                spec = {"arrow": spec, "mapper": mapper}
            # Some columns don't survive Arrow unchanged, e.g. pd.cut's intervals or timezone categories
            if _same_dtype(pd.Series(_column_from_plain(spec), copy=False).dtype, column.dtype):
                return spec
        except Exception:
            pass  # e.g. complex numbers, which Arrow has no type for
    if isinstance(column.dtype, pd.CategoricalDtype):
        # Codes plus plain categories, since one plain value per row can be many times larger
        categories = to_plain(list(column.cat.categories))
        try:
            unique = _stays_unique(categories)
        except TypeError:  # a category whose plain form is a list
            unique = False
        if unique:
            codes = _column_to_plain(pd.Series(column.cat.codes))
            return {"codes": codes, "categories": categories, "ordered": bool(column.cat.ordered)}
    return to_plain(column.tolist())


def _index_to_plain(index: pd.Index) -> Dict[str, Any]:
    names = to_plain(list(index.names))
    if isinstance(index, pd.RangeIndex):
        return {"range": [index.start, index.stop, index.step], "names": names}
    if isinstance(index, pd.MultiIndex):
        levels = []
        for level in index.levels:
            plain_level = _column_to_plain(pd.Series(level, dtype=level.dtype))
            if isinstance(plain_level, list) and not _stays_unique(plain_level):
                raise TypeError("Two index level values become equal when returned, e.g. times in nanoseconds")
            levels.append(plain_level)
        return {"levels": levels, "codes": [codes.tolist() for codes in index.codes], "names": names}
    return {"values": _column_to_plain(pd.Series(index, dtype=index.dtype)), "names": names}


def _frame_to_plain(value: Union[pd.DataFrame, pd.Series]) -> Dict[str, Any]:
    """DataFrames and Series travel column by column, so the parent never unpickles pandas internals"""
    is_series = isinstance(value, pd.Series)
    frame = value.to_frame() if is_series else value
    return {
        _MARKER: "series" if is_series else "frame",
        "name": to_plain(value.name) if is_series else None,
        "attrs": to_plain(dict(value.attrs)),
        "data": [_column_to_plain(frame.iloc[:, position]) for position in range(frame.shape[1])],
        "index": _index_to_plain(frame.index),
        "columns": _index_to_plain(frame.columns),
    }


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


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


def _column_from_plain(column: Any) -> Any:
    """A column the child sent, as an array that keeps its dtype"""
    if type(column) is dict and "codes" in column:
        codes = np.asarray(_column_from_plain(column["codes"]))
        categories = _as_index(_column_from_plain(column["categories"]))
        # from_codes checks every code against the categories
        return pd.Categorical.from_codes(codes, categories=categories, ordered=column["ordered"] is True)
    if type(column) is dict:
        return _arrow_values(column["arrow"], column["mapper"])
    if type(column) is list:
        values = np.empty(len(column), dtype=object)
        if any(type(item) in (dict, list, tuple, set, frozenset) for item in column):
            for position, item in enumerate(column):
                values[position] = _restore(item)
        else:
            values[:] = column
        return values
    return _arrow_values(column, None)


def _arrow_values(data: Any, mapper: Any) -> Any:
    if type(data) is not bytes:  # pyarrow would open a str as a file path
        raise ValueError("Column data must be bytes or a list")
    import pyarrow as pa

    table = pa.ipc.open_stream(data).read_all()
    # Checks every offset and dictionary index, so a crafted column can't make pandas read out of bounds
    table.validate(full=True)
    timezones = (tz for field in table.schema for tz in _arrow_timezones(field.type))
    if any("dateutil" in name for name in (*_strings(table.schema.pandas_metadata), *timezones)):
        raise ValueError("Column timezone names a dateutil file")  # pandas would open the file
    if mapper is None:
        types_mapper = None
    elif mapper == "arrow":
        types_mapper = pd.ArrowDtype
    elif mapper == "pyarrow_string":
        types_mapper = {pa.string(): pd.StringDtype("pyarrow"), pa.large_string(): pd.StringDtype("pyarrow")}.get
    else:
        raise ValueError("Unknown column mapper")
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
        # verify_integrity bounds-checks the codes, which pandas otherwise indexes the levels with unchecked
        return pd.MultiIndex(levels=levels, codes=plain["codes"], names=names, verify_integrity=True)
    return _as_index(_column_from_plain(plain["values"]), name=names[0])


def _frame_from_plain(plain: Dict[str, Any]) -> Union[pd.DataFrame, pd.Series]:
    index = _index_from_plain(plain["index"])
    columns = {}
    for position, column in enumerate(plain["data"]):
        values = _column_from_plain(column)
        if len(values) != len(index):
            raise ValueError("Column and index lengths differ")
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
        with decimal.localcontext():  # Decimal signals on the current context, which the event loop shares
            return decimal.Decimal(*fields)
    if kind == "complex":
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


def decode_result(data: bytes) -> Dict[str, Any]:
    """Unpickle a child's payload: plain data only, with frames rebuilt from validated Arrow columns"""
    payload = _ResultUnpickler(io.BytesIO(data)).load()
    if not isinstance(payload, dict):
        raise pickle.UnpicklingError("Script result payload is not a dict")
    if "result" in payload and _MARKER.encode() in data:  # results without markers need no second pass
        payload["result"] = _restore(payload["result"])
    return payload
