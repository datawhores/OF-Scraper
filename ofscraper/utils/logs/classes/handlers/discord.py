import asyncio
import logging
import threading
import queue

import ofscraper.managers.sessionmanager.sessionmanager as sessionManager
from ofscraper.managers.sessionmanager.sleepers import (
    discord_forbidden_session_sleeper,
    discord_rate_limit_session_sleeper,
)
import ofscraper.utils.config.data as data
import ofscraper.utils.of_env.of_env as of_env


class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.sess = sessionManager.sessionManager(
            total_timeout=of_env.getattr("DISCORD_TOTAL_TIMEOUT"),
            retries=of_env.getattr("DISCORD_NUM_TRIES"),
            wait_min=of_env.getattr("DISCORD_MIN_WAIT"),
            wait_max=of_env.getattr("DISCORD_MAX_WAIT"),
            forbidden_sleeper=discord_forbidden_session_sleeper,
            rate_limit_sleeper=discord_rate_limit_session_sleeper,
        )
        self.sess._set_session(async_=False)

        self._baseurl = data.get_discord()
        self._url = self._baseurl
        self.chunk_size = 1000

        # --- Threading and Queue Setup ---
        self.queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

        # --- Async setup remains for when DISCORD_ASYNC is True ---
        self._tasks = []
        try:
            self.loop = asyncio.get_running_loop()
        except Exception:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def _worker(self):
        """The worker thread's main loop."""
        while True:
            record = self.queue.get()
            # A None record is the signal to terminate
            if record is None:
                break
            self._send_to_discord(record)
            self.queue.task_done()

    def emit(self, record):
        log_entry = self.format(record)
        if not log_entry or not log_entry.strip():
            return

        log_entry_with_newlines = f"{log_entry}\n\n"

        if of_env.getattr("DISCORD_ASYNC"):
            self._tasks.append(
                self.loop.create_task(self._async_emit(log_entry_with_newlines))
            )
        else:
            # Put the log message on the queue instead of sending it directly
            self.queue.put(log_entry_with_newlines)

    def close(self) -> None:
        # Signal the worker thread to exit
        self.queue.put(None)
        # Wait for the worker thread to finish
        self._thread.join()
        # Handle async tasks shutdown if any were created
        if of_env.getattr("DISCORD_ASYNC") and self._tasks:
            self.loop.run_until_complete(asyncio.gather(*self._tasks))
            self.loop.close()
        super().close()

    def split_text_by_word_chunks(self, text):
        chunks = []
        start = 0
        length = len(text)
        if length <= self.chunk_size:
            return [text]
        while start < length:
            end = min(start + self.chunk_size, length)
            last_space = text.rfind(" ", start, end)
            if last_space == -1 or last_space <= start:
                chunks.append(text[start:end])
                start = end
            else:
                chunks.append(text[start:last_space])
                start = last_space + 1
        return chunks

    def _send_to_discord(self, log_message):
        if not self._url:
            return
        try:
            for chunk in self.split_text_by_word_chunks(log_message):
                if not bool(chunk):
                    continue
                try:
                    with self.sess.requests(
                        self._url,
                        method="post",
                        headers={"Content-type": "application/json"},
                        json={"content": chunk},
                    ) as response:
                        if response.status_code not in {200, 204}:
                            print(
                                f"Request failed for log chunk: '{chunk[:50]}...', status: {response.status_code}"
                            )
                except Exception as e:
                    print(f"Error sending Discord log chunk: '{chunk[:50]}...': {e}")
        except Exception as e:
            print(f"Error in _send_to_discord: {e}")

    async def _async_emit(self, record):
        # This async logic remains unchanged
        if not self._url:
            return
        try:
            # Assumes an async session manager (`asess`) would be initialized
            # if DISCORD_ASYNC is true. For now, this part is hypothetical.
            # async with self.asess.requests_async(...) as r:
            #     pass
            print("Async emit logic would go here.")
        except Exception:
            pass
