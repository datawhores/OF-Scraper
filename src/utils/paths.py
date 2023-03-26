from contextlib import contextmanager
from pathlib import Path
import os
import sys
from rich.console import Console
console=Console()
@contextmanager
def set_directory(path: Path):
    """Sets the cwd within the context

    Args:
        path (Path): The path to the cwd

    Yields:
        None
    """


    origin = Path().absolute()
    createDir(Path(str(path)))
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)
def createDir(path):
    try:
        path.mkdir(exist_ok=True,parents=True)
    except:
        console.print("Error creating directory, check the directory and make sure correct permissions have been issued.")
        sys.exit()