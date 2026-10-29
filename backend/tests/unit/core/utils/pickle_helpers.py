import struct


class WriteFilePayload:
    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return (eval, (f"__import__('pathlib').Path({str(self.marker)!r}).touch()",))


def pickle_unicode(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) <= 255:
        return b"\x8c" + bytes([len(encoded)]) + encoded
    return b"X" + struct.pack("<I", len(encoded)) + encoded


def call_global(module: str, name: str, *string_args: str) -> bytes:
    return (
        b"\x80\x04"
        + pickle_unicode(module)
        + pickle_unicode(name)
        + b"\x93("
        + b"".join(pickle_unicode(arg) for arg in string_args)
        + b"tR."
    )


def call_runstring(module: str, name: str, code: str) -> bytes:
    return (
        b"\x80\x04"
        + pickle_unicode(module)
        + pickle_unicode(name)
        + b"\x93"
        + pickle_unicode(code)
        + b"}\x86R."
    )
