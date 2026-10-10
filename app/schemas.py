"""Pydantic request and response schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RecipientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: object) -> object:
        """Trim names before length checks so whitespace-only names are rejected."""
        return value.strip() if isinstance(value, str) else value


class JobCreate(BaseModel):
    recipients: list[RecipientCreate] = Field(min_length=1)


class JobCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str


class JobProgress(BaseModel):
    id: int
    status: str
    total_recipients: int
    succeeded: int
    failed: int
    progress_percent: int


class RecipientResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    generation_status: str
    pdf_path: str | None
    failure_message: str | None
