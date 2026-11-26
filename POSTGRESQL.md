# Using PostgreSQL

By default, the scraper stores each creator's data in a separate SQLite file (`user_data.db`). That requires no extra setup and remains the default.

Optionally, you can store every creator's rows in one PostgreSQL database instead. This is useful if you want a single place to query and back up, or if you run the scraper on more than one machine against the same library. When two runs save the same post, message, media, story, or label at the same time, the second run keeps the first run's row and continues.

## What you need

- **PostgreSQL 15 or newer**, with a database where the scraper's login can create tables.
- **The PostgreSQL driver** (psycopg). It comes with the scraper on Windows (x64), macOS and 64-bit Linux (x86_64, aarch64, ppc64le, riscv64), whether installed with pip, Docker or a standalone download.

  On other systems, such as Windows on ARM or Android, the first run with `OFSC_DATABASE_URL` set offers to install it when it runs at a terminal (the daemon, cron and `sudo` runs print the command instead). If that install is declined, fails or is turned off (`OFSC_INSTALL_EXTRAS=False`), install it yourself:
  ```bash
  pip install "ofscraper[postgres]"
  ```

## Turning it on

Set `OFSC_DATABASE_URL` to your database address:

```text
OFSC_DATABASE_URL=postgresql://user:password@host:5432/database
```

- If a special character in the password breaks the URL, percent-encode it (for example, `@` becomes `%40`).
- PostgreSQL's keyword form (`host=... user=... password=...`) also works. Quote passwords that contain spaces (`password='a b'`), or use the URL form above.

You can set `OFSC_DATABASE_URL` in either of these places:

- **An environment variable.** In `docker-compose.yml`, add it under `environment:`.
- **A `.env` file** listed under `advanced_options.env_files` in `config.json`.

Leave `OFSC_DATABASE_URL` unset or empty to keep using SQLite files.

**Note:** `OFSC_DATABASE_URL` is not a `config.json` setting because it contains a password. The `advanced_options.database_url` entry in `config.json` is only a placeholder note pointing here; anything written there is ignored, replaced, and logged with a warning. The password is never written to the log.

At startup, the scraper connects once and logs which server it is using. If it cannot connect (no server, a refused login, no such database, or a server older than PostgreSQL 15), it stops immediately with one sentence saying why.

## Bringing your existing databases in

Turning PostgreSQL on does not migrate your existing `user_data.db` files. Use `postgres_import` to bring them in:

1. **Close the scraper.** Any file written to while it is being copied is refused.
2. **Run a dry run** to preview what will be imported:
   ```bash
   python -m ofscraper.commands.postgres_import <folder>
   ```
   `<folder>` is searched for `user_data.db` files (your profile's `.data` folder is the usual one), and `OFSC_DATABASE_URL` sets the target database, as above. Without `--apply`, nothing is written to PostgreSQL; the command only reports how many files, creators, and rows it found for each site, plus anything blocking the import.
3. **Apply the import:**
   ```bash
   python -m ofscraper.commands.postgres_import <folder> --apply
   ```

| Option | What it does |
|---|---|
| `--apply` | Writes the imported rows to PostgreSQL. Without it, the command only previews and reports. |
| `--staging <folder>` | Sets where temporary working copies are placed. Working copies need as much free space as the source files. |
| `--skip-bad-files` | Imports the files that can be imported and skips (and lists) the ones that cannot. Exits with code `1` if any file was skipped, or `0` only if every file came in. |

### How import works

- **Your files are never changed.** Each file is copied to a working folder and upgraded the same way a scan upgrades it, so files last used by an older version come in too.
- **All or nothing.** Every file goes in together. If anything fails partway through, PostgreSQL keeps none of it and you can run the command again.
- **Separated by site.** Each file goes into its site's tables (OnlyFans or Fansly).
- **One file per creator.** If two files hold rows for the same creator (for example, after a rename or a changed `metadata` setting), combine them with **Merge Databases** first. With PostgreSQL on, Merge Databases prints the `postgres_import` command for the folder it wrote the merged file to.
- **No duplicate imports.** A creator that PostgreSQL already has rows for is refused so a file cannot be imported twice. Creators not in PostgreSQL yet can be imported later.
- **Username history and dates.** A creator's names come with the dates they were seen when the file has them:
  - If PostgreSQL already has a name for that creator (because the scraper started on the creator there without saving content yet), that row is kept and its dates are widened to keep the earlier first-seen date and the later last-seen date. A date is never emptied, and because no new row is added, it is not counted in rows added.
  - A deleted account uses the name seen last, so an imported name with a newer date than any PostgreSQL has becomes that name.
- **Invalid values stop the file.** A file is blocked if a column holds a value PostgreSQL cannot store (a non-numeric ID, a yes/no column holding something else, or an unreadable date), or if two rows collide once a missing creator is filled in. Each problem is listed with its table, row, and column. Empty dates become empty.

Afterwards, the scraper no longer uses your `user_data.db` files. Keep them anyway as a backup from before the switch.

## Going back to SQLite files

Unsetting `OFSC_DATABASE_URL` returns to your existing `user_data.db` files as they were before the switch, without anything scraped since. To write what PostgreSQL holds back to SQLite files first, use `postgres_export`:

1. **Close the scraper.** Anything the scraper saves while the export runs is not included in the exported files.
2. **Run a dry run** to preview the export:
   ```bash
   python -m ofscraper.commands.postgres_export <folder>
   ```
   Without `--apply`, nothing is written; the command reports how many creators and rows it found and which creators already have a file in `<folder>`.
3. **Write the files:**
   ```bash
   python -m ofscraper.commands.postgres_export <folder> --apply
   ```

Each creator with rows in PostgreSQL gets a file at `<folder>/<creator_id>/user_data.db`. This matches a profile's `.data` folder layout unless you changed the `metadata` setting; if you did, move each file to where your setting puts it. `OFSC_DATABASE_URL` sets which database is read, as above.

| Option | What it does |
|---|---|
| `--apply` | Writes the `user_data.db` files. Without it, the command only previews and reports. |
| `--site onlyfans` or `--site fansly` | Exports one site at a time. Required when PostgreSQL has rows for both sites; give each site its own folder because the same ID can belong to a different creator on each site. |

### How export works

- **PostgreSQL is only read.** Everything in PostgreSQL remains as it was beforehand.
- **Existing files are never overwritten.** If a creator already has a `user_data.db`, or a leftover `user_data.db-wal` or `user_data.db-journal` file, that creator is skipped and listed while the others are written.
  - To export a skipped creator, run the command again with an empty folder so you have both files.
  - If you imported the old file into PostgreSQL before, the new file holds everything and can replace it. If you did not, combine the two files with **Merge Databases**.
- **Files that appear mid-run are also left alone**, and their creators are listed. This is guaranteed on Windows and on any filesystem that supports hard links (most do). On Linux or macOS filesystems without hard links (such as FAT, exFAT, or some network shares), the command checks for the file and then renames its output, so a file created by another program in between is replaced. That is another reason not to run the scraper during export.
- **Every file is complete or absent.** Each file is written beside its target path as `user_data.db.<letters>.partial` and renamed only once complete. Stopping a run (including with Ctrl-C) removes the in-progress file and leaves no half-written `user_data.db`. You can run the command again and already-written files are skipped. A `.partial` file is left only if the process was killed, or on Windows if another program held it open; it is safe to delete.
- **Current schema.** Each file is built by the same code that creates a new creator's database, so it has the current tables and every upgrade step applied.
- **Checked before renaming.** Before a file gets its final name, it is verified to hold the exact rows PostgreSQL returned and to be readable by `postgres_import`. A creator whose file fails this check is listed with the reason and gets no file.
- **Values SQLite cannot store stop that creator's file.** Each bad value is listed with its table, row number (its position among that creator's rows in that table, oldest first), column, and value. That creator gets no file until you fix the value in PostgreSQL and run the command again. Such values are rare, though import lets a few in: a numeric media, post, or label ID that is not a whole number (`1.5`, `1e20`), which SQLite would store as a different value, or a whole number of `2^63` or larger that SQLite has no room for.

### Differences from your original SQLite files

Exported files contain what the scraper reads from PostgreSQL. For files you previously imported, the rows are the same with these differences:

| Item | How it appears in the exported `user_data.db` |
|---|---|
| **Dates** | Same moment, written in UTC (`2024-03-01T09:30:00+00:00`), regardless of the old file's format (another offset, no offset, or seconds). Anything finer than a millionth of a second is rounded. |
| **Merged name dates** | For a name PostgreSQL already had at import time, the dates combine both sides: the earlier first-seen date and the later last-seen date. Dates written by the scraper since import are included too. |
| **Empty text in typed columns** | Stored as `NULL` in every number, yes/no, or date column (such as a post's price, a media's size, a message's `user_id`, or a label's `post_id`). Text columns keep empty text. |
| **Yes/no values** | Stored as `1` or `0`, however the old file wrote them (for example, `true` or `FALSE`). |
| **Large whole-number prices** | Prices above `2^53` (`9,007,199,254,740,992`) come back rounded, because the scraper reads prices from PostgreSQL as a number with a fraction. |
| **Bytes (`BLOB`)** | Come back as text. In a media, post, or label ID, bytes that spell a whole number come back as that number (`12`). |
| **Missing creator ID** | A row that named no creator now names the file's creator. |
| **Row `id`** | Set to the row's position among the creator's rows, oldest first. In a single-creator file this is usually the `id` it had; where it differs, an undo file written by `recover_collisions` for the old file no longer matches its rows. |
| **Other creators' rows** | Removed from the file. A file that held several creators comes back as one file per creator, each in its own folder. That goes for a single `models` or `profiles` row too. |
| **`models` row** | Every exported file has its creator's row in `models`, even when the old file did not. |
| **Not carried over** | Rows you added to `schema_flags` (each file gets only the upgrade steps of the version that writes it), custom indexes, and non-scraper tables. A file that held only `profiles` and `models` rows was never imported, so it does not come back. |

## Syncing to Stash

`stash_sync` (see [STASH.md](STASH.md)) reads from PostgreSQL when you pass `--postgres` instead of paths to `user_data.db` files:

```bash
python -m ofscraper.commands.stash_sync --postgres
```

**Note:** `stash_sync` is a separate tool and doesn't read the scraper's settings (`config.json`). Set `OFSC_DATABASE_URL` in the environment where you run the command; an address listed only in a `.env` file referenced by `config.json` is not seen. In Docker, a variable set under `environment:` is already set for commands run in the container. The PostgreSQL driver is also required.

- **Filtering creators.** Every creator on both sites is synced by default. Narrow the run with:
  - `--site onlyfans` or `--site fansly` to sync one site.
  - `--creator <username or id>` (repeatable) to sync matching creators. It matches IDs on either site and any username a creator has had, in any case, so one value can match more than one creator.
- **PostgreSQL is only read.** The command opens one read-only connection, reads the database as it was when reading started, and closes the connection before sending anything to Stash. The login only needs `USAGE` on each site's schema and `SELECT` on its tables.
- **Read timeouts.** A read that waits more than 30 seconds for a locked table, or takes more than 5 minutes, is ended by the server and stops the command.
- **Differences from SQLite sync.** A few results differ from reading `user_data.db` files; see [STASH.md](STASH.md) for the list.
- **Passing `user_data.db` files.** Still reads those files. If `OFSC_DATABASE_URL` is set, the command notes that the files hold nothing scraped since PostgreSQL was turned on. Passing files and `--postgres` together is refused.
- **Connection errors.** If the server is not running, the login is refused, the database does not exist, the driver is missing, or the login cannot read a site's tables, the command stops with one sentence and exit code `1` before contacting Stash. The message names the host, port, and database, never the password.

## Recovering filename collisions

`recover_collisions` (see [COLLISION_RECOVERY.md](COLLISION_RECOVERY.md)) works on PostgreSQL when you pass `--postgres` and `--creator` instead of a `user_data.db` path:

```bash
# Preview changes (read-only)
python -m ofscraper.commands.recover_collisions --postgres --creator <username or id>

# Apply changes and save an undo file
python -m ofscraper.commands.recover_collisions --postgres --creator <username or id> --apply --undo-dir <folder>

# Restore changes from an undo file
python -m ofscraper.commands.recover_collisions --postgres --creator <username or id> --undo <undo file> --apply
```

Like `stash_sync --postgres`, it reads `OFSC_DATABASE_URL` from the environment it is run in and requires the PostgreSQL driver. Given a `user_data.db` path instead, it still works on that file (and notes if `OFSC_DATABASE_URL` is set that the file holds nothing scraped since PostgreSQL was turned on). Passing a file and `--postgres` together is refused.

### Selecting a creator

- **One creator at a time.** `--creator` accepts a username or ID and must match exactly one creator. If more than one matches (an ID on both sites, an ID that is another creator's username, or a username two creators have had), the command changes nothing and lists the matches. Narrow it with `--site onlyfans` or `--site fansly`, or a username or ID unique to one creator.
- **Check the report before `--apply`.** The report prints the resolved `creator` (site, ID, and last-saved username). Check it before applying, because a number can be one creator's ID and another's username.
- **Scoped to one creator.** Only that creator's rows in that site's tables are read and changed. As with files, media from two different creators sharing a path are not checked.

### Running safely

- **Run where the scraper runs.** In Docker, run the command inside the scraper's container so recorded paths match the files. Paths recorded on another operating system (Windows paths read on Linux, or the reverse) are refused. `--path-root` applies to relative recorded paths only, as before.
- **Close the scraper first.** Unlike a SQLite file, PostgreSQL does not lock the scraper out. If the scraper changes one of the rows while the command runs, the command changes nothing and tells you; close the scraper and run it again. Rows saved by the scraper for the first time during the run are not seen by the command, so a post saved meanwhile for a media being reset keeps its download flag.
- **Avoid transaction-mode connection poolers.** Behind a pooler that hands each transaction to a different server connection (such as PgBouncer in transaction mode), the time zone and timeouts set by the command may not hold. Give it the server's own address instead.

### Preview, apply, and undo

- **Same changes as SQLite.** Without `--apply`, it runs over a read-only connection and reports what it found. With `--apply`, it resets the same download flags it would in a `user_data.db` with the same rows, and `--undo <file>` sets them back.
- **`--apply` requires `--undo-dir <folder>`.** The undo file is the only way back, so choose a folder that is kept. Passing `--undo-dir` on a preview checks that the folder exists and can be written to. The report prints the undo file's full path. **In Docker, give a mounted folder:** a folder inside the container is gone when the container is removed.
- **Failure handling:**
  - *Before saving to PostgreSQL:* The undo file is written first. If it cannot be written, or anything fails or stops before changes are saved, no rows are changed and the undo file is removed.
  - *While saving to PostgreSQL:* Once saving begins, the undo file is kept no matter what happens. If the connection is lost or you press Ctrl-C at that moment, the command cannot know whether the server kept the changes. It says so and prints where the undo file is; run `--undo <that file>` without `--apply` to see whether anything needs restoring.
- **What the undo file stores:** Each row by its media and post IDs, what the row held, and the server and database it was made on (not the login).
- **All-or-nothing restore.** `--undo` restores every row in the undo file or none. Unlike SQLite mode (which skips rows that no longer fit), PostgreSQL mode stops. It refuses if the creator or site does not match, or if any row has changed since recovery (for example, its media was downloaded again under another name); the error says if the undo file was made on a different database. An undo file written for a `user_data.db` only fits that file, even after the file is imported into PostgreSQL; one written from PostgreSQL only fits PostgreSQL.
- **Undo validation.** An undo file is trusted as far as the rows agree with it. As with files, a hand-edited undo file can mark as downloaded a row the recovery never touched: only for that creator, only changing from not downloaded to downloaded, and only when the row's folder, file name, size, and hash match the undo file.

## Moving a creator's files

`move_creator_files` (see [MOVING_FILES.md](MOVING_FILES.md)) works on PostgreSQL when you pass `--postgres --creator <username or id>` instead of a `user_data.db` path, plus `--site` if more than one creator matches.

- **Same lookup and moves.** It finds the database and creator the same way `recover_collisions --postgres` does above, and moves the same files it would for a `user_data.db` with the same rows.
- **Close the scraper first.** PostgreSQL does not lock the scraper out the way a SQLite file does.
- **One transaction at the end.** Rows are updated in a single transaction saved at the end:
  - If the scraper changed one of those rows meanwhile, no rows are changed, and files moved so far stay at their new places.
  - If the connection is lost while changes are being saved, it is unknown whether they were kept.
  - Either way, run the same command again to finish.

## What is different

- **One database for every creator.** Each site gets its own schema (`onlyfans`, `fansly`) holding the same tables a `user_data.db` has. Every row carries its creator's `model_id`.
- **One database for every profile.** Schemas are per site, not per profile, so switching profiles does not switch your data. The scraper tells you this when you switch.
- **Native column types.** IDs are 64-bit numbers (media, post, and label IDs are text, because a few are words or hashes). Yes/no columns are booleans and dates are timestamps, so other tools can query the database directly.
- **Already-downloaded checks stay per creator.** The scraper skips media already marked as downloaded. Just like per-creator SQLite files, only that creator's own rows count. Media is never skipped because another creator has it. (`--force-model-unique` therefore changes nothing here.)
- **No automatic backup copies.** The scraper backs up a SQLite file before upgrading it. For PostgreSQL, back up with `pg_dump`.
- **New versions add new columns on startup.** Tables created by an earlier version automatically get columns added since (so far, `first_seen_at` and `last_seen_at` in `profiles` for when each creator name was seen). Existing rows stay as they are with empty values in the new columns. The login must own the tables, as it does when the scraper created them. Because `postgres_export` is read-only, it adds nothing; columns the tables do not have yet come out empty.
- **Your SQLite files are left alone.** They are not read, changed, or deleted while PostgreSQL is on.

## What doesn't work with it yet

- **Existing libraries start empty** until you import your `user_data.db` files (see [Bringing your existing databases in](#bringing-your-existing-databases-in)). Until then, the scraper treats everything as new.
- **Tools that read `user_data.db` files** keep reading those files and do not see PostgreSQL: Merge Databases and parts of the GUI patch. Nothing scraped since you turned PostgreSQL on is in those files, and what a tool changes in them does not reach PostgreSQL.
  - **Merge Databases** says so on its screen.
  - **GUI patch:**
    - *Uses PostgreSQL:* scraping, downloads, metadata updates, and the check tables go through the scraper, so they use PostgreSQL.
    - *Reads `user_data.db` directly (without warning):* these features only see the old SQLite files until updated to call the scraper's database functions (see [reference/hooks.md](reference/hooks.md#database-reads)):

      | GUI feature | Scraper function to use | Notes |
      |---|---|---|
      | **Results table** | `get_all_medias_sync` (media), `get_post_info` (post price and text) | |
      | **Purge** (deletes downloaded files) | `get_media_post_files_downloaded` | Also deletes the creator's `user_data.db`; with PostgreSQL on, the creator's rows in PostgreSQL stay. |
      | **Showing only what is new since the last run** | `get_all_medias_sync` | Take the newest non-empty `posted_at` from its rows; this matches the newest `posted_at` in a SQLite file. |

    - *SQLite-only by design:* the GUI's Merge Databases and the download paths it updates when moving the OnlyFans folder work on `user_data.db` files by design, so with PostgreSQL on they change only those files.
- **Standalone tools that do work with PostgreSQL:** `stash_sync`, `recover_collisions`, `move_creator_files`, and `scripts/creator_names.py` all work on PostgreSQL when passed `--postgres`. Each reads `OFSC_DATABASE_URL` only from the environment it is run in (doesn't read the scraper's settings), and warns when given files while PostgreSQL is on:
  - See [Syncing to Stash](#syncing-to-stash), [Recovering filename collisions](#recovering-filename-collisions), and [Moving a creator's files](#moving-a-creators-files) above.
  - For `scripts/creator_names.py`:
    ```bash
    python scripts/creator_names.py --postgres [--site onlyfans|fansly]
    ```
    All of its usual options work (`--all`, `--find`, `--csv`, `--add MODEL_ID NAME [--seen DATE] [--force]`).

## Developing

### Live tests

Live tests run against a real PostgreSQL server and are skipped unless `OFSC_TEST_POSTGRES_URL` names a server they may use. Each test creates and drops its own schemas. CI runs them against PostgreSQL 15 to 19.

| Test file | What it tests |
|---|---|
| `test/test_db_postgres_live.py` | Core database engine |
| `test/test_postgres_import_live.py` | `postgres_import` |
| `test/test_postgres_export_live.py` | `postgres_export` |
| `test/test_stash_sync_postgres_live.py` | `stash_sync --postgres` |
| `test/test_collision_recovery_postgres_live.py` | `recover_collisions --postgres` |
| `test/test_move_creator_files_postgres_live.py` | `move_creator_files --postgres` |
| `test/test_creator_names_postgres_live.py` | `scripts/creator_names.py --postgres` |
| `test/test_postgres_server_checks_live.py` | Two runs writing at once and `remove_hash_match` |

### Architecture and schema changes

- **Shared SQL and backend selection:** Database operations in `ofscraper/db/operations_/` write their SQL once for both engines. `backend_for` in `ofscraper/db/operations_/wrapper.py` picks the engine for each call: PostgreSQL when `OFSC_DATABASE_URL` is set, and SQLite otherwise. A call given `db_path=` always works on that SQLite file (used by Merge Databases and single-file upgrades). `ofscraper/db/postgres.py` converts `?` placeholders to the driver's format and sets the schema to the current site's.
- **Adding columns:** A column added to a SQLite table must also be added to `TABLES` in `ofscraper/db/postgres.py`, along with an entry in `ADDED_COLUMNS` so existing PostgreSQL databases get upgraded. At each start, `create_tables` checks which of those columns are missing and adds them. `test/test_db_postgres.py` fails until SQLite and PostgreSQL match.
