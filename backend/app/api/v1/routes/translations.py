from typing import List

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.translation import (
    LanguageCreate,
    LanguageRead,
    TranslationCreate,
    TranslationRead,
    TranslationUpdate,
)
from app.services.translations import LanguagesService, TranslationsService


router = APIRouter()


# --- Language endpoints ---


@router.get(
    "/languages",
    response_model=List[LanguageRead],
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.READ))],
)
async def list_languages(
    svc: LanguagesService = Injected(LanguagesService),
):
    return await svc.get_all()


@router.post(
    "/languages",
    response_model=LanguageRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.CREATE))],
)
async def create_language(
    dto: LanguageCreate,
    svc: LanguagesService = Injected(LanguagesService),
):
    return await svc.create(dto)


# --- Translation endpoints ---


@router.get(
    "",
    response_model=List[TranslationRead],
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.READ))],
)
async def list_translations(
    svc: TranslationsService = Injected(TranslationsService),
):
    return await svc.get_all()


@router.get(
    "/{key}",
    response_model=TranslationRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.READ))],
)
async def get_translation(
    key: str,
    svc: TranslationsService = Injected(TranslationsService),
):
    return await svc.get_by_key(key)


@router.post(
    "",
    response_model=TranslationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.CREATE))],
)
async def create_translation(
    dto: TranslationCreate,
    svc: TranslationsService = Injected(TranslationsService),
):
    return await svc.create(dto)


@router.patch(
    "/{key}",
    response_model=TranslationRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.UPDATE))],
)
async def update_translation(
    key: str,
    dto: TranslationUpdate,
    svc: TranslationsService = Injected(TranslationsService),
):
    return await svc.update(key, dto)


@router.delete(
    "/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.DELETE))],
)
async def delete_translation(
    key: str,
    svc: TranslationsService = Injected(TranslationsService),
):
    await svc.delete(key)
