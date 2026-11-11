import asyncio, logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.outbox import Outbox
from app.messaging.publisher import publish_payment_event
logger = logging.getLogger(__name__)
async def publish_outbox_batch(batch_size: int = 100) -> int:
    async with SessionLocal() as session:
        result = await session.execute(select(Outbox).where(Outbox.published_at.is_(None))
            .order_by(Outbox.created_at).limit(batch_size).with_for_update(skip_locked=True))
        rows = list(result.scalars())
        if not rows:
            await session.rollback()
            return 0
        published = 0
        for row in rows:
            try:
                await publish_payment_event(row.payload)
                row.published_at = datetime.now(timezone.utc)
                row.publish_attempts += 1
                published += 1
            except Exception:
                row.publish_attempts += 1
                logger.exception("Outbox publish failed: %s", row.id)
                break
        await session.commit()
        return published
async def outbox_loop():
    while True:
        try:
            count = await publish_outbox_batch()
            if count == 0: await asyncio.sleep(settings.outbox_poll_interval)
        except asyncio.CancelledError: raise
        except Exception:
            logger.exception("Outbox dispatcher failed")
            await asyncio.sleep(settings.outbox_poll_interval)
