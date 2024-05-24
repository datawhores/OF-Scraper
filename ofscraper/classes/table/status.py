import arrow


class Status:
    def __init__(self, *args, **kwargs) -> None:
        self._status = {}
        self._set_defaults()

    def _set_defaults(self):
        self._status.setdefault("mediatype", None)
        self._status.setdefault("responsetype", None)
        self._status.setdefault("unlocked", None)
        self._status.setdefault("downloaded", None)
        self._status.setdefault("times_detected", None)
        self._status.setdefault("post_media_count", None)
        self._status.setdefault("username", None)
        self._status.setdefault("mindate", None)
        self._status.setdefault("maxdate", None)
        self._status.setdefault("min_length", {})
        self._status.setdefault("max_length", {})

    def validate(self, key, test):
        key = key.lower()
        if key in {"unlocked", "downloaded", "mediatype", "responsetype"}:
            return self._bool_helper(key, test)
        elif key in {"times_detected", "post_media_count"}:
            return self._times_detected_helper(key, test)
        elif key in {"username"}:
            return self._generic_helper(key, test)
        elif key == "post_date":
            return self._date_helper(test)
        elif key == "length":
            return self._length_helper(test)
        return True

    def _generic_helper(self, key, test):
        if self._status[key] == None:
            return True
        return test.lower() == self._status[key]

    def _length_helper(self, test):
        if not bool(self._status["max_length"]) and not bool(
            self._status["min_length"]
        ):
            return True
        elif bool(self._status["max_length"]) and bool(self._status["min_length"]):
            min_length = arrow.get(
                "{hour}:{minute}:{second}".format(
                    hour=self._status["min_length"].get("min_hour", "0"),
                    minute=self._status["min_length"].get("min_minute", "0"),
                    second=self._status["min_length"].get("min_second", "0"),
                ),
                ["h:m:s"],
            )
            max_length = arrow.get(
                "{hour}:{minute}:{second}".format(
                    hour=self._status["max_length"].get("max_hour", "0"),
                    minute=self._status["max_length"].get("max_minute", "0"),
                    second=self._status["max_length"].get("max_second", "0"),
                ),
                ["h:m:s"],
            )
            return test.is_between(min_length, max_length, bounds="[]")
        elif bool(self._status["min_length"]):
            min_length = arrow.get(
                "{hour}:{minute}:{second}".format(
                    hour=self._status["min_length"].get("min_hour", "0"),
                    minute=self._status["min_length"].get("min_minute", "0"),
                    second=self._status["min_length"].get("min_second", "0"),
                ),
                ["h:m:s"],
            )
            return test >= arrow.get(min_length)
        elif bool(self._status["max_length"]):
            max_length = arrow.get(
                "{hour}:{minute}:{second}".format(
                    hour=self._status["max_length"].get("max_hour", "0"),
                    minute=self._status["max_length"].get("max_minute", "0"),
                    second=self._status["max_length"].get("max_second", "0"),
                ),
                ["h:m:s"],
            )
            return test <= arrow.get(max_length)
        return True

    def _date_helper(self, test):
        if not bool(self._status["mindate"]) and not bool(self._status["maxdate"]):
            return True
        elif bool(self._status["mindate"]) and bool(self._status["maxdate"]):
            return test.is_between(
                arrow.get(self._status["mindate"]),
                arrow.get(self._status["maxdate"]),
                bounds="[]",
            )
        elif bool(self._status["mindate"]):
            return test >= arrow.get(self._status["mindate"])
        elif bool(self._status["maxdate"]):
            return test <= arrow.get(self._status["maxdate"])
        return True

    def _bool_helper(self, key, test):
        if self._status[key] == None:
            return True
        elif test in self._status[key]:
            return True
        return False

    def _times_detected_helper(self, key, test):
        if self._status[key] is None:
            return True
        else:
            return int(self._status[key]) == int(test)

    @property
    def status(self):
        return self._status


status = Status()
