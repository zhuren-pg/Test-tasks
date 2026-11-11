# Асинхронный сервис процессинга платежей

Демонстрационный микросервис: FastAPI принимает платежи, PostgreSQL хранит их и outbox-события, RabbitMQ доставляет задания одному FastStream consumer, который эмулирует шлюз (2–5 секунд, 90% успех / 10% бизнес-отказ) и отправляет webhook.

## Запуск
Требуются Docker Engine и Docker Compose v2.

Linux/macOS:
```bash
cp .env.example .env
docker compose up --build
```
Windows PowerShell:
```powershell
Copy-Item .env.example .env
docker compose up --build
```

API: http://localhost:8000 · Swagger: http://localhost:8000/docs · RabbitMQ UI: http://localhost:15672 (guest/guest).

API контейнер применяет Alembic migrations перед запуском Uvicorn. В его lifespan запускается Outbox dispatcher. Consumer — отдельный контейнер.

## Создать платёж
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-secret-change-me' \
  -H 'Idempotency-Key: order-42-payment-1' \
  -d '{"amount":"1499.90","currency":"RUB","description":"Оплата заказа 42","metadata":{"order_id":"42"},"webhook_url":"https://webhook.site/YOUR-ID"}'
```
Ожидается `202 Accepted`: `payment_id`, `status=pending`, `created_at`.

```bash
curl http://localhost:8000/api/v1/payments/ВАШ-UUID -H 'X-API-Key: dev-secret-change-me'
```
Повтор POST с тем же `Idempotency-Key` и тем же payload возвращает тот же платёж. Повтор с другим payload возвращает `409 Conflict`.

## Гарантии и поведение
- Платёж и Outbox-запись создаются в одной транзакции PostgreSQL.
- Dispatcher выбирает неопубликованные записи через `FOR UPDATE SKIP LOCKED`, публикует их в RabbitMQ, затем проставляет `published_at`.
- Если процесс упадёт после publish, но до отметки `published_at`, событие может прийти повторно. Это at-least-once доставка; consumer идемпотентен.
- Consumer сохраняет терминальный результат платежа до webhook. При ошибке webhook повторно отправляет сохранённый результат, не вызывает шлюз повторно.
- Ошибки инфраструктуры/webhook повторяются через TTL очереди 2/4 секунды (экспоненциальная задержка); после трёх суммарных попыток обработки (первая + две повторные) событие отправляется в `payments.dlq`.
- `failed` — бизнес-результат эмулятора (10%), а не техническая ошибка, поэтому он не retry-ится.
- Webhook также at-least-once: принимающая сторона должна дедуплицировать по `event_id` / `X-Webhook-Event-Id`.

## Очереди
`payments.process`, `payments.retry.2s`, `payments.retry.4s`, `payments.dlq`.

## Проверка

Unit-тест эмулятора можно запустить локально после установки зависимостей:
```bash
python -m pip install -r requirements.txt
pytest -q
```

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f consumer
```
В RabbitMQ Management → Queues можно наблюдать основную очередь, retry queues и DLQ.

## Webhook
POST JSON:
```json
{"event_id":"payment:UUID:result","payment_id":"UUID","status":"succeeded","amount":"1499.90","currency":"RUB","processed_at":"2026-01-01T12:00:05+00:00"}
```
Заголовок `X-Webhook-Event-Id` повторяет `event_id`; успешный ответ — любой HTTP 2xx. Для теста используйте webhook.site. Не указывайте localhost для сервиса на хосте: из контейнера localhost — сам контейнер.

## Структура
```text
app/api/             роуты и API-key auth
app/core/            настройки
app/db/              async engine/session
app/models/          SQLAlchemy Payment и Outbox
app/schemas/         Pydantic v2 контракты
app/services/        fake gateway и webhook client
app/messaging/       Rabbit topology, publisher, outbox loop, consumer
alembic/             миграция payments + outbox
tests/               unit tests
```

## Ограничения демонстрационного решения / production hardening
- Outbox dispatcher находится в API-процессе; при масштабировании API можно вынести его в отдельный deployment. `SKIP LOCKED` поддерживает параллельные экземпляры.
- Retry/DLQ переводятся явной публикацией и ack исходного сообщения. Это даёт at-least-once; при сбое между publish и ack возможны дубликаты.
- В production нужны подпись webhook, allowlist доменов/IP и SSRF-защита, запрет/контроль redirect, TLS, секреты через secret manager, rate limits, аудит, метрики/tracing, reconciliation с провайдером, политика хранения и защита персональных данных.
- В учебной реализации нет отдельного статуса `processing` и отдельного журнала попыток webhook; для промышленного решения их стоит добавить.
