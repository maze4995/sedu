from __future__ import annotations

import asyncio
from typing import Any

import httpx


class SyncASGIClient:
    def __init__(self, app, base_url: str = "http://testserver"):
        self._app = app
        self._base_url = base_url

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def _run() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url=self._base_url) as client:
                response = await client.request(method, url, **kwargs)
                await response.aread()
                return response

        return asyncio.run(_run())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
