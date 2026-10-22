"""Security regression tests for the restricted ML-model unpickler.

These cover CWE-502 (insecure deserialization): the loader must reconstruct
benign ML artefacts while refusing pickles that reach for dangerous modules
via ``__reduce__``-based code-execution payloads.
"""

import copyreg
import importlib
import io
import os
import pickle
import sys
import types
from collections import OrderedDict, defaultdict

import numpy as np
import pytest

from app.core.utils.safe_pickle import (
    BUILTINS_ONLY_ALLOWED_MODULES,
    RestrictedUnpickler,
    is_pickle_global_allowed,
    safe_pickle_load,
)
from tests.unit.core.utils.pickle_helpers import WriteFilePayload, call_global, call_runstring


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

    def test_lightgbm_best_score_shape_roundtrips(self):
        payload = defaultdict(OrderedDict, {"valid_0": OrderedDict(l2=0.5)})

        loaded = safe_pickle_load(io.BytesIO(pickle.dumps(payload)))

        assert loaded == payload
        assert loaded.default_factory is OrderedDict


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

    @pytest.mark.parametrize(
        ("module", "name"),
        [
            ("builtins", "type"),
            ("copy", "deepcopy"),
            ("functools", "partial"),
            ("sklearn", "os.system"),
            ("numpy", "load"),
            ("numpy", "testing._private.utils.runstring"),
            ("numpy.testing._private.utils", "runstring"),
            ("xgboost.core", "_load_lib"),
            ("joblib", "load"),
            ("pandas", "read_pickle"),
        ],
    )
    def test_framework_gadget_is_not_allowlisted(self, module, name):
        assert not is_pickle_global_allowed(module, name)

    def test_dotted_framework_global_does_not_execute(self, tmp_path):
        marker = tmp_path / "dotted-global-executed"
        data = call_global("sklearn", "os.system", f"touch {marker}")

        with pytest.raises(pickle.UnpicklingError, match="sklearn.os.system"):
            safe_pickle_load(io.BytesIO(data))

        assert not marker.exists()

    @pytest.mark.parametrize(
        ("module", "name"),
        [
            ("numpy", "testing._private.utils.runstring"),
            ("numpy.testing._private.utils", "runstring"),
        ],
    )
    def test_framework_code_runner_does_not_execute(self, tmp_path, module, name):
        marker = tmp_path / "runstring-executed"
        data = call_runstring(module, name, f"open({str(marker)!r}, 'w').close()")

        with pytest.raises(pickle.UnpicklingError):
            safe_pickle_load(io.BytesIO(data))

        assert not marker.exists()

    @pytest.mark.parametrize(("module", "name"), [("joblib", "load"), ("pandas", "read_pickle")])
    def test_nested_pickle_loader_does_not_execute(self, tmp_path, module, name):
        marker = tmp_path / f"{module}-executed"
        inner_pickle = tmp_path / "inner.pkl"
        inner_pickle.write_bytes(pickle.dumps(WriteFilePayload(marker), protocol=pickle.HIGHEST_PROTOCOL))
        data = call_global(module, name, str(inner_pickle))

        with pytest.raises(pickle.UnpicklingError, match=rf"{module}\.{name}"):
            safe_pickle_load(io.BytesIO(data))

        assert not marker.exists()


class TestBuiltinClassRestriction:
    def test_allowed_builtin_class(self):
        assert RestrictedUnpickler(io.BytesIO()).find_class("builtins", "bytearray") is bytearray

    @pytest.mark.parametrize("name", ["eval", "exec", "getattr"])
    def test_disallowed_builtin_class(self, name):
        with pytest.raises(pickle.UnpicklingError):
            RestrictedUnpickler(io.BytesIO()).find_class("builtins", name)

    @pytest.mark.parametrize(
        ("module", "name"),
        [("pty", "spawn"), ("operator", "methodcaller")],
    )
    def test_disallowed_stdlib_callable(self, module, name):
        assert not is_pickle_global_allowed(module, name)
        with pytest.raises(pickle.UnpicklingError):
            RestrictedUnpickler(io.BytesIO()).find_class(module, name)

    def test_exact_supported_framework_global_is_allowed(self):
        assert is_pickle_global_allowed("sklearn.ensemble._forest", "RandomForestRegressor")

    def test_legacy_module_aliases_resolve_to_safe_canonical_modules(self):
        unpickler = RestrictedUnpickler(io.BytesIO())

        assert unpickler.find_class("copy_reg", "_reconstructor") is copyreg._reconstructor
        assert unpickler.find_class("__builtin__", "object") is object

    def test_loss_alias_ignores_shadowed_top_level_module(self, monkeypatch):
        canonical_module = importlib.import_module("sklearn._loss._loss")
        shadow_module = types.ModuleType("_loss")
        shadow_module.CyHalfSquaredError = object
        monkeypatch.setitem(sys.modules, "_loss", shadow_module)

        resolved = RestrictedUnpickler(io.BytesIO()).find_class("_loss", "CyHalfSquaredError")

        assert resolved is canonical_module.CyHalfSquaredError

    def test_string_allowlist_value_is_rejected(self):
        with pytest.raises(TypeError, match="sets of exact global names"):
            RestrictedUnpickler(io.BytesIO(), allowed_modules={"builtins": "*"})

    @pytest.mark.parametrize("name", ["system", "os.system"])
    def test_unlisted_or_dotted_framework_global_is_blocked(self, name):
        assert not is_pickle_global_allowed("sklearn", name)

    @pytest.mark.parametrize(
        ("module", "name"),
        [("builtins", "float"), ("numpy", "int8"), ("numpy", "bool_"), ("numpy.core._multiarray_umath", "log1p")],
    )
    def test_plain_type_and_numpy_1_ufunc_globals_are_allowed(self, module, name):
        assert is_pickle_global_allowed(module, name)

    def test_builtins_type_is_not_allowlisted(self):
        assert not is_pickle_global_allowed("builtins", "type")


class TestBuildTargetRestriction:
    """BUILD must never mutate the process-wide objects find_class hands out."""

    def test_build_on_class_is_blocked(self):
        payload = b"csklearn.pipeline\nPipeline\n(dS'x'\nI1\nsb."

        with pytest.raises(pickle.UnpicklingError, match="BUILD cannot target"):
            safe_pickle_load(io.BytesIO(payload))

    def test_build_on_allowlisted_function_is_blocked(self):
        from sklearn.metrics import r2_score

        # Slot state: setattr(r2_score, "__kwdefaults__", None) under a plain unpickler.
        payload = b"csklearn.metrics._regression\nr2_score\n(N(dS'__kwdefaults__'\nNstb."
        original_kwdefaults = r2_score.__kwdefaults__

        with pytest.raises(pickle.UnpicklingError, match="BUILD cannot target"):
            safe_pickle_load(io.BytesIO(payload))

        assert r2_score.__kwdefaults__ == original_kwdefaults

    def test_build_on_allowlisted_function_dict_state_is_blocked(self):
        from sklearn.metrics import accuracy_score

        payload = b"csklearn.metrics._classification\naccuracy_score\n(dS'tampered'\nI1\nsb."

        with pytest.raises(pickle.UnpicklingError, match="BUILD cannot target"):
            safe_pickle_load(io.BytesIO(payload))

        assert not hasattr(accuracy_score, "tampered")

    def test_build_on_reconstructed_instance_is_allowed(self):
        loaded = safe_pickle_load(io.BytesIO(pickle.dumps(OrderedDict(a=1))))

        assert loaded == OrderedDict(a=1)


class TestBuiltinsOnlyAllowlist:
    def test_plain_data_roundtrips(self):
        payload = {
            "id_map": {0: "a", 1: "b"},
            "metadata_map": {"a": {"chunk_index": 0, "flag": True}},
            "next_id": 2,
            "dimension": None,
        }
        data = pickle.dumps(payload)
        assert safe_pickle_load(io.BytesIO(data), allowed_modules=BUILTINS_ONLY_ALLOWED_MODULES) == payload

    def test_numpy_scalar_blocked_but_allowed_by_default(self):
        data = pickle.dumps(np.int64(3))
        with pytest.raises(pickle.UnpicklingError):
            safe_pickle_load(io.BytesIO(data), allowed_modules=BUILTINS_ONLY_ALLOWED_MODULES)
        assert safe_pickle_load(io.BytesIO(data)) == 3

    def test_reduce_payload_is_blocked_without_side_effect(self, tmp_path):
        marker = tmp_path / "pwned"

        class _WriteFile:
            def __reduce__(self):
                return (eval, (f"__import__('os').system('touch {marker}')",))

        with pytest.raises(pickle.UnpicklingError):
            safe_pickle_load(io.BytesIO(pickle.dumps(_WriteFile())), allowed_modules=BUILTINS_ONLY_ALLOWED_MODULES)
        assert not marker.exists()
