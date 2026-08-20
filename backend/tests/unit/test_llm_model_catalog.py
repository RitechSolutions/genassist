"""Unit tests for the tenant LLM model catalog.

The catalog is an *overlay*: it may only ever add options to the built-in lists in
``LLM_FORM_SCHEMAS``. These tests pin that contract, above all that an empty
catalog leaves the provider form schemas byte-identical to what ships in code.
"""

import copy
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.modules.workflow.llm.provider as provider_module
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_model_catalog import LlmModelCatalogModel
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.schemas.llm_model_catalog import LlmModelCatalogCreate, LlmModelCatalogUpdate
from app.services.llm_model_catalog import LlmModelCatalogService


class FakeCatalogRepo:
    def __init__(self, active=None, in_use=None, existing_by_pm=None, existing_by_id=None):
        self._active = active or []
        self._in_use = in_use or []
        self._by_pm = existing_by_pm
        self._by_id = existing_by_id

    async def list_all(self):
        return self._active

    async def list_active(self):
        return [r for r in self._active if r.is_active == 1]

    async def list_models_in_use(self):
        return self._in_use

    async def get_by_provider_model(self, provider_key, model_key):
        return self._by_pm

    async def get_active_by_id(self, entry_id):
        return self._by_id

    async def soft_delete_by_id(self, entry_id):
        # Mirrors the real repository: only an existing, not-yet-deleted row is removed.
        if self._by_id is None or self._by_id.id != entry_id:
            return False
        self._by_id.is_deleted = 1
        return True

    async def create(self, obj):
        obj.id = uuid4()
        return obj

    async def update(self, obj):
        return obj


def _entry(provider_key, model_key, label, is_active=1):
    row = LlmModelCatalogModel(
        provider_key=provider_key,
        model_key=model_key,
        label=label,
        is_active=is_active,
    )
    row.id = uuid4()
    return row


def _model_options(schemas, provider_key):
    for field in schemas[provider_key]["fields"]:
        if field["name"] == "model":
            return [opt["value"] for opt in (field.get("options") or [])]
    return None


@pytest.fixture(autouse=True)
def _configure_mappers(app_def):
    return app_def


# ───────────── create / update validation ─────────────


@pytest.mark.asyncio
async def test_create_rejects_unknown_provider():
    service = LlmModelCatalogService(FakeCatalogRepo())
    with pytest.raises(AppException) as exc:
        await service.create_entry(
            LlmModelCatalogCreate(provider_key="not_a_provider", model_key="x", label="X")
        )
    assert exc.value.status_code == 400
    assert exc.value.error_key is ErrorKey.LLM_CATALOG_UNKNOWN_PROVIDER


@pytest.mark.asyncio
async def test_create_rejects_provider_without_a_model_field():
    # azure_openai selects a deployment, not a model, so there is nothing to extend
    service = LlmModelCatalogService(FakeCatalogRepo())
    with pytest.raises(AppException) as exc:
        await service.create_entry(
            LlmModelCatalogCreate(provider_key="azure_openai", model_key="x", label="X")
        )
    assert exc.value.status_code == 400
    assert exc.value.error_key is ErrorKey.LLM_CATALOG_PROVIDER_HAS_NO_MODEL_FIELD


@pytest.mark.asyncio
async def test_create_duplicate_raises_409():
    existing = _entry("groq", "llama-3.3-70b-versatile", "Llama 3.3 70B")
    service = LlmModelCatalogService(FakeCatalogRepo(existing_by_pm=existing))
    with pytest.raises(AppException) as exc:
        await service.create_entry(
            LlmModelCatalogCreate(
                provider_key="groq", model_key="llama-3.3-70b-versatile", label="Llama 3.3 70B"
            )
        )
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_CATALOG_MODEL_ALREADY_EXISTS


@pytest.mark.asyncio
async def test_create_normalizes_provider_and_keeps_model_case():
    service = LlmModelCatalogService(FakeCatalogRepo())
    read = await service.create_entry(
        LlmModelCatalogCreate(
            provider_key="  GROQ ", model_key="  Llama-3.3-70B  ", label="  Llama 3.3 70B  "
        )
    )
    assert read.provider_key == "groq"
    assert read.model_key == "Llama-3.3-70B"
    assert read.label == "Llama 3.3 70B"
    assert read.is_shadowed_by_builtin is False


@pytest.mark.asyncio
async def test_entry_matching_a_builtin_is_flagged_as_shadowed():
    service = LlmModelCatalogService(FakeCatalogRepo())
    read = await service.create_entry(
        LlmModelCatalogCreate(provider_key="groq", model_key="llama2-70b-4096", label="Renamed")
    )
    assert read.is_shadowed_by_builtin is True


@pytest.mark.asyncio
async def test_update_missing_entry_returns_none():
    service = LlmModelCatalogService(FakeCatalogRepo(existing_by_id=None))
    assert await service.update_entry(uuid4(), LlmModelCatalogUpdate(label="X")) is None


@pytest.mark.asyncio
async def test_update_only_touches_the_fields_that_were_sent():
    row = _entry("groq", "custom-model", "Old label", is_active=1)
    service = LlmModelCatalogService(FakeCatalogRepo(existing_by_id=row))

    read = await service.update_entry(row.id, LlmModelCatalogUpdate(label="  New label  "))

    assert read.label == "New label"
    assert read.is_active == 1  # untouched by a label-only update
    assert read.model_key == "custom-model"


@pytest.mark.asyncio
async def test_update_can_hide_an_entry_without_deleting_it():
    row = _entry("groq", "custom-model", "Custom", is_active=1)
    service = LlmModelCatalogService(FakeCatalogRepo(existing_by_id=row))

    read = await service.update_entry(row.id, LlmModelCatalogUpdate(is_active=0))

    assert read.is_active == 0
    assert read.label == "Custom"


@pytest.mark.asyncio
async def test_delete_reports_whether_a_row_was_removed():
    present = _entry("groq", "custom-model", "Custom")
    assert await LlmModelCatalogService(FakeCatalogRepo(existing_by_id=present)).delete_entry(
        present.id
    ) is True
    assert await LlmModelCatalogService(FakeCatalogRepo(existing_by_id=None)).delete_entry(
        uuid4()
    ) is False


@pytest.mark.asyncio
async def test_list_entries_flags_only_the_rows_a_builtin_shadows():
    repo = FakeCatalogRepo(
        active=[
            _entry("groq", "llama2-70b-4096", "Shadowed by a built-in"),
            _entry("groq", "llama-3.3-70b-versatile", "Genuinely new"),
        ]
    )
    by_model = {r.model_key: r for r in await LlmModelCatalogService(repo).list_entries()}
    assert by_model["llama2-70b-4096"].is_shadowed_by_builtin is True
    assert by_model["llama-3.3-70b-versatile"].is_shadowed_by_builtin is False


# ───────────── payload validation ─────────────


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
@pytest.mark.parametrize("field", ["provider_key", "model_key", "label"])
def test_create_payload_rejects_blank_identifiers(field, blank):
    payload = {"provider_key": "groq", "model_key": "m", "label": "M", field: blank}
    with pytest.raises(ValidationError):
        LlmModelCatalogCreate(**payload)


@pytest.mark.parametrize("bad_flag", [-1, 2])
def test_create_payload_rejects_an_out_of_range_active_flag(bad_flag):
    with pytest.raises(ValidationError):
        LlmModelCatalogCreate(
            provider_key="groq", model_key="m", label="M", is_active=bad_flag
        )


def test_create_payload_defaults_to_active():
    assert LlmModelCatalogCreate(provider_key="groq", model_key="m", label="M").is_active == 1


def test_update_payload_defaults_to_touching_nothing():
    dto = LlmModelCatalogUpdate()
    assert dto.label is None and dto.is_active is None


def test_list_providers_only_includes_types_with_a_model_field():
    service = LlmModelCatalogService(FakeCatalogRepo())
    keys = {p.provider_key for p in service.list_providers()}
    assert "groq" in keys
    assert "azure_openai" not in keys
    groq = next(p for p in service.list_providers() if p.provider_key == "groq")
    assert "llama2-70b-4096" in groq.builtin_model_keys


# ───────────── overlay construction ─────────────


@pytest.mark.asyncio
async def test_overlay_skips_inactive_rows():
    repo = FakeCatalogRepo(
        active=[
            _entry("groq", "active-model", "Active"),
            _entry("groq", "hidden-model", "Hidden", is_active=0),
        ]
    )
    overlay = await LlmModelCatalogService(repo).build_option_overlay()
    assert [o["value"] for o in overlay["groq"]] == ["active-model"]


@pytest.mark.asyncio
async def test_overlay_re_adds_a_model_a_provider_is_already_using():
    """A configured provider must keep showing its own model in the edit form."""
    repo = FakeCatalogRepo(in_use=[("groq", "retired-model")])
    overlay = await LlmModelCatalogService(repo).build_option_overlay()
    assert overlay["groq"] == [{"value": "retired-model", "label": "retired-model"}]


@pytest.mark.asyncio
async def test_overlay_ignores_in_use_models_that_are_already_builtin():
    repo = FakeCatalogRepo(in_use=[("groq", "llama2-70b-4096")])
    overlay = await LlmModelCatalogService(repo).build_option_overlay()
    assert "groq" not in overlay


@pytest.mark.asyncio
async def test_overlay_leaves_free_text_and_replaced_option_lists_alone():
    # vllm's model field is free text; vllm_fine_tuned's options are replaced with
    # the deployments that are currently running, so a stale value must not return.
    repo = FakeCatalogRepo(
        in_use=[("vllm", "./outputs/merged"), ("vllm_fine_tuned", "http://x:::/model")]
    )
    overlay = await LlmModelCatalogService(repo).build_option_overlay()
    assert overlay == {}


# ───────────── merge into the provider form schemas ─────────────


@pytest.mark.asyncio
async def test_empty_catalog_leaves_the_builtin_schemas_untouched(monkeypatch):
    class EmptyService:
        async def build_option_overlay(self):
            return {}

    import app.dependencies.injector as injector_module

    monkeypatch.setattr(
        injector_module, "injector", type("I", (), {"get": lambda self, cls: EmptyService()})()
    )

    baseline = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
    schemas = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
    await provider_module._apply_model_catalog(schemas)
    assert schemas == baseline


@pytest.mark.asyncio
async def test_overlay_is_appended_and_builtins_win_on_collision(monkeypatch):
    class OverlayService:
        async def build_option_overlay(self):
            return {
                "groq": [
                    {"value": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B Versatile"},
                    {"value": "llama2-70b-4096", "label": "Renamed built-in"},
                ],
                "no_such_provider": [{"value": "x", "label": "X"}],
            }

    import app.dependencies.injector as injector_module

    monkeypatch.setattr(
        injector_module, "injector", type("I", (), {"get": lambda self, cls: OverlayService()})()
    )

    baseline = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
    schemas = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
    await provider_module._apply_model_catalog(schemas)

    groq_options = _model_options(schemas, "groq")
    # built-ins keep their position and their label, the new model is appended once
    assert groq_options == _model_options(baseline, "groq") + ["llama-3.3-70b-versatile"]
    labels = {
        opt["value"]: opt["label"]
        for field in schemas["groq"]["fields"]
        if field["name"] == "model"
        for opt in field["options"]
    }
    assert labels["llama2-70b-4096"] == "Llama 2 70B"
    assert "no_such_provider" not in schemas

    # nothing else moved
    untouched = {k for k in baseline if k != "groq"}
    assert all(_model_options(schemas, k) == _model_options(baseline, k) for k in untouched)


@pytest.mark.asyncio
async def test_a_broken_catalog_never_breaks_the_provider_form(monkeypatch):
    class BoomService:
        async def build_option_overlay(self):
            raise RuntimeError("database is down")

    import app.dependencies.injector as injector_module

    monkeypatch.setattr(
        injector_module, "injector", type("I", (), {"get": lambda self, cls: BoomService()})()
    )

    baseline = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
    schemas = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
    await provider_module._apply_model_catalog(schemas)
    assert schemas == baseline
