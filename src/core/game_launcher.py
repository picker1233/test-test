"""Game launcher for Minecraft."""

import subprocess
import platform
import os
from pathlib import Path
from typing import List, Dict, Optional
from ..versions.models import VersionMetadata, VersionLibrary
from ..auth import MicrosoftAuthenticator


class GameLauncher:
    def __init__(self, minecraft_dir: Path = None):
        self.minecraft_dir = minecraft_dir or (Path.home() / ".minecraft")
        self.libraries_dir = self.minecraft_dir / "libraries"
        self.assets_dir = self.minecraft_dir / "assets"
        self.versions_dir = self.minecraft_dir / "versions"

    def get_library_path(self, library: VersionLibrary) -> Optional[Path]:
        """Resolve library JAR path."""
        if not library.downloads or not library.downloads.artifact:
            return None
        
        artifact = library.downloads.artifact
        path_str = artifact.path
        return self.libraries_dir / path_str

    def get_native_path(self, library: VersionLibrary) -> Optional[Path]:
        """Get native library path."""
        if not library.natives or not library.downloads or not library.downloads.classifiers:
            return None
        
        current_os = platform.system().lower()
        arch = platform.machine().lower()
        
        # Map OS/arch to classifier keys
        os_dict = {
            "windows": "windows",
            "linux": "linux",
            "darwin": "macos"
        }
        
        arch_suffix = ""
        if "64" in arch or arch in ("amd64", "x86_64"):
            arch_suffix = "-x86"
        
        classifier_key = f"{os_dict.get(current_os, current_os)}{arch_suffix}"
        
        if classifier_key in library.downloads.classifiers:
            download = library.downloads.classifiers[classifier_key]
            path_str = download.path
            return self.libraries_dir / path_str
        
        return None

    def assemble_classpath(self, metadata: VersionMetadata, applicable_libs: List[VersionLibrary]) -> str:
        """Assemble Java classpath."""
        paths = []
        
        # Add version JAR
        version_jar = self.versions_dir / metadata.id / f"{metadata.id}.jar"
        if version_jar.exists():
            paths.append(str(version_jar))
        
        # Add libraries
        for lib in applicable_libs:
            lib_path = self.get_library_path(lib)
            if lib_path and lib_path.exists():
                paths.append(str(lib_path))
        
        # Join with platform separator
        return os.pathsep.join(paths)

    def build_jvm_args(self, metadata: VersionMetadata, user_profile: Dict, java_path: str) -> List[str]:
        """Build JVM arguments."""
        args = []
        
        # Java executable
        args.append(java_path)
        
        # JVM flags
        args.extend([
            "-Xmx4G",  # Can be configurable
            "-Xms2G",
            "-XX:+UseG1GC",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:G1NewSizePercent=20",
            "-XX:G1ReservePercent=20",
            "-XX:MaxGCPauseMillis=50",
            "-XX:G1HeapRegionSize=32M"
        ])
        
        # Add classpath
        # Note: Assuming applicable_libs is available, but passed through caller
        
        # Game args (user, access token, etc.)
        game_args = self.build_game_args(metadata, user_profile)
        
        return args + game_args

    def build_game_args(self, metadata: VersionMetadata, user_profile: Dict) -> List[str]:
        """Build game arguments."""
        args = []
        
        # Authentication args
        if user_profile.get("access_token"):
            args.extend([
                "--accessToken", user_profile["access_token"],
                "--uuid", user_profile.get("id", ""),
                "--username", user_profile["name"]
            ])
        else:
            # Offline
            args.extend([
                "--uuid", "",
                "--demo"  # Or handle offline properly
            ])
        
        # Version info
        asset_index_id = "pre-1.6"  # default for old versions
        if metadata.assets:
            if isinstance(metadata.assets, str):
                asset_index_id = metadata.assets
            elif hasattr(metadata.assets, 'id'):
                asset_index_id = metadata.assets.id

        args.extend([
            "--version", metadata.id,
            "--gameDir", str(self.minecraft_dir),
            "--assetsDir", str(self.assets_dir),
            "--assetIndex", asset_index_id,
            "--versionType", metadata.type or "release"
        ])
        
        # Logging if specified
        # Add more as needed
        
        return args

    def prepare_launch(self, metadata: VersionMetadata, applicable_libs: List[VersionLibrary], 
                       user_profile: Dict, java_path: str) -> Dict:
        """Prepare launch command."""
        classpath = self.assemble_classpath(metadata, applicable_libs)
        
        jvm_args = [
            "--add-exports", "jdk.naming.dns/com.sun.jndi.dns=java.naming",
            "--add-opens", "java.base/java.util.jar=cpw.mods.securejarhandler",
            "--add-opens", "java.base/java.lang.invoke=cpw.mods.securejarhandler"
        ] + self.build_jvm_args(metadata, user_profile, java_path)
        
        jvm_args.extend(["-cp", classpath])
        jvm_args.append(metadata.mainClass)
        
        game_args = self.build_game_args(metadata, user_profile)
        jvm_args.extend(game_args)
        
        return {
            "command": jvm_args,
            "cwd": self.minecraft_dir,
            "env": os.environ.copy()
        }

    def launch_game(self, launch_data: Dict) -> subprocess.Popen:
        """Launch the game process."""
        popen_args = {
            "args": launch_data["command"],
            "cwd": launch_data["cwd"],
            "env": launch_data["env"],
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "stdin": subprocess.DEVNULL
        }
        
        # Windows needs shell for console
        if platform.system() == "Windows":
            popen_args["shell"] = True
        
        return subprocess.Popen(**popen_args)
