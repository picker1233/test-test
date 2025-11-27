"""Tests for auth module."""

import pytest
from unittest.mock import AsyncMock, patch
from src.auth.offline import OfflineAuthenticator


@pytest.mark.asyncio
async def test_offline_auth():
    """Test offline authentication."""
    profile = await OfflineAuthenticator.authenticate("testuser")
    assert profile["name"] == "testuser"
    assert profile["type"] == "offline"


# Add more tests for Microsoft auth (with mocks)
