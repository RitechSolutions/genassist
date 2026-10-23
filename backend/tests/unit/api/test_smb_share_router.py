"""Unit tests for the SMB share router: local mode never falls back to the working directory, and every route checks a permission"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import smb_share_router as smb
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.services.smb_share_service import SMBShareFSService


@pytest.mark.parametrize("local_root", [None, ""])
def test_local_mode_requires_a_local_root(local_root):
    with pytest.raises(HTTPException) as exc:
        smb._validate_local_root(local_root, use_local_fs=True)
    assert exc.value.status_code == 400


def test_smb_mode_does_not_need_a_local_root():
    assert smb._validate_local_root(None, use_local_fs=False) is None


@pytest.mark.asyncio
async def test_reading_without_a_local_root_does_not_reach_backend_files():
    with pytest.raises(HTTPException) as exc:
        await smb.read_file(smb.FileRequest(use_local_fs=True, filepath=".env"))
    assert exc.value.status_code == 400


def test_service_never_falls_back_to_the_working_directory(monkeypatch):
    monkeypatch.delenv("LOCAL_ROOT", raising=False)
    with pytest.raises(ValueError):
        SMBShareFSService(use_local_fs=True)


def test_service_still_uses_the_local_root_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_ROOT", str(tmp_path))
    assert SMBShareFSService(use_local_fs=True).local_root == tmp_path


def _request(perms):
    return SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(permissions=perms)))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,needed",
    [
        ("POST", "/smb/list", P.DataSource.READ),
        ("POST", "/smb/read", P.DataSource.READ),
        ("POST", "/smb/exists", P.DataSource.READ),
        ("POST", "/smb/write", P.DataSource.UPDATE),
        ("POST", "/smb/folder", P.DataSource.UPDATE),
        ("DELETE", "/smb/file", P.DataSource.DELETE),
        ("DELETE", "/smb/folder", P.DataSource.DELETE),
        ("GET", "/smb/execute-celery-jobs", P.DataSource.UPDATE),
    ],
)
async def test_every_route_requires_auth_and_a_permission(method, path, needed):
    route = next(r for r in smb.router.routes if r.path == path and method in r.methods)
    calls = [dep.call for dep in route.dependant.dependencies]
    assert smb.auth in calls
    checks = [call for call in calls if call is not smb.auth]

    for check in checks:
        await check(_request([needed]))

    denied = 0
    for check in checks:
        try:
            await check(_request([]))
        except AppException:
            denied += 1
    assert denied == 1
