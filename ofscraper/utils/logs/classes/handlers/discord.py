import asyncio
import logging

from filelock import FileLock

import ofscraper.classes.sessionmanager.sessionmanager as sessionManager
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates_manager
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.logs.globals as log_globals


class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)

        self.asess = sessionManager.sessionManager(
            backend="httpx",
            total_timeout=constants.getattr("DISCORD_TOTAL_TIMEOUT"),
            retries=constants.getattr("DISCORD_NUM_TRIES"),
            wait_min=constants.getattr("DISCORD_MIN_WAIT"),
            wait_max=constants.getattr("DISCORD_MAX_WAIT"),
        )
        self.sess = sessionManager.sessionManager(
            backend="httpx",
            total_timeout=constants.getattr("DISCORD_TOTAL_TIMEOUT"),
            retries=constants.getattr("DISCORD_NUM_TRIES"),
            wait_min=constants.getattr("DISCORD_MIN_WAIT"),
            wait_max=constants.getattr("DISCORD_MAX_WAIT"),
        )
        self.asess._set_session(async_=True)
        self.sess._set_session(async_=False)

        self._thread = None
        self._baseurl = data.get_discord()
        self._url = self._baseurl
        self._appendhelper()
        self._tasks = []
        try:
            self.loop = asyncio.get_running_loop()
        except Exception:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def _appendhelper(self, date=None):
        if constants.getattr("DISCORD_THREAD_OVERRIDE"):
            try:
                with self.sess.requests(
                    "{url}?wait=true".format(url=self._baseurl),
                    method="post",
                    headers={"Content-type": "application/json"},
                    json={
                        "thread_name": date or dates_manager.getLogDate().get("now"),
                        "content": date or dates_manager.getLogDate().get("now"),
                    },
                    skip_expection_check=True,
                ) as _:
                    pass
            except Exception:
                pass

    def emit(self, record):
        if hasattr(record, "message") and (
            record.message in log_globals.stop_codes or record.message == ""
        ):
            return
        elif record in log_globals.stop_codes or record == "":
            return
        log_entry = self.format(record)
        log_entry = f"{log_entry}\n\n"
        if log_entry is None or log_entry == "None" or log_entry == "":
            return
        elif constants.getattr("DISCORD_ASYNC"):
            self._tasks.append(self.loop.create_task(self._async_emit(log_entry)))
        self._emit(log_entry)
        pass

    def close(self) -> None:
        if constants.getattr("DISCORD_ASYNC"):
            self.loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(self.loop)))
            self.loop.close()

    def _emit(self, record):
        url = data.get_discord()

        try:
            sess = self.sess
            if url is None or url == "":
                return
            with sess.requests(
                self._url,
                method="post",
                headers={"Content-type": "application/json"},
                json={
                    "content": record,
                    # "thread_name": self._thread,
                },
            ) as r:
                if not r.status == 204:
                    raise Exception
        except Exception:
            pass

    async def _async_emit(self, record):
        url = data.get_discord()

        try:
            sess = self.asess
            if url is None or url == "":
                return
            async with sess.requests_async(
                self._url,
                method="post",
                headers={"Content-type": "application/json"},
                json={
                    "content": record,
                    # "thread_name": self._thread,
                },
                skip_expection_check=True,
            ) as r:
                if not r.status == 204:
                    raise Exception
        except Exception:
            pass


class DiscordHandlerMulti(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.lock = FileLock(common_paths.getDiscord())

        self.asess = sessionManager.sessionManager(
            backend="httpx",
            total_timeout=constants.getattr("DISCORD_TOTAL_TIMEOUT"),
            retries=constants.getattr("DISCORD_NUM_TRIES"),
            wait_min=constants.getattr("DISCORD_MIN_WAIT"),
            wait_max=constants.getattr("DISCORD_MAX_WAIT"),
        )
        self.sess = sessionManager.sessionManager(
            backend="httpx",
            total_timeout=constants.getattr("DISCORD_TOTAL_TIMEOUT"),
            retries=constants.getattr("DISCORD_NUM_TRIES"),
            wait_min=constants.getattr("DISCORD_MIN_WAIT"),
            wait_max=constants.getattr("DISCORD_MAX_WAIT"),
        )
        self.asess._set_session(async_=True)
        self.sess._set_session(async_=False)

        self._thread = None
        self._baseurl = data.get_discord()
        self._url = self._baseurl
        self._appendhelper()
        self._tasks = []
        try:
            self.loop = asyncio.get_running_loop()
        except:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def _appendhelper(self, date=None):
        if constants.getattr("DISCORD_THREAD_OVERRIDE"):
            try:
                with self.sess.requests(
                    "{url}?wait=true".format(url=self._baseurl),
                    method="post",
                    headers={"Content-type": "application/json"},
                    json={
                        "thread_name": date or dates_manager.getLogDate().get("now"),
                        "content": date or dates_manager.getLogDate().get("now"),
                    },
                    skip_expection_check=True,
                ) as _:
                    pass
            except Exception:
                pass

    def emit(self, record):
        if hasattr(record, "message") and (
            record.message in log_globals.stop_codes or record.message == ""
        ):
            return
        elif record in log_globals.stop_codes or record == "":
            return

        log_entry = self.format(record)
        log_entry = f"{log_entry}\n\n"
        if constants.getattr("DISCORD_ASYNC"):
            self._tasks.append(self.loop.create_task(self._async_emit(log_entry)))
        else:
            self._emit(log_entry)
        pass

    def close(self) -> None:
        if constants.getattr("DISCORD_ASYNC"):
            with self.lock:
                self.loop.run_until_complete(
                    asyncio.gather(*asyncio.all_tasks(self.loop))
                )
                self.loop.close()

    def _emit(self, record):
        url = data.get_discord()
        try:
            sess = self.sess
            if url is None or url == "":
                return
            with self.lock:
                with sess.requests(
                    self._url,
                    method="post",
                    headers={"Content-type": "application/json"},
                    json={
                        "content": record,
                        # "thread_name": self._thread,
                    },
                ) as r:
                    if not r.status == 204:
                        raise Exception
        except Exception:
            pass

    async def _async_emit(self, record):
        url = data.get_discord()
        try:
            sess = self.asess
            if url is None or url == "":
                return
            async with sess.requests_async(
                self._url,
                method="post",
                headers={"Content-type": "application/json"},
                json={
                    "content": record,
                    # "thread_name": self._thread,
                },
                skip_expection_check=True,
            ) as r:
                if not r.status == 204:
                    raise Exception
        except Exception:
            pass
