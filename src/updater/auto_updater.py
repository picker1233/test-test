"""Auto-updater for the launcher."""

import aiohttp
import json
import platform
import subprocess
from pathlib import Path
from typing import Optional, Callable
import aiofiles


class AutoUpdater:
    GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
    
    def __init__(self, owner: str = "your-github-username", repo: str = "custom-minecraft-launcher"):
        self.owner = owner
        self.repo = repo
        self.current_dir = Path(__file__).parent.parent.parent
        self.update_dir = self.current_dir / "updates"

    async def get_latest_release(self) -> Optional[dict]:
        """Get latest release info from GitHub."""
        url = self.GITHUB_API.format(owner=self.owner, repo=self.repo)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        return None

    def get_current_version(self) -> str:
        """Get current launcher version."""
        try:
            import src
            return src.__version__
        except:
            return "0.1.0"

    def should_update(self, latest_release: dict) -> bool:
        """Check if update is needed."""
        current = self.get_current_version()
        latest = latest_release['tag_name'].lstrip('v')
        return latest > current

    async def download_update(self, asset_url: str, progress_callback: Optional[Callable] = None) -> Optional[Path]:
        """Download update asset."""
        self.update_dir.mkdir(exist_ok=True)
        
        platform_suffix = ""
        if platform.system() == "Windows":
            platform_suffix = "-windows"
        elif platform.system() == "Linux":
            platform_suffix = "-linux"
        elif platform.system() == "Darwin":
            platform_suffix = "-macos"

        asset_name = f"launcher{platform_suffix}.exe"  # Assume .exe for Windows
        dest = self.update_dir / asset_name
        
        async with aiohttp.ClientSession() as session:
            async with session.get(asset_url) as resp:
                if resp.status != 200:
                    return None
                
                total_size = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                
                async with aiofiles.open(dest, 'wb') as f:
                    async for chunk in resp.content.iter_chunks():
                        chunk_data = chunk[0]
                        if not chunk[1]:
                            continue
                        await f.write(chunk_data)
                        downloaded += len(chunk_data)
                        if progress_callback:
                            await progress_callback(asset_name, downloaded, total_size)
                
                return dest

    async def install_update(self, update_path: Path) -> bool:
        """Install the update."""
        # For simplicity, copy over current executable
        # In a real app, you'd replace the running exe
        target = self.current_dir / "launcher_updated.exe"  # Example
        
        await aiofiles.copy(update_path, target)
        
        # Run update script or restart
        # This is tricky; often done with batch script
        update_script = self.update_dir / "update.bat"
        with open(update_script, 'w') as f:
            f.write(f"""
@echo off
timeout /t 2
move /y "{target}" "{self.current_dir / "launcher.exe"}"
start "" "{self.current_dir / "launcher.exe"}"
del "%~f0"
""")
        
        subprocess.Popen([str(update_script)], shell=True)
        return True

    async def check_and_update(self, progress_callback: Optional[Callable] = None) -> bool:
        """Check for updates and apply if available."""
        release = await self.get_latest_release()
        if not release or not self.should_update(release):
            return False
        
        # Find appropriate asset
        assets = release['assets']
        asset_url = None
        for asset in assets:
            name = asset['name'].lower()
            if 'windows' in name and platform.system() == "Windows":
                asset_url = asset['browser_download_url']
                break
            elif 'linux' in name and platform.system() == "Linux":
                asset_url = asset['browser_download_url']
                break
            # Add more checks
        
        if not asset_url:
            asset_url = assets[0]['browser_download_url'] if assets else None
        
        if not asset_url:
            return False
        
        # Download and install
        update_path = await self.download_update(asset_url, progress_callback)
        if update_path:
            return await self.install_update(update_path)
        
        return False
