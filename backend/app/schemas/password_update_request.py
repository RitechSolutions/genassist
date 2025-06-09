from pydantic import BaseModel

class PasswordUpdateRequest(BaseModel):
    username: str
    old_password: str
    new_password: str