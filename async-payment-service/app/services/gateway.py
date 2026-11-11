import asyncio, random
from dataclasses import dataclass
@dataclass
class GatewayResult:
    succeeded: bool
class FakePaymentGateway:
    async def charge(self, amount: str, currency: str) -> GatewayResult:
        await asyncio.sleep(random.uniform(2, 5))
        return GatewayResult(succeeded=random.random() < 0.90)
