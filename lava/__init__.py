"""lava — A CLI toolkit for interacting with Obsidian vaults."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("lava-cmd")
except PackageNotFoundError:
    __version__ = "unknown"
