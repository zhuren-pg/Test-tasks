# Поток обработки

```text
Client --POST--> FastAPI --transaction--> PostgreSQL(payments + outbox)
                                         Outbox dispatcher
                                                |
                                                v
                                         RabbitMQ main queue
                                                |
                                         FastStream consumer
                                                |
                                      Fake payment gateway (2-5s)
                                                |
                                         PostgreSQL result
                                                |
                                             Webhook
                                                |
                                  retry TTL queues (2/4/8s) -> main
                                                |
                                               DLQ
```

Критическая гарантия: платеж и outbox event записываются атомарно. Публикация после commit может дублироваться при падении между publish и отметкой published_at; это at-least-once. Consumer повторно использует уже сохранённый terminal status и не инициирует повторный charge. Webhook endpoint должен быть идемпотентным.
