"""Offline authentication for Minecraft."""

from typing import Dict, Any


class OfflineAuthenticator:
    """Offline mode authenticator with username only."""

    @staticmethod
    async def authenticate(username: str) -> Dict[str, Any]:
        """Authenticate offline with given username."""
        if not username or len(username) > 16:
            raise ValueError("Invalid username for offline mode")
        
        return {
            "id": username,
            "name": username,
            "type": "offline",
            "access_token": ""  # No token needed
        }
