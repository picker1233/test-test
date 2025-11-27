"""Async HTTP client utilities."""

import aiohttp
from typing import Optional, Dict, Any


class AsyncHTTPClient:
    """Reusable async HTTP client."""
    
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.default_headers = headers or {}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.default_headers)
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()
    
    async def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """GET request."""
        req_headers = {**self.session.headers, **(headers or {})}
        async with self.session.get(url, headers=req_headers) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def post(self, url: str, json_data: Optional[Dict] = None,
                   data: Optional[Dict] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """POST request."""
        req_headers = {**self.session.headers, **(headers or {})}
        async with self.session.post(url, json=json_data, data=data, headers=req_headers) as resp:
            resp.raise_for_status()
            return await resp.json()
