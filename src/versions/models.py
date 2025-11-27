"""Data models for Minecraft versions."""

from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


class VersionDownloads(BaseModel):
    client: Optional[Dict[str, Any]] = None
    server: Optional[Dict[str, Any]] = None


class VersionLibraryExtractor(BaseModel):
    exclude: Optional[List[str]] = None


class VersionLibraryArtifact(BaseModel):
    path: Optional[str] = None
    sha1: Optional[str] = None
    size: Optional[Union[int, str]] = None
    url: Optional[str] = None


class VersionLibraryDownloads(BaseModel):
    artifact: Optional[VersionLibraryArtifact] = None
    classifiers: Optional[Dict[str, Any]] = None


class VersionLibraryRulesOs(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    arch: Optional[str] = None


class VersionLibraryRules(BaseModel):
    action: str
    os: Optional[VersionLibraryRulesOs] = None


class VersionLibrary(BaseModel):
    name: str
    downloads: Optional[VersionLibraryDownloads] = None
    rules: Optional[List[VersionLibraryRules]] = None
    extract: Optional[VersionLibraryExtractor] = None
    natives: Optional[Dict[str, str]] = None


class VersionAssetsUnion(BaseModel):
    id: Optional[str] = None
    sha1: Optional[str] = None
    size: Optional[int] = None
    totalSize: Optional[int] = None
    url: Optional[str] = None


class VersionInfo(BaseModel):
    id: str
    type: str
    url: str
    time: datetime
    releaseTime: datetime
    sha1: Optional[str] = None
    complianceLevel: int = 0


class VersionManifest(BaseModel):
    latest: Dict[str, str]
    versions: List[VersionInfo]


class VersionMetadata(BaseModel):
    """Parsed version.json data - flexible for all versions"""
    id: str
    type: Optional[str] = None
    time: Optional[datetime] = None
    releaseTime: Optional[datetime] = None
    minimumLauncherVersion: Optional[int] = None
    downloads: Optional[VersionDownloads] = None
    assets: Optional[Union[str, VersionAssetsUnion]] = None
    arguments: Optional[Dict[str, Any]] = None
    minecraftArguments: Optional[str] = None
    libraries: Optional[List[VersionLibrary]] = None
    mainClass: Optional[str] = None
    jar: Optional[str] = None
