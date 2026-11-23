# Hooks for add-ons

Code that runs in the same process as the scraper, such as the GUI patch or a plugin, can use the functions and events on this page instead of shipping changed copies of the scraper's files. Each entry gives the module, how to call it, what it gives back, and, where it matters, how it behaves with PostgreSQL on. The [GUI patch migration map](#gui-patch-migration-map) at the end says which part of the GUI patch's copied files each one can replace.

This file is written by hand. Check an entry against the code before relying on it.

## Contents

- [Quick reference](#quick-reference)
- [Calling async code](#calling-async-code)
- [Downloads](#downloads)
- [Check tables](#check-tables)
- [Auth](#auth)
- [Purchased content](#purchased-content)
- [Database reads](#database-reads)
- [GUI patch migration map](#gui-patch-migration-map)

## Quick reference

| Hook | Module | Call from | Purpose |
|---|---|---|---|
| [`subscribe` / `unsubscribe`](#download-events) | `ofscraper.utils.events` | sync code | follow saved and finished downloads |
| [`stop.request()` / `stop.clear()`](#stopping-downloads) | `ofscraper.commands.scraper.actions.download.stop` | sync code, any thread | stop running downloads and post fetches |
| [`gather_rows(command)`](#gather_rowscommand) | `ofscraper.commands.check` | worker thread with no running loop | get check-table rows without the Textual table |
| [`reset_table_data()`](#gather_rowscommand) | `ofscraper.commands.check` | sync code | forget the last scan's rows |
| [`process_user_batch(...)`](#process_user_batchusername-model_id-media_list-post_list-row_list) | `ofscraper.commands.check` | worker thread with no running loop | download one creator's check-table rows |
| [`auth_status()`](#auth_status) | `ofscraper.data.api.init` | sync code | check the auth and say why it couldn't be checked |
| [`check_auth(include_main_menu=False)`](#check_authinclude_main_menufalse) | `ofscraper.utils.checkers` | sync code | check the auth, prompting when it's rejected |
| [`unavailable_message(e)`](#unavailable_messagee) | `ofscraper.data.api.init` | sync code | tell a network or server failure from an auth failure |
| [`get_request_auth()`](#dynamic-rule-fallback) | `ofscraper.utils.auth.request` | sync code | get a dynamic rule, falling back to other sources |
| [`resolve_paid_username(model_id)`](#resolve_paid_usernamemodel_id) | `ofscraper.data.posts.post` | async code | username for a purchased-content creator |
| [Database reads](#database-reads) | `ofscraper.db.operations_.media` | sync or async code (see the table) | read a creator's media, posts and downloads |
| [PostgreSQL helpers](#postgresql-helpers) | `ofscraper.db.postgres`, `ofscraper.utils.profiles.manage` | sync code | tell whether PostgreSQL is on, and its notices |

## Calling async code

- **Sync functions** run on the calling thread and block it until they return.
- **`async def` functions** must be awaited. From sync code, call them from a thread that has no running event loop, with `asyncio.run(...)`. From another thread while a loop runs elsewhere, use `asyncio.run_coroutine_threadsafe(coro, loop).result()`.
- **Functions wrapped in `@run`** (`ofscraper.utils.context.run_async`) run the coroutine to the end when the thread has no running loop. Inside a running loop they return the coroutine unawaited, so the work doesn't happen unless the caller awaits it. Call them from a worker thread, not from a loop's thread.

## Downloads

### Download events

**Module:** `ofscraper.utils.events` · **Execution:** sync; subscribers run in the download's own thread and event loop · **Returns:** None

`subscribe(name, fn)` calls `fn` on every `name` event, and `unsubscribe(name, fn)` stops it. Subscribing the same function again does nothing. `subscribe` raises `ValueError` for an unknown name; `unsubscribe` ignores a name or function it doesn't know.

```python
import queue
from ofscraper.utils import events

saved = queue.Queue()
events.subscribe("item_downloaded", lambda ele, path: saved.put((ele, path)))
```

Subscribers get these keyword arguments:

| Event | Arguments | Sent when |
|---|---|---|
| `item_downloaded` | `ele`, `path` (a `pathlib.Path`) | a media file has been saved at `path` and recorded in the database |
| `item_finished` | `ele`, `username`, `result`, `reason` | the download loop has counted one item |

- `item_downloaded` is sent before `after_download_script` runs, and a stop during the script still counts the item as downloaded.
- It's sent for normal files, DRM videos and Fansly HLS/DASH streams.
- The Fansly check of videos saved without sound runs after a run's downloads. When it saves a video again with sound, it also sends `item_downloaded`, with no `item_finished` after it.
- An item cancelled by a stop before it starts gets no `item_finished`.

`item_finished`'s `result` and `reason`:

| `result` | `reason` |
|---|---|
| `downloaded` | None |
| `stopped` | None |
| `skipped` | `size limit`, `skip_download_script`, `CDM keys not found`, `protected stream`, or `skipped` |
| `failed` | `no link` (locked or removed media), the error's text, or `download failed` when there's no error |

Note on error text: links (including JSON-escaped and percent-encoded ones) are removed. A link without a scheme keeps its address but drops everything after the `?`. Cookies and the home folder's name are hidden as in the logs.

A subscriber can be a plain function or an `async def` one. An error in a subscriber is logged at debug level and doesn't affect the download.

> ⚠️ **A subscriber holds up the download.** It runs in the download's own thread and event loop and holds up that download until it returns. A GUI should hand the event to its own thread and return.

**PostgreSQL:** no difference. `item_downloaded` is sent after the row is saved, to whichever database is in use.

### Stopping downloads

**Module:** `ofscraper.commands.scraper.actions.download.stop` · **Execution:** sync, from any thread · **Returns:** None

`stop.request()` stops the running downloads and post fetches. `stop.requested` is the `threading.Event` it sets, and `stop.clear()` clears it. A scrape and the check commands clear it when they start.

```python
from ofscraper.commands.scraper.actions.download import stop

stop.request()  # from any thread
stop.clear()    # before the next scan
```

> ⚠️ **`stop.DownloadsStopped` is a `BaseException`.** After a `stop.request()`, post fetches (in both scrapes and check scans) raise it, and a scrape raises it once a creator's downloads have stopped. `except Exception` doesn't catch it. A whole scrape run through `scraperManager.runner` catches it and, outside the menu, exits with `SystemExit(130)` instead.

## Check tables

### `gather_rows(command)`

**Module:** `ofscraper.commands.check` · **Execution:** sync, uses `@run` inside · **Returns:** a list of row dicts

Runs a check command's scan and returns the rows its table would show, without opening the Textual table or starting the table's download thread. The creators and areas come from the settings, as for the command. The check commands call it and then open the table, so a row is the same dict the table gets.

```python
from ofscraper.commands.check import gather_rows, reset_table_data
from ofscraper.commands.scraper.actions.download import stop

stop.clear()
reset_table_data()
rows = gather_rows("post_check")
```

| `command` | Result |
|---|---|
| `post_check`, `msg_check`, `paid_check`, `story_check` (except `story_check` on Fansly) | the rows of that check command's table |
| `story_check` on Fansly | logs an error and returns `[]` |
| anything else | raises `ValueError` |

- Call it from a worker thread with no running event loop: it runs `@run` functions inside.
- It checks the auth first with [`check_auth()`](#check_authinclude_main_menufalse), without arguments, so it can raise `AuthCheckUnavailable` or `SystemExit` (see its table), and a rejected auth opens the terminal's auth prompt.
- It doesn't clear a stop. Call `stop.clear()` first (see [Stopping downloads](#stopping-downloads)).

> ⚠️ **It changes settings for the whole process.** It sets `force_all` to True and `after` to 0 in the settings, as the check commands do. They stay that way for the rest of the process, so a scrape run after it in the same process gets them too.

> ⚠️ **Rows add to the last scan's.** Call `reset_table_data()` first for a new table.

**PostgreSQL:** the downloaded state and file names come from `get_media_post_files_downloaded`, so they come from PostgreSQL when it's on.

### `process_user_batch(username, model_id, media_list, post_list, row_list)`

**Module:** `ofscraper.commands.check` · **Execution:** sync, uses `@run` inside · **Returns:** a dict of the batch's totals

Downloads one creator's rows from a check table, retries the failed ones once after refreshing their posts, and returns the batch's totals.

```python
import ofscraper.classes.table.app as table_app
from ofscraper.commands.check import process_user_batch

table_app.app = my_table  # any object with update_cell_state(key, state, style)
totals = process_user_batch(username, model_id, media_list, post_list, row_list)
```

| Key | Counts |
|---|---|
| `videos`, `audios`, `photos` | downloaded files |
| `forced` | skipped because the file was already there |
| `failed` | rows still failed after the retry |
| `bytes` | bytes downloaded |

The totals are added up over both passes. Each `process_dicts` call starts its own counts again, so a caller can't read them afterwards.

- Call it from a worker thread with no running event loop: it runs `@run` functions inside.
- `row_list` holds `(key, row)` pairs. Each row's state is reported through `ofscraper.classes.table.app.app.update_cell_state(key, state, style)`, with `state` one of `[downloaded]`, `[skipped]`, `[failed]`, `[stopped]` or `[added]`. A GUI without the Textual table sets `app.app` to an object with that method.
- `_process_user_batch` is the same function under its old name, kept for the GUI patch.

**PostgreSQL:** no difference; downloads record to whichever database is in use.

## Auth

### `auth_status()`

**Module:** `ofscraper.data.api.init` · **Execution:** sync · **Returns:** `(status, message)`

Checks the auth. `getstatus()` returns only the status.

```python
from ofscraper.data.api.init import auth_status

status, message = auth_status()
if status == "UNAVAILABLE":
    print(f"Couldn't check the auth: {message}")
```

| `status` | Meaning | `message` |
|---|---|---|
| `UP` | the auth works (always, for an anonymous run) | None |
| `DOWN` | the auth was rejected; also any error that `unavailable_message` doesn't recognise | None |
| `UNAVAILABLE` | the auth couldn't be checked | why, for a caller with no log to point to |

`UNAVAILABLE` covers a network or proxy failure, a server error, a reply that isn't JSON, or no usable dynamic rule: the cases [`unavailable_message`](#unavailable_messagee) lists.

### `check_auth(include_main_menu=False)`

**Module:** `ofscraper.utils.checkers` · **Execution:** sync · **Returns:** None once the auth is `UP`

Checks the auth with `auth_status()`, and asks for new auth until it's `UP`. `include_main_menu=True` adds a "Go to Main Menu" choice to the auth prompt. [`gather_rows`](#gather_rowscommand) calls it without arguments.

```python
from ofscraper.utils.checkers import AuthCheckUnavailable, check_auth

try:
    check_auth()
except AuthCheckUnavailable as e:
    print(e)
```

| Raises | When |
|---|---|
| `AuthCheckUnavailable("Couldn't check the auth: <message>")` | `auth_status()` returned `UNAVAILABLE` |
| `AuthCheckLeft` | only with `include_main_menu=True`: the user picked "Go to Main Menu" in the auth prompt |
| `SystemExit(0)` | the user picked quit in the auth prompt |
| `SystemExit` (no code) | the auth was rejected with the `auth_fail` setting on: it quits without prompting, on OnlyFans and Fansly |

On Fansly the login prompt has no quit choice, so `check_auth()` asks again until the auth is `UP`.

> ⚠️ **A rejected auth opens a terminal prompt.** When the auth is rejected and `auth_fail` is off, `check_auth()` opens the terminal's auth prompt (`make.make_auth`; on Fansly its login prompt). The core does this in GUI mode too.

### `unavailable_message(e)`

**Module:** `ofscraper.data.api.init` · **Execution:** sync · **Returns:** `str | None`

`unavailable_message(e: Exception)` returns a one-sentence message for a failure that says nothing about the auth, else None. It covers httpx errors (the auth check) and aiohttp errors (the async session).

```python
from ofscraper.data.api.init import unavailable_message

try:
    ...
except Exception as e:
    message = unavailable_message(e)  # None: not a failure it recognises
```

| Failure it recognises | Note |
|---|---|
| a proxy that refused the tunnel | |
| connection failures and timeouts | includes aiohttp's total timeout |
| a certificate that couldn't be verified | |
| 429 and 5xx replies | |
| `DynamicRuleUnavailable` | see [Dynamic rule fallback](#dynamic-rule-fallback) |
| a reply that isn't JSON | a 4xx reply that isn't JSON is left to the auth check |

### Dynamic rule fallback

**Module:** `ofscraper.utils.auth.request` · **Execution:** sync · **Returns:** a usable dynamic rule, or raises `DynamicRuleUnavailable`

`get_request_auth()` tries the chosen dynamic rule source first. If it can't be reached, returns an error, or sends a rule that can't be used, it tries the sources in `FALLBACK_SOURCES` (`digitalcriminals`, `rafa`, `xagler`), skipping the one already tried, and logs at info level which one it used and why. An unknown or removed rule name falls back the same way, with the reason logged.

```python
from ofscraper.utils.auth.request import DynamicRuleUnavailable, get_request_auth

try:
    get_request_auth()
except DynamicRuleUnavailable as e:
    print(e.failures)
```

If no source gives a usable rule, it raises `DynamicRuleUnavailable`. Its message lists each source's reason and says it isn't an auth problem, and `.failures` holds the `(source, error)` pairs. Nothing is cached then, so the next request tries again. The sessions don't retry it, and `auth_status()` reports it as `UNAVAILABLE`.

## Purchased content

### `resolve_paid_username(model_id)`

**Module:** `ofscraper.data.posts.post` · **Execution:** async, not wrapped in `@run` · **Returns:** a username

Returns the username for a creator in the purchased-content list. For a deleted account it returns the name the database recorded, else the `DELETED_MODEL_PLACEHOLDER` environment default (`modeldeleted` unless changed) followed by `_<model_id>`. `process_all_paid` uses it.

```python
from ofscraper.data.posts.post import resolve_paid_username

username = await resolve_paid_username(model_id)
```

**PostgreSQL:** the recorded name is read through the database operations, so it comes from PostgreSQL when it's on.

## Database reads

**Module:** `ofscraper.db.operations_.media` · **Execution:** see the table · **Returns:** see the table

Call these with keyword arguments: `model_id=` and `username=` for the creator. Pass both: on SQLite the `metadata` path is built from them.

```python
from ofscraper.db.operations_.media import get_media_post_files_downloaded
from ofscraper.db.operations_.wrapper import DatabaseMissing

try:
    files = get_media_post_files_downloaded(model_id=model_id, username=username, read_only=True)
except DatabaseMissing:
    files = {}
```

| Function | Execution | Returns |
|---|---|---|
| `get_all_medias(model_id, username)` | async | a list of dicts, one per media row of every area |
| `get_all_medias_sync(model_id, username)` | sync | the same rows, from the same query |
| `get_post_info(model_id, username)` | sync | `{post_id: {"price": ..., "text": ...}}` for the creator's posts, messages and stories. An empty value is None. Where a post, a message and a story share an id, the first of those three tables keeps it. |
| `get_media_post_files_downloaded(model_id, username, media_id=None)` | sync | `{(media_id, post_id): (directory, filename)}` for downloaded media. Directory and filename are None when no file was recorded. `media_id` limits it to one media. |
| `get_media_ids_downloaded_model_sync(model_id, username, without_permanent_skips=False)` | sync | the set of the creator's downloaded media ids. `without_permanent_skips` leaves out the permanent `skip_download_script` skips. |

- **Don't pass `conn=`:** the wrapper opens the connection itself and raises `TypeError` if one is given.
- **Which database:** `backend_for` in `ofscraper.db.operations_.wrapper` picks it for each call. With PostgreSQL on, the call reads the current site's schema and only that creator's rows. With it off, it opens the creator's `user_data.db` at the `metadata` path. A call given `db_path=` always opens that SQLite file, whichever is on.
- **`read_only=True`** opens the database read-only. A creator with no `user_data.db` then raises `DatabaseMissing` (`ofscraper.db.operations_.wrapper`) instead of getting a new file. With PostgreSQL on, tables that aren't there yet raise it too.

### PostgreSQL helpers

**Module:** `ofscraper.db.postgres`, `ofscraper.utils.profiles.manage` · **Execution:** sync · **Returns:** see the table

```python
from ofscraper.db import postgres

if postgres.enabled():
    print(postgres.sqlite_files_notice("Merge Databases"))
```

| Function | Returns | What it does |
|---|---|---|
| `ofscraper.db.postgres.enabled()` | bool | True when `OFSC_DATABASE_URL` is set. It's read through `of_env.getattr`, so an env file named in `config.json` counts. |
| `ofscraper.db.postgres.describe(database_url=None)` | str | the server and database the URL names, without the login (`host:port/dbname`), for messages. Returns `the configured database` if the URL can't be parsed reliably. |
| `ofscraper.db.postgres.sqlite_files_notice(tool)` | str | the sentence a tool that still works on `user_data.db` files shows while PostgreSQL is on. The caller checks `enabled()` first. Merge Databases shows it. |
| `ofscraper.utils.profiles.manage.postgres_profiles_notice()` | None | with PostgreSQL on, prints that every profile uses the same database. The profile menu calls it after switching the active or default profile. |

## GUI patch migration map

What each hook can replace in the GUI patch's copied files, and what the copies do that the core doesn't.

| Hook | Replaces in the GUI patch's copies | Notes |
|---|---|---|
| [Download events](#download-events) | the `plugin_manager.dispatch_event("on_item_downloaded", ...)` calls in its copies of `main_download.py` and `alt_download.py`, and the failure tracking and table-cell updates in its copy of `download/run.py` | a subscriber can make the same `dispatch_event` call with `ele` and `str(path)` |
| [Stopping downloads](#stopping-downloads) | the `is_gui_cancelled()` checks in its copies of `download/run.py` and `downloadmanager.py` | |
| [`gather_rows`](#gather_rowscommand) | the `--gui` branches in its copy of `check.py` that skip the Textual table | its `gui_checker` can call `gather_rows`, then filter and normalise the rows as it does now. The patch's copy of `checkers.py` skips the auth prompt in GUI mode; the core doesn't. |
| [`process_user_batch`](#process_user_batchusername-model_id-media_list-post_list-row_list) | its copy's `_process_user_batch`, which returns a stats dict with the same keys | the patch's `workflow.py` calls `_process_user_batch` and reads those keys |
| [`auth_status`](#auth_status) | the `last_unavailable_message` global in its copy of `data/api/init.py`, and the code in its copy of `utils/checkers.py` that reads it | that copy also returns without prompting in GUI mode, which the core doesn't do |
| [`unavailable_message`](#unavailable_messagee) | its copy of the function in `data/api/init.py` | the copy lacks the proxy refusal (`aiohttp.ClientHttpProxyError`), certificate, aiohttp total-timeout, `aiohttp.ClientPayloadError` and `aiohttp.ContentTypeError` cases. The patch's `gui/utils/auth_errors.py` already imports it from `ofscraper.data.api.init`. |
| [Dynamic rule fallback](#dynamic-rule-fallback) | the fallback in its copy of `utils/auth/request.py` (digitalcriminals, then riley) | the copy also reads `advanced_options.dynamic_rules_manual` and `dynamic_rules_url` from `config.json`. The core has no such keys; the `manual` and `generic` rules come from environment defaults (see [env.md](env.md)). |
| [`resolve_paid_username`](#resolve_paid_usernamemodel_id) | the same function in its copy of `data/posts/post.py` | |
| [Database reads](#database-reads) | the GUI's own reads of `user_data.db`, which see only the files | [POSTGRESQL.md](../POSTGRESQL.md#what-doesnt-work-with-it-yet) says which GUI part can use which function |

### Fixes that replace copied code

These aren't hooks, but they make a change in the GUI patch's copies unnecessary.

- **One `sess` cookie on sync requests (#607):** a request's own cookies now replace the httpx client's copies of the same names for that request, as aiohttp already did. The client's cookie jar is unchanged. This covers the `self._session.cookies.clear()` before each sync request in the patch's copy of `managers/sessionmanager/sessionmanager.py`.
