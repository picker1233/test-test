"""Download manager for assets and libraries."""

import aiohttp
import aiofiles
import hashlib
import asyncio
from pathlib import Path
from typing import List, Callable, Optional
from .models import VersionMetadata, VersionLibrary


class DownloadManager:
    def __init__(self, concurrent_downloads: int = 8):
        self.concurrent_downloads = concurrent_downloads
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(concurrent_downloads)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def download_file(self, url: str, dest: Path, expected_sha1: Optional[str] = None,
                           progress_callback: Optional[Callable] = None) -> bool:
        """Download a file with optional SHA1 verification."""
        await self.semaphore.acquire()
        try:
            async with self.session.get(url) as resp:
                resp.raise_for_status()
                total_size = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(dest, 'wb') as f:
                    async for chunk in resp.content.iter_chunks():
                        chunk_data = chunk[0]
                        if not chunk[1]:  # Last chunk
                            continue
                        await f.write(chunk_data)
                        downloaded += len(chunk_data)
                        if progress_callback:
                            await progress_callback(dest.name, downloaded, total_size)
                
                # Verify SHA1 if provided
                if expected_sha1:
                    if not await self.verify_sha1(dest, expected_sha1):
                        return False
                
                return True
        finally:
            self.semaphore.release()

    @staticmethod
    async def verify_sha1(file_path: Path, expected_sha1: str) -> bool:
        """Verify SHA1 hash of a file."""
        hash_sha1 = hashlib.sha1()
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha1.update(chunk)
        return hash_sha1.hexdigest() == expected_sha1.lower()

    async def download_libraries(self, applicable_libs: List[VersionLibrary],
                                progress_callback: Optional[Callable] = None) -> List[bool]:
        """Download all libraries."""
        tasks = []
        
        for lib in applicable_libs:
            if not lib.downloads or not lib.downloads.artifact:
                continue
            
            artifact = lib.downloads.artifact
            url = artifact.url
            dest = Path.home() / ".minecraft" / "libraries" / artifact.path
            sha1 = getattr(artifact, 'sha1', None)
            
            task = self.download_file(url, dest, sha1)
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def download_version_jar(self, metadata: VersionMetadata,
                                   progress_callback: Optional[Callable] = None) -> bool:
        """Download version JAR."""
        downloads = metadata.downloads
        if downloads and downloads.client:
            client_dl = downloads.client
            url = getattr(client_dl, 'url', None)
            sha1 = getattr(client_dl, 'sha1', None)
            dest = Path.home() / ".minecraft" / "versions" / metadata.id / f"{metadata.id}.jar"

            if url:
                return await self.download_file(url, dest, sha1, progress_callback)

        # For very old versions that don't have download URLs,
        # try to construct a URL (helps for some versions)
        if not downloads or not downloads.client or not getattr(downloads.client, 'url', None):
            # Try old-style URL construction
            assumed_url = f"https://s3.amazonaws.com/Minecraft.Download/versions/{metadata.id}/{metadata.id}.jar"
            dest = Path.home() / ".minecraft" / "versions" / metadata.id / f"{metadata.id}.jar"
            # Don't fail if this doesn't work - some ancient versions may not download
            # Silently skip failed downloads for ancient versions (expected)
            try:
                return await self.download_file(assumed_url, dest, None, progress_callback)
            except Exception:
                # Ancient versions don't have preserved JAR downloads - this is normal
                pass

        return False

    async def download_asset_index(self, metadata: VersionMetadata,
                                   progress_callback: Optional[Callable] = None) -> Optional[dict]:
        """Download asset index JSON."""
        assets = metadata.assets
        if not assets:
            return None

        # Handle different assets formats
        if isinstance(assets, str):
            # Old versions have string assets like "pre-1.6"
            # For these, create empty asset index
            return {}
        elif hasattr(assets, 'url') and hasattr(assets, 'id'):
            # Modern version with dict assets
            url = assets.url
            dest = Path.home() / ".minecraft" / "assets" / "indexes" / f"{assets.id}.json"

            success = await self.download_file(url, dest, assets.sha1 if hasattr(assets, 'sha1') else None, progress_callback)
            if success:
                import json
                async with aiofiles.open(dest, 'r') as f:
                    return json.loads(await f.read())

        return None

    async def download_assets(self, asset_index: dict,
                              progress_callback: Optional[Callable] = None) -> List[bool]:
        """Download all assets from index."""
        objects = asset_index.get('objects', {})
        base_url = "https://resources.download.minecraft.net/"
        
        tasks = []
        
        for asset_path, asset_info in objects.items():
            hash_part = asset_info['hash']
            subdir = hash_part[:2]
            url = f"{base_url}{subdir}/{hash_part}"
            dest = Path.home() / ".minecraft" / "assets" / "objects" / subdir / hash_part
            sha1 = asset_info['hash']
            
            task = self.download_file(url, dest, sha1)
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
