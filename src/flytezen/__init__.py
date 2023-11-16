"""flytezen."""

from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    __version__ = "flytezen package may no be installed"

del metadata
