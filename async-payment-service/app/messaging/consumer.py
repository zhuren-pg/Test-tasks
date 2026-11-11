import logging, uuid
from datetime import datetime, timezone
from faststream import FastStream
from faststream.rabbit import RabbitMessage
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.payment import Payment
from app.messaging.topology import broker, MAIN_QUEUE, MAIN_EXCHANGE, RETRY_EXCHANGE, DLQ_EXCHANGE, declare_topology
from app.services.gateway import FakePaymentGateway
from app.services.webhook import send_webhook
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastStream(broker)
gateway = FakePaymentGateway()
@app.after_startup
async def startup():
    await declare_topology()
async def retry_or_dlq(event: dict, attempt: int, error: Exception):
    # attempt=0 is the first processing attempt. Total attempts = 3:
    # after failures #1 and #2 schedule retries; after failure #3 send to DLQ.
    if attempt < 3:
        route = {1: "2s", 2: "4s"}[attempt]
        await broker.publish({**event, "attempt": attempt}, exchange=RETRY_EXCHANGE, routing_key=route, persist=True)
    else:
        await broker.publish({**event, "last_error": str(error)[:1000]}, exchange=DLQ_EXCHANGE, routing_key="dead", persist=True)
@broker.subscriber(MAIN_QUEUE, exchange=MAIN_EXCHANGE)
async def process_payment(event: dict, message: RabbitMessage):
    payment_id = event.get("payment_id", "unknown")
    attempt = 0
    try:
        payment_id = uuid.UUID(payment_id)
        attempt = int(event.get("attempt", 0))
        async with SessionLocal() as session:
            payment = await session.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
            if payment is None:
                raise RuntimeError(f"Unknown payment {payment_id}")
            if payment.status == "pending":
                gateway_result = await gateway.charge(str(payment.amount), payment.currency)
                payment.status = "succeeded" if gateway_result.succeeded else "failed"
                payment.processed_at = datetime.now(timezone.utc)
                await session.commit()
                await session.refresh(payment)
            else:
                # Повтор после ошибки webhook: терминальный результат уже сохранён, второй charge не нужен.
                await session.commit()
            webhook_url = payment.webhook_url
            body = {"event_id": f"payment:{payment.id}:result", "payment_id": str(payment.id),
                "status": payment.status, "amount": str(payment.amount), "currency": payment.currency,
                "processed_at": payment.processed_at.isoformat() if payment.processed_at else None}
        await send_webhook(webhook_url, body)
        await message.ack()
        logger.info("Processed payment %s", payment_id)
    except Exception as exc:
        logger.exception("Payment event failed: %s (attempt=%s)", payment_id, attempt)
        try:
            next_attempt = attempt + 1
            await retry_or_dlq(event, next_attempt, exc)
            await message.ack()
        except Exception:
            logger.exception("Retry/DLQ publish failed; requeue original message")
            await message.nack(requeue=True)
