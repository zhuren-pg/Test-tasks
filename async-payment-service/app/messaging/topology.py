from faststream.rabbit import RabbitBroker, RabbitQueue, RabbitExchange
from app.core.config import settings

MAIN_EXCHANGE = RabbitExchange("payments.events", type="direct", durable=True)
RETRY_EXCHANGE = RabbitExchange("payments.retry", type="direct", durable=True)
DLQ_EXCHANGE = RabbitExchange("payments.dlx", type="direct", durable=True)

MAIN_QUEUE = RabbitQueue("payments.process", routing_key="process", durable=True)
RETRY_2S = RabbitQueue("payments.retry.2s", routing_key="2s", durable=True,
    arguments={"x-message-ttl": 2000, "x-dead-letter-exchange": "payments.events", "x-dead-letter-routing-key": "process"})
RETRY_4S = RabbitQueue("payments.retry.4s", routing_key="4s", durable=True,
    arguments={"x-message-ttl": 4000, "x-dead-letter-exchange": "payments.events", "x-dead-letter-routing-key": "process"})
DLQ_QUEUE = RabbitQueue("payments.dlq", routing_key="dead", durable=True)

broker = RabbitBroker(settings.rabbitmq_url)

async def declare_topology():
    """Declare durable exchanges/queues and bind routing keys explicitly."""
    main_exchange = await broker.declare_exchange(MAIN_EXCHANGE)
    retry_exchange = await broker.declare_exchange(RETRY_EXCHANGE)
    dlq_exchange = await broker.declare_exchange(DLQ_EXCHANGE)

    main_queue = await broker.declare_queue(MAIN_QUEUE)
    retry_2s = await broker.declare_queue(RETRY_2S)
    retry_4s = await broker.declare_queue(RETRY_4S)
    dlq_queue = await broker.declare_queue(DLQ_QUEUE)

    await main_queue.bind(main_exchange, routing_key="process")
    await retry_2s.bind(retry_exchange, routing_key="2s")
    await retry_4s.bind(retry_exchange, routing_key="4s")
    await dlq_queue.bind(dlq_exchange, routing_key="dead")
