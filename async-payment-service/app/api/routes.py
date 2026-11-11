import hashlib, json, uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.auth import require_api_key
from app.db.session import get_session
from app.models.payment import Payment
from app.models.outbox import Outbox
from app.schemas.payment import PaymentCreate, PaymentAccepted, PaymentRead
router = APIRouter(prefix="/api/v1/payments", tags=["payments"])
def request_hash(payload: PaymentCreate) -> str:
    body = payload.model_dump(mode="json")
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
@router.post("", response_model=PaymentAccepted, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
async def create_payment(payload: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    session: AsyncSession = Depends(get_session)):
    digest = request_hash(payload)
    existing = await session.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(409, "Idempotency-Key was already used with a different request")
        return PaymentAccepted(payment_id=existing.id, status=existing.status, created_at=existing.created_at)
    payment = Payment(amount=payload.amount, currency=payload.currency, description=payload.description,
        metadata_json=payload.metadata, status="pending", idempotency_key=idempotency_key,
        request_hash=digest, webhook_url=str(payload.webhook_url))
    session.add(payment)
    try:
        await session.flush()
        session.add(Outbox(payment_id=payment.id, event_type="payment.created",
            payload={"payment_id": str(payment.id), "attempt": 0}))
        await session.commit()
        await session.refresh(payment)
    except Exception:
        await session.rollback()
        existing = await session.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
        if existing and existing.request_hash == digest:
            return PaymentAccepted(payment_id=existing.id, status=existing.status, created_at=existing.created_at)
        if existing:
            raise HTTPException(409, "Idempotency-Key conflict")
        raise
    return PaymentAccepted(payment_id=payment.id, status=payment.status, created_at=payment.created_at)
@router.get("/{payment_id}", response_model=PaymentRead, dependencies=[Depends(require_api_key)])
async def get_payment(payment_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "Payment not found")
    return PaymentRead.model_validate(payment)
