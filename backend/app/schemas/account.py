import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    account_type: AccountType
    currency: str = "RUB"


class AccountUpdate(BaseModel):
    """Partial update. Only name is safe to edit without breaking operation history.
    TODO: Allow account_type and currency edits with history-compatibility validation."""
    name: str | None = None


class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    account_type: AccountType
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
