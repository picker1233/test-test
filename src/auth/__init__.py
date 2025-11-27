"""Authentication module for Minecraft accounts."""

from .microsoft import MicrosoftAuthenticator
from .offline import OfflineAuthenticator

__all__ = ["MicrosoftAuthenticator", "OfflineAuthenticator"]
