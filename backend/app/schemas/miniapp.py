import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.operation import OperationCreate


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    text: str = Field(default="", max_length=2000)
    audio: str | None = Field(default=None, max_length=6_700_000)

    @model_validator(mode="after")
    def one_input(self):
        if bool(self.text.strip()) == bool(self.audio):
            raise ValueError("Укажите текст или голосовую запись")
        return self


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    operation: OperationCreate


class DraftDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    action: Literal["confirm", "cancel"]


class MiniAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    account_type: Literal["cash", "bank", "broker", "savings", "other"] = "cash"
