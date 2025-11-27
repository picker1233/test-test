"""Version manifest and metadata manager."""

import aiohttp
import json
from pathlib import Path
from typing import Optional, Union
from .models import VersionManifest, VersionMetadata, VersionInfo


class VersionManager:
    MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    CACHE_DIR = Path.home() / ".minecraft" / "versions"

    def __init__(self):
        self.cache_dir = self.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def fetch_manifest(self) -> VersionManifest:
        """Fetch the launcher version manifest."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        async with self.session.get(self.MANIFEST_URL) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return VersionManifest(**data)

    async def get_version_info(self, version_id: str, manifest: Optional[VersionManifest] = None) -> Optional[VersionInfo]:
        """Get version info for a specific version."""
        if not manifest:
            manifest = await self.fetch_manifest()
        
        for version in manifest.versions:
            if version.id == version_id:
                return version
        return None

    async def fetch_version_metadata(self, version_info: VersionInfo) -> VersionMetadata:
        """Fetch and parse version.json for a specific version."""
        cache_path = self.cache_dir / f"{version_info.id}.json"
        
        # Use cache if available and valid
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                data = json.load(f)
                if data.get("sha1") == version_info.sha1:
                    return VersionMetadata(**data)

        # Fetch from URL
        if not self.session:
            self.session = aiohttp.ClientSession()

        async with self.session.get(version_info.url) as resp:
            resp.raise_for_status()
            data = await resp.json()

        # Cache it
        with open(cache_path, 'w') as f:
            json.dump(data, f)

        return VersionMetadata(**data)

    async def filter_applicable_libraries(self, metadata: VersionMetadata) -> list:
        """Filter libraries based on rules (OS, arch, etc.)."""
        import platform
        import sys
        
        current_os = platform.system().lower()
        if current_os == "darwin":
            current_os = "osx"
        current_arch = platform.machine().lower()
        java_version = int(sys.version_info[1])  # Assume Java version matches Python minor
        
        applicable = []
        
        for lib in metadata.libraries:
            if not lib.rules:
                applicable.append(lib)
                continue
                
            allow = True
            for rule in lib.rules:
                if self._matches_rule(rule, current_os, current_arch, java_version):
                    if rule.action == "disallow":
                        allow = False
                        break
                    elif rule.action == "allow":
                        allow = True
                else:
                    if rule.action == "allow":
                        allow = False
            
            if allow:
                applicable.append(lib)
        
        return applicable

    def _matches_rule(self, rule, os_name: str, arch: str, java_version: int) -> bool:
        """Check if a rule matches current system."""
        # rule can be dict or VersionLibraryRules object
        if hasattr(rule, 'os') and rule.os:
            rule_os = rule.os
        elif isinstance(rule, dict):
            rule_os = rule.get("os", {})
        else:
            return True

        if hasattr(rule_os, 'name') and rule_os.name and rule_os.name != os_name:
            return False
        if hasattr(rule_os, 'arch') and rule_os.arch and rule_os.arch not in arch:
            return False
        # Add Java version check if needed

        return True
