import pathlib
import rich.progress
import arrow


class Task(rich.progress.Task):
    def __init__(self, *args, file=None, **kwargs) -> None:
        self._file = file
        self._bytes_received = 0
        self._last_updated = None
        self._file_speed = None
        self._completed = None
        super().__init__(*args, **kwargs)

    @property
    def speed_via_file(self):
        if not self._file:
            return 0
        elif not pathlib.Path(self._file).exists():
            return 0
        elif not self._last_updated or not self._bytes_received:
            self._last_updated = arrow.now().float_timestamp
            self._bytes_received = pathlib.Path(self._file).stat().st_size
            return 0
        new_bytes_received = pathlib.Path(self._file).stat().st_size
        new_time = arrow.now().float_timestamp
        if new_time - self._last_updated < 2:
            return self._file_speed or 0
        elif new_bytes_received == self._bytes_received:
            return 0
        else:
            new_time = arrow.now().float_timestamp
            speed = (new_bytes_received - self._bytes_received) / (
                new_time - self._last_updated
            )
            self._bytes_received = new_bytes_received
            self._last_updated = new_time
            self._file_speed = speed
            return self._file_speed

    @property
    def completed(self):
        if self._completed:
            return self._completed
        if not self._file:
            return 0
        elif not pathlib.Path(self._file).exists():
            return 0
        return pathlib.Path(self._file).stat().st_size

    @completed.setter
    def completed(self, value):
        self._completed = value
