import os
import pathlib
import platform
import shutil
import stat
import tempfile
from tarfile import TarFile
from zipfile import ZipFile

import httpx
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn

import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths


def ffmpeg_download():
    if platform.system() == "Windows":
        return ffmpeg_windows()
    elif platform.system() == "Linux":
        return ffmpeg_linux()
    elif platform.system() == "Darwin":
        return ffmpeg_mac()


def ffmpeg_windows():
    with tempfile.TemporaryDirectory() as t:
        zip_path = pathlib.Path(t, "ffmpeg.zip")
        with Progress(
            TextColumn("{task.description}"), BarColumn(), DownloadColumn()
        ) as download:
            with httpx.stream(
                "GET",
                constants.getattr("FFMPEG_WINDOWS"),
                timeout=None,
                follow_redirects=True,
            ) as r:
                total = int(r.headers["Content-Length"])
                task1 = download.add_task("ffmpeg download", total=total)
                num_bytes_downloaded = r.num_bytes_downloaded
                with open(pathlib.Path(zip_path), "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1024):
                        f.write(chunk)
                        download.update(
                            task1, advance=r.num_bytes_downloaded - num_bytes_downloaded
                        )
                        num_bytes_downloaded = r.num_bytes_downloaded
            download.remove_task(task1)
        bin_path = common_paths.get_config_home() / "bin" / "ffmpeg.exe"
        bin_path.parent.mkdir(exist_ok=True, parents=True)
        with ZipFile(zip_path) as zObject:
            zObject.extractall(path=t)
        pathlib.Path(bin_path).unlink(missing_ok=True)
        shutil.move(list(pathlib.Path(t).glob("**/ffmpeg.exe"))[0], bin_path)
        st = os.stat(bin_path)
        os.chmod(bin_path, st.st_mode | stat.S_IEXEC)
        return str(bin_path)


def ffmpeg_linux():
    with tempfile.TemporaryDirectory() as t:
        zip_path = pathlib.Path(t, "ffmpeg.tar.xz")
        with Progress(
            TextColumn("{task.description}"), BarColumn(), DownloadColumn()
        ) as download:
            with httpx.stream(
                "GET",
                constants.getattr("FFMPEG_LINUX"),
                timeout=None,
                follow_redirects=True,
            ) as r:
                total = int(r.headers["Content-Length"])
                task1 = download.add_task("ffmpeg download", total=total)
                num_bytes_downloaded = r.num_bytes_downloaded
                with open(pathlib.Path(zip_path), "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1024):
                        f.write(chunk)
                        download.update(
                            task1, advance=r.num_bytes_downloaded - num_bytes_downloaded
                        )
                        num_bytes_downloaded = r.num_bytes_downloaded
            download.remove_task(task1)
        bin_path = common_paths.get_config_home() / "bin" / "ffmpeg"
        bin_path.parent.mkdir(exist_ok=True, parents=True)
        with TarFile.open(zip_path, mode="r:xz") as zObject:
            zObject.extractall(path=t)
        pathlib.Path(bin_path).unlink(missing_ok=True)
        shutil.move(list(pathlib.Path(t).glob("**/ffmpeg"))[0], bin_path)
        st = os.stat(bin_path)
        os.chmod(bin_path, st.st_mode | stat.S_IEXEC)
        return str(bin_path)


def ffmpeg_mac():
    with tempfile.TemporaryDirectory() as t:
        zip_path = pathlib.Path(t, "ffmpeg.zip")
        with Progress(
            TextColumn("{task.description}"), BarColumn(), DownloadColumn()
        ) as download:
            with httpx.stream(
                "GET",
                constants.getattr("FFMPEG_MAC"),
                timeout=None,
                follow_redirects=True,
            ) as r:
                total = int(r.headers["Content-Length"])
                task1 = download.add_task("ffmpeg download", total=total)
                num_bytes_downloaded = r.num_bytes_downloaded
                with open(pathlib.Path(zip_path), "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1024):
                        f.write(chunk)
                        download.update(
                            task1, advance=r.num_bytes_downloaded - num_bytes_downloaded
                        )
                        num_bytes_downloaded = r.num_bytes_downloaded
            download.remove_task(task1)
        bin_path = common_paths.get_config_home() / "bin" / "ffmpeg"
        bin_path.parent.mkdir(exist_ok=True, parents=True)
        with ZipFile(zip_path) as zObject:
            zObject.extractall(path=t)
        pathlib.Path(bin_path).unlink(missing_ok=True)
        shutil.move(list(pathlib.Path(t).glob("**/ffmpeg"))[0], bin_path)
        st = os.stat(bin_path)
        os.chmod(bin_path, st.st_mode | stat.S_IEXEC)
        return str(bin_path)
