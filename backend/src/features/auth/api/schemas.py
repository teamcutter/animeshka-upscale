from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from src.features.auth.domain import User

# Deliberately loose: the real check is that the user can log in with it.
Email = Annotated[str, Field(max_length=254, pattern=r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$")]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: Email
    password: Password
    name: Annotated[str, Field(min_length=1, max_length=64)]


class LoginRequest(BaseModel):
    email: Email
    password: Annotated[str, Field(max_length=128)]


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, name=user.name, created_at=user.created_at)
