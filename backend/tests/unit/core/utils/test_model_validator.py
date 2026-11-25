"""Security tests for static ML model pickle validation."""

import collections
import operator
import os
import pickle
import pty

import pytest

from app.core.utils import model_validator
from app.core.utils.model_validator import validate_pickle_file_safe
from tests.unit.core.utils.pickle_helpers import WriteFilePayload, call_global, pickle_unicode


@pytest.fixture(autouse=True)
def _ml_models_folder_is_tmp_path(monkeypatch, tmp_path):
    # Model files are only read from inside the ML models folder; these tests write them to tmp_path
    monkeypatch.setattr(model_validator, "ML_MODELS_DIR", os.path.realpath(tmp_path))


def _validate_bytes(tmp_path, data: bytes):
    pickle_file = tmp_path / "model.pkl"
    pickle_file.write_bytes(data)
    return validate_pickle_file_safe(str(pickle_file))


class TestAllowedPickles:
    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_allowed_global_is_resolved_across_protocols(self, tmp_path, protocol):
        is_valid, error = _validate_bytes(tmp_path, pickle.dumps(collections.OrderedDict, protocol=protocol))

        assert is_valid is True
        assert error is None

    def test_allowed_inst_reference_is_resolved(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, b"(icollections\nOrderedDict\n.")

        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize(
        "data",
        [
            b"c_codecs\nencode\n.",
            b"ccopy_reg\n_reconstructor\n.",
            b"c__builtin__\nobject\n.",
        ],
    )
    def test_legacy_global_alias_is_resolved(self, tmp_path, data):
        is_valid, error = _validate_bytes(tmp_path, data)

        assert is_valid is True
        assert error is None

    def test_primitive_payload_is_valid(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, pickle.dumps({"features": [1, 2, 3]}))

        assert is_valid is True
        assert error is None

    def test_lightgbm_best_score_shape_is_valid(self, tmp_path):
        payload = collections.defaultdict(
            collections.OrderedDict,
            {"valid_0": collections.OrderedDict(l2=0.5)},
        )

        is_valid, error = _validate_bytes(tmp_path, pickle.dumps(payload))

        assert is_valid is True
        assert error is None


class TestDisallowedPickles:
    @pytest.mark.parametrize("dangerous_global", [eval, exec, getattr, pty.spawn, operator.methodcaller])
    @pytest.mark.parametrize("protocol", [4, pickle.HIGHEST_PROTOCOL])
    def test_disallowed_global_is_rejected(self, tmp_path, dangerous_global, protocol):
        is_valid, error = _validate_bytes(tmp_path, pickle.dumps(dangerous_global, protocol=protocol))

        assert is_valid is False
        assert "Disallowed pickle global" in error
        assert dangerous_global.__name__ in error

    def test_disallowed_inst_reference_is_rejected(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, b"(ibuiltins\neval\n.")

        assert is_valid is False
        assert "Disallowed pickle global 'builtins.eval'" in error
        assert "INST" in error

    def test_memoized_stack_global_ignores_decoy_strings(self, tmp_path):
        data = (
            b"\x80\x04"
            + pickle_unicode("builtins")
            + b"\x94"
            + b"0"
            + pickle_unicode("eval")
            + b"\x94"
            + b"0"
            + pickle_unicode("sklearn")
            + b"\x94"
            + b"0"
            + pickle_unicode("Pipeline")
            + b"\x94"
            + b"0"
            + b"h\x00h\x01\x93."
        )

        is_valid, error = _validate_bytes(tmp_path, data)

        assert is_valid is False
        assert "Disallowed pickle global 'builtins.eval'" in error
        assert "STACK_GLOBAL" in error

    def test_validation_does_not_execute_reduce_payload(self, tmp_path):
        marker = tmp_path / "executed"

        is_valid, error = _validate_bytes(
            tmp_path,
            pickle.dumps(WriteFilePayload(marker), protocol=pickle.HIGHEST_PROTOCOL),
        )

        assert is_valid is False
        assert "Disallowed pickle global 'builtins.eval'" in error
        assert not marker.exists()

    @pytest.mark.parametrize(
        ("module", "name"),
        [
            ("sklearn", "os.system"),
            ("numpy", "testing._private.utils.runstring"),
            ("numpy.testing._private.utils", "runstring"),
            ("joblib", "load"),
            ("pandas", "read_pickle"),
        ],
    )
    def test_framework_gadget_is_rejected(self, tmp_path, module, name):
        is_valid, error = _validate_bytes(tmp_path, call_global(module, name))

        assert is_valid is False
        assert f"Disallowed pickle global '{module}.{name}'" in error

    def test_extension_registry_reference_is_rejected(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, b"\x80\x02\x82\x01.")

        assert is_valid is False
        assert "Unsupported pickle opcode EXT1" in error

    @pytest.mark.parametrize(
        "data",
        [
            b"Pexternal-id\n.",
            b"\x80\x05\x97.",
        ],
    )
    def test_external_pickle_reference_is_rejected(self, tmp_path, data):
        is_valid, error = _validate_bytes(tmp_path, data)

        assert is_valid is False
        assert "Unsupported pickle opcode" in error

    def test_unsupported_protocol_is_rejected(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, b"\x80\xffN.")

        assert is_valid is False
        assert "Unsupported pickle protocol" in error

    def test_unresolvable_stack_global_is_rejected(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, b"\x80\x04NN\x93.")

        assert is_valid is False
        assert "Unable to safely resolve STACK_GLOBAL" in error

    def test_control_characters_are_escaped_in_error(self, tmp_path):
        is_valid, error = _validate_bytes(tmp_path, b"cbad\x1b[31m\ncallable\n.")

        assert is_valid is False
        assert "\\x1b" in error
        assert "\x1b" not in error


class TestMalformedPickles:
    @pytest.mark.parametrize(
        "data",
        [
            b"",
            pickle.dumps({"valid": True})[:-1],
            b"\x80\x04\xff.",
            b"\x80\x04\x95\xff\xff\xff\xff\xff\xff\xff\xffN.",
            b"0.",
            b"\x80\x04h\x00.",
            b"cnumpy testing._private.utils\nrunstring\n.",
        ],
    )
    def test_malformed_pickle_is_rejected(self, tmp_path, data):
        is_valid, error = _validate_bytes(tmp_path, data)

        assert is_valid is False
        assert "Malformed pickle file" in error
