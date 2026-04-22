from typing import Optional
from pydantic import BaseModel


class AzureExistsResponse(BaseModel):
    exists: bool


class AzureUploadResponse(BaseModel):
    status: str
    url: str


class AzureDeleteResponse(BaseModel):
    status: str
    deleted: bool


class AzureConnection(BaseModel):
    connection_string: Optional[str] = None
    container: Optional[str] = None


class AzureListRequest(AzureConnection):
    prefix: Optional[str] = None


class AzureFileRequest(AzureConnection):
    filename: str
    prefix: Optional[str] = None
    overwrite: Optional[bool] = True
    content: Optional[str] = None
    binary: Optional[bool] = False


class AzureMoveRequest(AzureConnection):
    source_name: str
    destination_name: str
    source_prefix: Optional[str] = None
    destination_prefix: Optional[str] = None