import pytest
from app.services.gateway import FakePaymentGateway
@pytest.mark.asyncio
async def test_gateway_success(monkeypatch):
    async def no_sleep(_): return None
    monkeypatch.setattr("app.services.gateway.asyncio.sleep", no_sleep)
    monkeypatch.setattr("app.services.gateway.random.random", lambda: 0.01)
    result = await FakePaymentGateway().charge("10.00", "RUB")
    assert result.succeeded is True
