import httpx
from app.core.config import settings
async def send_webhook(url: str, payload: dict) -> None:
    headers = {"Content-Type": "application/json", "X-Webhook-Event-Id": payload["event_id"]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.webhook_timeout), follow_redirects=False) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
