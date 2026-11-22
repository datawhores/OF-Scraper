# Hooks for add-ons

Code that runs in the same process as the scraper, such as the GUI patch or a plugin, can use the functions and events on this page instead of shipping changed copies of the scraper's files. Each entry gives the module, how to call it, when it runs, what it gives back, how it behaves with PostgreSQL on, and which part of the GUI patch's copied files it can replace.

This file is written by hand. Check an entry against the code before relying on it.

## Calling async code

- **Sync functions** run on the calling thread and block it until they return.
- **`async def` functions** must be awaited. From sync code, call them from a thread that has no running event loop, with `asyncio.run(...)`. From another thread while a loop runs elsewhere, use `asyncio.run_coroutine_threadsafe(coro, loop).result()`.
- **Functions wrapped in `@run`** (`ofscraper/utils/context/run_async.py`) run the coroutine to the end when the thread has no running loop. Inside a running loop they return the coroutine unawaited, so the work doesn't happen unless the caller awaits it. Call them from a worker thread, not from a loop's thread.

## Downloads

### Download events

`ofscraper/utils/events.py` has `subscribe(name, fn)` and `unsubscribe(name, fn)`. Subscribing the same function again does nothing. `subscribe` raises `ValueError` for an unknown name; `unsubscribe` ignores a name or function it doesn't know. Subscribers get keyword arguments:

- **`item_downloaded(ele, path)`:** a media file has been saved at `path` (a `pathlib.Path`) and recorded in the database. It's sent before `after_download_script` runs, and a stop during the script still counts the item as downloaded. Sent for normal files, DRM videos and Fansly HLS/DASH streams. The Fansly check of videos saved without sound, which runs after a run's downloads, also sends it when it saves a video again with sound, with no `item_finished` after it.
- **`item_finished(ele, username, result, reason)`:** the download loop has counted one item. `result` is `downloaded`, `failed`, `skipped` or `stopped`. An item a stop ended before it started gets no event. `reason` is None unless the item failed or was skipped:
  - skipped: `size limit`, `skip_download_script`, `CDM keys not found`, `protected stream`, or `skipped`.
  - failed: `no link` (locked or removed media), or the error's text with links removed (also JSON-escaped and percent-encoded ones; a link without a scheme keeps its address but loses everything after the `?`) and cookies and the home folder's name hidden as in the logs. `download failed` when there's no error.

A subscriber can be a plain function or an `async def` one. It runs in the download's own thread and event loop and holds up that download until it returns, so a GUI should hand the event to its own thread and return. An error in a subscriber is logged at debug level and doesn't affect the download.

- **PostgreSQL:** no difference. `item_downloaded` is sent after the row is saved, to whichever database is in use.
- **Replaces in the GUI patch:** the `plugin_manager.dispatch_event("on_item_downloaded", ...)` calls in its copies of `main_download.py` and `alt_download.py` (a subscriber can make the same call with `ele` and `str(path)`), and the failure tracking and table-cell updates in its copy of `download/run.py`.

### Stopping downloads

`ofscraper.commands.scraper.actions.download.stop.request()` stops the running downloads and post fetches, from any thread. `stop.requested` is the `threading.Event` it sets, and `stop.clear()` clears it. A scrape and the check commands clear it when they start.

- **Replaces in the GUI patch:** the `is_gui_cancelled()` checks in its copies of `download/run.py` and `downloadmanager.py`.

## Check tables

Both functions are in `ofscraper/commands/check.py`. They are sync and use `@run` functions inside, so call them from a worker thread with no running event loop.

### `gather_rows(command)`

Runs a check command's scan and returns the rows its table would show, without opening the Textual table or starting the table's download thread. `command` is `post_check`, `msg_check`, `paid_check` or `story_check`; anything else raises `ValueError`. The creators and areas come from the settings, as for the command.

- It sets `force_all` to True and `after` to 0 in the settings, as the check commands do. They stay that way for the rest of the process, so a scrape run after it in the same process gets them too.
- It checks the auth first with `check_auth()` (see [Auth](#auth)), so it can raise `AuthCheckUnavailable` or `AuthCheckLeft`. When the auth is rejected, `check_auth()` opens the terminal's auth prompt (`make.make_auth`; on Fansly its login prompt), and choosing quit there raises `SystemExit(0)`. The GUI patch's copy of `checkers.py` skips that prompt in GUI mode; the core doesn't.
- It doesn't clear a stop. Call `stop.clear()` first (see [Stopping downloads](#stopping-downloads)): after a `stop.request()` the scan raises `stop.DownloadsStopped`, which is a `BaseException`, so `except Exception` doesn't catch it.
- `story_check` on Fansly logs an error and returns `[]`.
- Rows add to the last scan's. Call `reset_table_data()` first for a new table.
- The check commands call it and then open the table, so a row is the same dict the table gets.
- **PostgreSQL:** the downloaded state and file names come from `get_media_post_files_downloaded`, so they come from PostgreSQL when it's on.
- **Replaces in the GUI patch:** the `--gui` branches in its copy of `check.py` that skip the Textual table. Its `gui_checker` can call `gather_rows`, then filter and normalise the rows as it does now.

### `process_user_batch(username, model_id, media_list, post_list, row_list)`

Downloads one creator's rows from a check table, retries the failed ones once after refreshing their posts, and returns the batch's totals as a dict:

- `videos`, `audios`, `photos`: downloaded files.
- `forced`: skipped because the file was already there.
- `failed`: rows still failed after the retry.
- `bytes`: bytes downloaded.

They are added up over both passes. Each `process_dicts` call starts its own counts again, so a caller can't read them afterwards.

- `row_list` holds `(key, row)` pairs. Each row's state is reported through `ofscraper.classes.table.app.app.update_cell_state(key, state, style)`, with `state` one of `[downloaded]`, `[skipped]`, `[failed]`, `[stopped]` or `[added]`. A GUI without the Textual table sets `app.app` to an object with that method.
- `_process_user_batch` is the same function under its old name, kept for the GUI patch.
- **PostgreSQL:** no difference; downloads record to whichever database is in use.
- **Replaces in the GUI patch:** its copy's `_process_user_batch`, which returns a stats dict with the same keys. The patch's `workflow.py` calls `_process_user_batch` and reads those keys.

## Auth

### `auth_status()`

In `ofscraper/data/api/init.py`. Sync. Checks the auth and returns `(status, message)`:

- `UP`: the auth works (always, for an anonymous run).
- `DOWN`: the auth was rejected. Also for any error that `unavailable_message` doesn't recognise.
- `UNAVAILABLE`: the auth couldn't be checked: a network or proxy failure, a server error, a reply that isn't JSON, or no usable dynamic rule (the cases `unavailable_message` lists below). `message` says why, for a caller with no log to point to.

`message` is None for `UP` and `DOWN`. `getstatus()` returns only the status.

`check_auth()` in `ofscraper/utils/checkers.py` uses it. On `UNAVAILABLE` it raises `AuthCheckUnavailable("Couldn't check the auth: <message>")`. When the user picks "Go to Main Menu" in the auth prompt it raises `AuthCheckLeft`.

- **PostgreSQL:** not involved.
- **Replaces in the GUI patch:** the `last_unavailable_message` global in its copy of `data/api/init.py`, and the code in its copy of `utils/checkers.py` that reads it. That copy also returns without prompting in GUI mode, which the core doesn't do.

### `unavailable_message(e)`

In `ofscraper/data/api/init.py`. Sync. `unavailable_message(e: Exception) -> str | None` returns a one-sentence message for a failure that says nothing about the auth, else None. It covers httpx errors (the auth check) and aiohttp errors (the async session):

- a proxy that refused the tunnel;
- connection failures and timeouts, including aiohttp's total timeout;
- a certificate that couldn't be verified;
- 429 and 5xx replies;
- `DynamicRuleUnavailable` (see below);
- a reply that isn't JSON. A 4xx reply that isn't JSON is left to the auth check.

**Replaces in the GUI patch:** its copy of the function in `data/api/init.py`, which lacks the proxy refusal (`aiohttp.ClientHttpProxyError`), certificate, aiohttp total-timeout, `aiohttp.ClientPayloadError` and `aiohttp.ContentTypeError` cases. The patch's `gui/utils/auth_errors.py` already imports it from `ofscraper.data.api.init`.

### Dynamic rule fallback

`get_request_auth()` in `ofscraper/utils/auth/request.py` tries the chosen dynamic rule source first. If it can't be reached, returns an error, or sends a rule that can't be used, it tries the sources in `FALLBACK_SOURCES` (`digitalcriminals`, `rafa`, `xagler`), skipping the one already tried, and logs at info level which one it used and why. An unknown or removed rule name falls back the same way, with the reason logged.

If no source gives a usable rule, it raises `DynamicRuleUnavailable`. Its message lists each source's reason and says it isn't an auth problem, and `.failures` holds the `(source, error)` pairs. Nothing is cached then, so the next request tries again. The sessions don't retry it, and `auth_status()` reports it as `UNAVAILABLE`.

- **Replaces in the GUI patch:** the fallback in its copy of `utils/auth/request.py` (digitalcriminals, then riley). The copy also reads `advanced_options.dynamic_rules_manual` and `dynamic_rules_url` from `config.json`. The core has no such keys; the `manual` and `generic` rules come from environment defaults (see [env.md](env.md)).

## Purchased content

### `resolve_paid_username(model_id)`

In `ofscraper/data/posts/post.py`. `async`, not wrapped in `@run`. Returns the username for a creator in the purchased-content list. For a deleted account it returns the name the database recorded, else the `DELETED_MODEL_PLACEHOLDER` environment default (`modeldeleted` unless changed) followed by `_<model_id>`. `process_all_paid` uses it.

- **PostgreSQL:** the recorded name is read through the database operations, so it comes from PostgreSQL when it's on.
- **Replaces in the GUI patch:** the same function in its copy of `data/posts/post.py`.

## Database reads

These are in `ofscraper/db/operations_/media.py`. Call them with keyword arguments: `model_id=` and `username=` for the creator. Pass both: on SQLite the `metadata` path is built from them. Don't pass `conn=`: the wrapper opens the connection itself and raises `TypeError` if one is given.

| Function | Sync | Returns |
|---|---|---|
| `get_all_medias(model_id, username)` | async | a list of dicts, one per media row of every area |
| `get_all_medias_sync(model_id, username)` | sync | the same rows, from the same query |
| `get_post_info(model_id, username)` | sync | `{post_id: {"price": ..., "text": ...}}` for the creator's posts, messages and stories. An empty value is None. Where a post, a message and a story share an id, the first of those three tables keeps it. |
| `get_media_post_files_downloaded(model_id, username, media_id=None)` | sync | `{(media_id, post_id): (directory, filename)}` for downloaded media. Directory and filename are None when no file was recorded. `media_id` limits it to one media. |
| `get_media_ids_downloaded_model_sync(model_id, username, without_permanent_skips=False)` | sync | the set of the creator's downloaded media ids. `without_permanent_skips` leaves out the permanent `skip_download_script` skips. |

- **Which database:** `backend_for` in `ofscraper/db/operations_/wrapper.py` picks it for each call. With PostgreSQL on, the call reads the current site's schema and only that creator's rows. With it off, it opens the creator's `user_data.db` at the `metadata` path. A call given `db_path=` always opens that SQLite file, whichever is on.
- **`read_only=True`** opens the database read-only. A creator with no `user_data.db` then raises `DatabaseMissing` (`ofscraper/db/operations_/wrapper.py`) instead of getting a new file. With PostgreSQL on, tables that aren't there yet raise it too.
- **Replaces in the GUI patch:** the GUI's own reads of `user_data.db`, which see only the files. [POSTGRESQL.md](../POSTGRESQL.md#what-doesnt-work-with-it-yet) says which GUI part can use which function.

### PostgreSQL helpers

- **`ofscraper.db.postgres.enabled()`:** True when `OFSC_DATABASE_URL` is set. It's read through `of_env.getattr`, so an env file named in `config.json` counts.
- **`ofscraper.db.postgres.describe(database_url=None)`:** the server and database the URL names, without the login (`host:port/dbname`), for messages. It gives `the configured database` when it can't read the URL for certain.
- **`ofscraper.db.postgres.sqlite_files_notice(tool)`:** the sentence a tool that still works on `user_data.db` files shows while PostgreSQL is on. The caller checks `enabled()` first. Merge Databases shows it.
- **`ofscraper.utils.profiles.manage.postgres_profiles_notice()`:** with PostgreSQL on, prints that every profile uses the same database. The profile menu calls it after switching the active or default profile.

## Fixes that replace copied code

These aren't hooks, but they make a change in the GUI patch's copies unnecessary.

- **One `sess` cookie on sync requests (#607):** a request's own cookies now replace the httpx client's copies of the same names for that request, as aiohttp already did. The client's cookie jar is unchanged. This covers the `self._session.cookies.clear()` before each sync request in the patch's copy of `managers/sessionmanager/sessionmanager.py`.
