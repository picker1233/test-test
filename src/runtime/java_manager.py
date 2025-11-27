"""Java runtime manager for Minecraft."""

import platform
import subprocess
import zipfile
import shutil
from pathlib import Path
from typing import Optional, List
import aiohttp
import aiofiles


class JavaManager:
    def __init__(self, runtime_dir: Optional[Path] = None):
        self.runtime_dir = runtime_dir or (Path.home() / ".minecraft" / "runtime")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def get_system_java(self) -> Optional[Path]:
        """Detect installed Java on system."""
        try:
            result = subprocess.run(["java", "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                # Try to find java executable
                result_cwd = subprocess.run(["where", "java"], capture_output=True, text=True)
                if result_cwd.returncode == 0:
                    java_path = Path(result_cwd.stdout.strip().split('\n')[0])
                    return java_path.parent / "java.exe" if platform.system() == "Windows" else java_path
        except Exception:
            pass
        
        # Check common paths
        common_paths = [
            Path("C:/Program Files/Java"),
            Path("C:/Program Files (x86)/Java"),
            Path("/usr/lib/jvm"),
            Path("/Library/Java/JavaVirtualMachines")
        ]
        
        for base in common_paths:
            if base.exists():
                for item in base.iterdir():
                    if item.is_dir() and "java" in item.name.lower():
                        java_bin = item / "bin" / "java.exe" if platform.system() == "Windows" else item / "bin" / "java"
                        if java_bin.exists():
                            return java_bin
        
        return None

    def get_adoptium_version_url(self) -> str:
        """Get Adoptium download URL for current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Map to Adoptium identifiers
        os_map = {
            "windows": "windows",
            "linux": "linux",
            "darwin": "mac"
        }
        arch_map = {
            "amd64": "x64",
            "x86_64": "x64",
            "i386": "x86",
            "arm64": "aarch64"
        }
        
        os_id = os_map.get(system, system)
        arch_id = arch_map.get(machine, machine)
        
        return f"https://api.adoptium.net/v3/binary/latest/17/ga/{os_id}/{arch_id}/jdk/hotspot/normal/adoptium"

    async def download_java(self, progress_callback: Optional[callable] = None) -> Optional[Path]:
        """Download and extract Adoptium JDK."""
        url = self.get_adoptium_version_url()
        archive_name = f"java-17-adoptium-{platform.system().lower()}-{platform.machine().lower()}.zip"
        archive_path = self.runtime_dir / archive_name
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                total_size = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                
                async with aiofiles.open(archive_path, 'wb') as f:
                    async for chunk in resp.content.iter_chunks():
                        chunk_data = chunk[0]
                        if not chunk[1]:
                            continue
                        await f.write(chunk_data)
                        downloaded += len(chunk_data)
                        if progress_callback:
                            await progress_callback("java.zip", downloaded, total_size)
        
        # Extract
        extract_dir = self.runtime_dir / "java-17"
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find java executable
        for item in extract_dir.iterdir():
            if item.is_dir():
                java_bin = item / "bin" / ("java.exe" if platform.system() == "Windows" else "java")
                if java_bin.exists():
                    return java_bin
        
        return None

    def get_java_version(self, java_path: Path) -> Optional[str]:
        """Get Java version."""
        try:
            result = subprocess.run([str(java_path), "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                version_line = result.stderr.split('\n')[0]  # version is on stderr
                if "version" in version_line:
                    # Parse version
                    version_part = version_line.split('"')[1]
                    return version_part
        except Exception:
            pass
        return None

    async def ensure_java(self, progress_callback: Optional[callable] = None) -> Path:
        """Ensure Java is available, download if needed."""
        # Try system Java first
        system_java = self.get_system_java()
        if system_java:
            version = self.get_java_version(system_java)
            if version and version.startswith("17"):
                return system_java
        
        # Try downloaded Java
        java_paths = list(self.runtime_dir.glob("**/bin/java")) + list(self.runtime_dir.glob("**/bin/java.exe"))
        for java_path in java_paths:
            version = self.get_java_version(java_path)
            if version and version.startswith("17"):
                return java_path
        
        # Download new one
        java_path = await self.download_java(progress_callback)
        if java_path:
            return java_path
        
        raise Exception("Could not find or download suitable Java runtime")
