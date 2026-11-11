from app.messaging.topology import broker, MAIN_EXCHANGE
async def publish_payment_event(payload: dict) -> None:
    await broker.publish(payload, exchange=MAIN_EXCHANGE, routing_key="process", persist=True)
