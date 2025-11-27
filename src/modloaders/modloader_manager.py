"""Mod loader manager."""

import json
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Optional, Any
from ..versions.models import VersionMetadata


class ModLoaderManager:
    def __init__(self):
        self.modloader_dir = Path.home() / ".minecraft" / "modloaders"

    async def download_forge_installer(self, forge_version: str) -> Optional[Path]:
        """Download Forge installer."""
        forge_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{forge_version}/forge-{forge_version}-installer.jar"
        dest = self.modloader_dir / "forge" / f"{forge_version}-installer.jar"
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(forge_url) as resp:
                if resp.status == 200:
                    async with aiohttp.open(dest, 'wb') as f:
                        await f.write(await resp.read())
                    return dest
        return None

    async def download_fabric_installer(self, fabric_version: str) -> Optional[Path]:
        """Download Fabric installer."""
        # Find server JAR URL from meta
        meta_url = "https://meta.fabricmc.net/v2/versions/installer"
        async with aiohttp.ClientSession() as session:
            async with session.get(meta_url) as resp:
                versions = await resp.json()
                if versions:
                    installer_version = versions[0]['version']
                    url = versions[0]['url']
                    dest = self.modloader_dir / "fabric" / f"{installer_version}.jar"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    
                    async with session.get(url) as resp2:
                        if resp2.status == 200:
                            async with aiohttp.open(dest, 'wb') as f:
                                await f.write(await resp2.read())
                            return dest
        return None

    async def run_installer(self, installer_path: Path, minecraft_version: str, modloader_type: str) -> Optional[Path]:
        """Run mod loader installer (this might need Java, simplified for example)."""
        # In practice, running JAR installers requires Java
        # For simplicity, assume it generates version JSON
        # Actual implementation would call java -jar installer.jar with params
        
        # Placeholder: create modded version metadata
        modded_dir = Path.home() / ".minecraft" / "versions" / f"{minecraft_version}-{modloader_type}"
        modded_dir.mkdir(parents=True, exist_ok=True)
        
        # Modify version.json (basic example)
        base_metadata_path = Path.home() / ".minecraft" / "versions" / minecraft_version / f"{minecraft_version}.json"
        if base_metadata_path.exists():
            with open(base_metadata_path, 'r') as f:
                base_metadata = json.load(f)
            
            # Add mod loader libraries, change main class, etc.
            modded_metadata = dict(base_metadata)
            modded_metadata["id"] = f"{minecraft_version}-{modloader_type}"
            modded_metadata["arguments"] = {
                "game": ["--modLoader", modloader_type.lower(), "--fml.forgeVersion", "47.1.4"]  # Example
            }
            if "libraries" not in modded_metadata:
                modded_metadata["libraries"] = []
            modded_metadata["libraries"].extend([
                {
                    "name": f"net.minecraftforge:forge:{modloader_type.lower()}-{minecraft_version}",
                    "downloads": {
                        "artifact": {
                            "path": f"net/minecraftforge/forge/{modloader_type.lower()}-{minecraft_version}/forge-{modloader_type.lower()}-{minecraft_version}.jar",
                            "url": f"https://maven.minecraftforge.net/net/minecraftforge/forge/{modloader_type.lower()}-{minecraft_version}/forge-{modloader_type.lower()}-{minecraft_version}.jar"
                        }
                    }
                }
            ])
            modded_metadata["mainClass"] = f"net.minecraft.launchwrapper.Launch"  # Example
            
            modded_path = modded_dir / f"{minecraft_version}-{modloader_type}.json"
            with open(modded_path, 'w') as f:
                json.dump(modded_metadata, f, indent=2)
            
            return modded_path
        
        return None

    async def install_modloader(self, minecraft_version: str, modloader_type: str, 
                               modloader_version: str) -> Optional[VersionMetadata]:
        """Install mod loader for specific Minecraft version."""
        if modloader_type.lower() == "forge":
            installer_path = await self.download_forge_installer(modloader_version)
            if installer_path:
                version_path = await self.run_installer(installer_path, minecraft_version, modloader_type)
                if version_path:
                    # Load and return metadata
                    with open(version_path, 'r') as f:
                        data = json.load(f)
                    return VersionMetadata(**data)
        
        elif modloader_type.lower() == "fabric":
            installer_path = await self.download_fabric_installer(modloader_version)
            if installer_path:
                version_path = await self.run_installer(installer_path, minecraft_version, modloader_type)
                if version_path:
                    with open(version_path, 'r') as f:
                        data = json.load(f)
                    return VersionMetadata(**data)
        
        return None

    async def get_modloader_versions(self, modloader_type: str) -> list:
        """Get available versions for mod loader."""
        if modloader_type.lower() == "forge":
            url = "https://files.minecraftforge.net/net/minecraftforge/forge/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    # Parse HTML for versions (simplified)
                    html = await resp.text()
                    # Extract versions from HTML
                    return ["1.20.1-47.1.0", "1.19.4-45.1.0"]  # Example
        
        elif modloader_type.lower() == "fabric":
            url = "https://meta.fabricmc.net/v2/versions/loader"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    return [v['version'] for v in data]
        
        return []

    def extract_natives(self, lib_path: Path, natives_path: Path):
        """Extract native libraries (simplified)."""
        if lib_path.exists() and lib_path.suffix == ".jar":
            import zipfile
            with zipfile.ZipFile(lib_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if 'META-INF' not in file_info.filename:
                        zip_ref.extract(file_info, natives_path)
