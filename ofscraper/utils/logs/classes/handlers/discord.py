import asyncio
import logging

from filelock import FileLock

import ofscraper.classes.sessionmanager.sessionmanager as sessionManager
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates_manager
import ofscraper.utils.logs.globals as log_globals


class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)

        self.asess = sessionManager.sessionManager(
           
            total_timeout=constants.getattr("DISCORD_TOTAL_TIMEOUT"),
            retries=constants.getattr("DISCORD_NUM_TRIES"),
            wait_min=constants.getattr("DISCORD_MIN_WAIT"),
            wait_max=constants.getattr("DISCORD_MAX_WAIT"),
        )
        self.sess = sessionManager.sessionManager(
           
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
        self.chunk_size=1000
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

    def split_text_by_word_chunks(self, text):
        chunks = []
        start = 0
        length = len(text)
        if length<=self.chunk_size:
            return [text]
        while start < length:
            end = min(start + self.chunk_size, length)
            last_space = text.rfind(' ', start, end)
            if last_space == -1 or last_space <= start:
                chunks.append(text[start:end])
                start = end
            else:
                chunks.append(text[start:last_space])
                start = last_space + 1
        return chunks

    def _emit(self,log_message):
        try:
            session = self.sess
            target_url = self._url
            if not target_url:
                return

            for chunk in self.split_text_by_word_chunks(log_message):
                if not bool(chunk):
                    continue
                try:
                    with session.requests(
                        target_url,
                        method="post",
                        headers={"Content-type": "application/json"},
                        json={"content": chunk},
                    ) as response:
                        if response.status_code != 204:
                            print(f"Request failed for log chunk: '{chunk[:50]}...', status: {response.status_code}")
                except Exception as e:
                    print(f"Error sending log chunk: '{chunk[:50]}...': {e}")
                    pass
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
