import importlib.metadata

try:
    # This will read the version from the installed package's metadata
    __version__ = importlib.metadata.version("ofscraper")
except importlib.metadata.PackageNotFoundError:
    # This is a fallback for when the package is not installed, e.g.,
    # when running in a development environment without installation.
    __version__ = "0.0.0"