"""Security regression tests for the restricted ML-model unpickler.

These cover CWE-502 (insecure deserialization): the loader must reconstruct
benign ML artefacts while refusing pickles that reach for dangerous modules
via ``__reduce__``-based code-execution payloads.
"""

import io
import os
import pickle

import pytest

from app.core.utils.safe_pickle import RestrictedUnpickler, safe_pickle_load


class _EvilReduce:
    """Object whose unpickling would run ``os.system`` under stdlib pickle."""

    def __reduce__(self):
        return (os.system, ("echo pwned",))


class _EvilSubprocess:
    def __reduce__(self):
        import subprocess

        return (subprocess.call, (["echo", "pwned"],))


class _EvilEval:
    def __reduce__(self):
        return (eval, ("__import__('os').system('echo pwned')",))


class TestBenignPayloadsLoad:
    def test_primitive_container_roundtrips(self):
        payload = {"model": [1, 2, 3], "metadata": {"version": "v2.0"}, "flag": True}
        data = pickle.dumps(payload)
        assert safe_pickle_load(io.BytesIO(data)) == payload

    def test_nested_builtins_roundtrip(self):
        payload = {"a": (1, 2), "b": {"c": [None, "x", 3.5]}, "s": {1, 2, 3}}
        data = pickle.dumps(payload)
        assert safe_pickle_load(io.BytesIO(data)) == payload


class TestMaliciousPayloadsBlocked:
    @pytest.mark.parametrize("evil", [_EvilReduce, _EvilSubprocess, _EvilEval])
    def test_reduce_based_rce_is_blocked(self, evil):
        data = pickle.dumps(evil())
        with pytest.raises(pickle.UnpicklingError):
            safe_pickle_load(io.BytesIO(data))

    def test_os_system_global_is_blocked(self):
        # STACK_GLOBAL reference to os.system directly.
        data = pickle.dumps(os.system)
        with pytest.raises(pickle.UnpicklingError):
            safe_pickle_load(io.BytesIO(data))

    def test_unlisted_module_is_blocked(self):
        # A module that is neither explicitly blocked nor on the allowlist
        # must still be refused (allowlist, not blocklist, semantics).
        with pytest.raises(pickle.UnpicklingError):
            RestrictedUnpickler(io.BytesIO()).find_class("shutil", "rmtree")

    def test_pickle_module_itself_is_blocked(self):
        with pytest.raises(pickle.UnpicklingError):
            RestrictedUnpickler(io.BytesIO()).find_class("pickle", "loads")

    def test_no_side_effect_on_blocked_load(self, tmp_path):
        # Prove code execution never happens: the payload would create a file,
        # but loading must raise before __reduce__ runs.
        marker = tmp_path / "pwned"

        class _WriteFile:
            def __reduce__(self):
                return (os.system, (f"touch {marker}",))

        data = pickle.dumps(_WriteFile())
        with pytest.raises(pickle.UnpicklingError):
            safe_pickle_load(io.BytesIO(data))
        assert not marker.exists()


class TestBuiltinClassRestriction:
    def test_allowed_builtin_class(self):
        # dict is on the builtins allowlist.
        assert RestrictedUnpickler(io.BytesIO()).find_class("builtins", "dict") is dict

    def test_disallowed_builtin_class(self):
        # eval/exec/getattr are not on the builtins class allowlist.
        with pytest.raises(pickle.UnpicklingError):
            RestrictedUnpickler(io.BytesIO()).find_class("builtins", "eval")
