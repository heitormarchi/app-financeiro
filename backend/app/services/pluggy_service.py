"""
Pluggy API client.
Docs: https://docs.pluggy.ai
"""
from datetime import datetime, timedelta

import httpx

from app.core.config import settings

_KEY_TTL = timedelta(hours=1, minutes=50)  # Pluggy keys valid 2h; refresh 10 min early


class PluggyService:
    def __init__(self):
        self.base_url = settings.pluggy_base_url
        self._api_key: str | None = None
        self._api_key_expires_at: datetime | None = None

    async def _get_api_key(self) -> str:
        """Exchange client credentials for an API key (valid 2h, cached until near expiry)."""
        now = datetime.utcnow()
        if self._api_key and self._api_key_expires_at and now < self._api_key_expires_at:
            return self._api_key

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth",
                json={
                    "clientId": settings.pluggy_client_id,
                    "clientSecret": settings.pluggy_client_secret,
                },
            )
            response.raise_for_status()
            self._api_key = response.json()["apiKey"]
            self._api_key_expires_at = datetime.utcnow() + _KEY_TTL
            return self._api_key

    async def create_connect_token(self, user_id: str) -> str:
        """Generate a Connect Token for the Pluggy Widget (frontend)."""
        api_key = await self._get_api_key()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/connect_token",
                json={"clientUserId": user_id},
                headers={"X-API-KEY": api_key},
            )
            response.raise_for_status()
            return response.json()["accessToken"]

    async def get_item(self, item_id: str) -> dict:
        """Retrieve a connected bank item."""
        api_key = await self._get_api_key()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/items/{item_id}",
                headers={"X-API-KEY": api_key},
            )
            response.raise_for_status()
            return response.json()

    async def get_transactions(self, account_id: str, from_date: str, to_date: str) -> list[dict]:
        """Fetch all transactions for an account in date range (YYYY-MM-DD), handling pagination."""
        api_key = await self._get_api_key()
        results: list[dict] = []
        page = 1
        page_size = 100

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"{self.base_url}/transactions",
                    params={
                        "accountId": account_id,
                        "from": from_date,
                        "to": to_date,
                        "pageSize": page_size,
                        "page": page,
                    },
                    headers={"X-API-KEY": api_key},
                )
                response.raise_for_status()
                data = response.json()
                batch = data.get("results", [])
                results.extend(batch)

                total = data.get("total", len(results))
                if len(results) >= total or not batch:
                    break
                page += 1

        return results

    async def get_accounts(self, item_id: str) -> list[dict]:
        """List all accounts for a connected item."""
        api_key = await self._get_api_key()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/accounts",
                params={"itemId": item_id},
                headers={"X-API-KEY": api_key},
            )
            response.raise_for_status()
            return response.json().get("results", [])


pluggy_service = PluggyService()
