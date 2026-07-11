"""Pydantic schemas — Auth (login, register, tokens)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    org_name: str = Field(..., min_length=1, max_length=255)
    org_slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    org_id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
