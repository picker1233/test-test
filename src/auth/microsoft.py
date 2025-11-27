"""Microsoft OAuth authentication for Minecraft."""

import asyncio
import json
import aiohttp
import keyring
from pathlib import Path
from typing import Optional, Dict, Any
import msal


class MicrosoftAuthenticator:
    CLIENT_ID = "00000000402b5328"  # Official Minecraft Launcher client ID
    AUTHORITY = "https://login.microsoftonline.com/consumers/"
    SCOPES = ["XboxLive.signin"]

    def __init__(self):
        self.app = msal.PublicClientApplication(
            self.CLIENT_ID,
            authority=self.AUTHORITY
        )

    def get_stored_refresh_token(self) -> Optional[str]:
        """Retrieve stored refresh token from keyring."""
        return keyring.get_password("minecraft_launcher", "microsoft_refresh_token")

    def store_refresh_token(self, token: str):
        """Store refresh token securely."""
        keyring.set_password("minecraft_launcher", "microsoft_refresh_token", token)

    async def initiate_device_code_flow(self) -> Dict[str, Any]:
        """Start device code OAuth flow using MSAL."""
        def _initiate():
            return self.app.initiate_device_flow(self.SCOPES)

        flow = await asyncio.get_event_loop().run_in_executor(None, _initiate)
        if "error" in flow:
            raise Exception(f"Device flow error: {flow['error_description']}")
        return flow

    async def poll_tokens(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """Poll for access token using MSAL."""
        def _acquire():
            return self.app.acquire_token_by_device_flow(flow)

        result = await asyncio.get_event_loop().run_in_executor(None, _acquire)
        if "error" in result:
            raise Exception(result.get("error_description", "Auth failed"))
        return result

    async def authenticate_with_xbox_live(self, access_token: str) -> str:
        """Get Xbox Live token."""
        async with aiohttp.ClientSession() as session:
            data = {
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={access_token}"
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            }

            async with session.post(
                "https://user.auth.xboxlive.com/user/authenticate",
                json=data
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result["Token"]

    async def authenticate_with_xsts(self, xbox_token: str) -> str:
        """Get XSTS token."""
        async with aiohttp.ClientSession() as session:
            data = {
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbox_token]
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT"
            }

            async with session.post(
                "https://xsts.auth.xboxlive.com/xsts/authorize",
                json=data
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result["Token"]

    async def authenticate_with_minecraft(self, xsts_token: str, user_hash: str) -> Dict[str, Any]:
        """Get Minecraft access token."""
        headers = {"Authorization": f"XBL3.0 x={user_hash};{xsts_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.minecraftservices.com/authentication/login_with_xbox",
                headers=headers
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result

    async def get_profile(self, access_token: str) -> Dict[str, Any]:
        """Fetch Minecraft profile."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.minecraftservices.com/minecraft/profile",
                headers=headers
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def authenticate_full_flow(self) -> Dict[str, Any]:
        """Complete authentication flow, returning Minecraft profile."""
        try:
            # Try silent auth with stored refresh token first
            accounts = self.app.get_accounts()
            refresh_token = self.get_stored_refresh_token()

            if refresh_token and accounts:
                def _acquire_silent():
                    return self.app.acquire_token_silent(self.SCOPES, account=accounts[0])

                silent_result = await asyncio.get_event_loop().run_in_executor(None, _acquire_silent)
                if silent_result and "access_token" in silent_result:
                    # Have MS token, continue with Xbox/Minecraft
                    xbox_token = await self.authenticate_with_xbox_live(silent_result["access_token"])
                    xsts_token = await self.authenticate_with_xsts(xbox_token)
                    user_hash = self.extract_xbox_user_hash(xsts_token)
                    mc_data = await self.authenticate_with_minecraft(xsts_token, user_hash)
                    profile = await self.get_profile(mc_data["access_token"])
                    return profile

            # Device code flow
            flow = await self.initiate_device_code_flow()
            print(f"Go to {flow['verification_uri']}")
            print(f"Enter code: {flow['user_code']}")

            # Poll for token
            ms_token_result = await self.poll_tokens(flow)

            # Store refresh token if available
            if "refresh_token" in ms_token_result:
                self.store_refresh_token(ms_token_result["refresh_token"])

            # Xbox auth steps
            xbox_token = await self.authenticate_with_xbox_live(ms_token_result["access_token"])
            xsts_token = await self.authenticate_with_xsts(xbox_token)
            user_hash = self.extract_xbox_user_hash(xsts_token)

            mc_data = await self.authenticate_with_minecraft(xsts_token, user_hash)
            profile = await self.get_profile(mc_data["access_token"])

            return profile

        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")

    def extract_xbox_user_hash(self, xsts_token: str) -> str:
        """Extract user hash from XSTS token."""
        # XSTS token is JWT; decode to get xui[0].uhs
        import base64
        payload = xsts_token.split(".")[1]
        # Fix padding
        payload += "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded)
        return data["DisplayClaims"]["xui"][0]["uhs"]
