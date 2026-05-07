"""Auth request / response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh: str


class LogoutRequest(BaseModel):
    refresh: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    title_provider_model_id: str | None = None


class UpdateMeRequest(BaseModel):
    """Partial-update payload for `PATCH /auth/me`."""

    display_name: str | None = Field(default=None, max_length=120)
    title_provider_model_id: str | None = None


class TokenPair(BaseModel):
    access: str
    refresh: str
    access_expires_at: datetime
    user: UserOut
