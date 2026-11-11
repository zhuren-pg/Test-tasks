import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
Currency = Literal["RUB", "USD", "EUR"]
Status = Literal["pending", "succeeded", "failed"]
class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl
class PaymentAccepted(BaseModel):
    payment_id: uuid.UUID
    status: Status
    created_at: datetime
class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID = Field(serialization_alias="payment_id")
    amount: Decimal
    currency: str
    description: str
    metadata_json: dict[str, Any] = Field(serialization_alias="metadata")
    status: Status
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
