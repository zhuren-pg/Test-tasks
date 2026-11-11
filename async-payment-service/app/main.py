import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router
from app.messaging.topology import broker, declare_topology
from app.messaging.outbox import outbox_loop
@asynccontextmanager
async def lifespan(app: FastAPI):
    await broker.connect()
    await declare_topology()
    task = asyncio.create_task(outbox_loop(), name="outbox-dispatcher")
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    await broker.stop()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(router)
@app.get("/health", tags=["health"])
async def health(): return {"status": "ok"}
