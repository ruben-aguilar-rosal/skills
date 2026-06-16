"""skillsync — mirror, security-scan, and agentically adapt upstream skill repos."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("skillsync")
except PackageNotFoundError:  # running from a source tree without install metadata
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
