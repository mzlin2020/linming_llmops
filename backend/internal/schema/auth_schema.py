import re
from typing import Optional

from pydantic import BaseModel, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(v: str) -> str:
    return (v or "").strip().lower()


class RegisterReq(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = normalize_email(v)
        if not _EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v


class LoginReq(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class RefreshReq(BaseModel):
    refresh_token: str
