# Using PostgreSQL

By default the scraper keeps one SQLite file (`user_data.db`) per creator. Nothing needs installing, and that stays the default.

As an option, it can keep every creator's rows in one PostgreSQL database instead. That is useful if you want one place to query and back up, or you run the scraper from more than one machine against the same library.

## What you need

- A PostgreSQL server, version 15 or newer, and a database on it that the scraper's login may create tables in.
- The PostgreSQL driver:
  - **pip:** `pip install "ofscraper-community[postgres]"`
  - **Docker:** the image already includes it.
  - **Standalone downloads** (the `.exe` and the other single files) don't include it. Use the pip or Docker install.

## Turning it on

Set `OFSC_DATABASE_URL` to the database's address:

```
OFSC_DATABASE_URL=postgresql://user:password@host:5432/database
```

Any of these works:

- An environment variable. In `docker-compose.yml`, add it under `environment:`.
- A line in a `.env` file that `advanced_options.env_files` in `config.json` names.

Leave it unset, or empty, to keep using SQLite files.

It is not a `config.json` setting, because it holds a password. `config.json` has a line, `advanced_options.database_url`, that only says so and points here; anything written there is ignored and replaced, with a warning that says so.

The password is never written to the log. If a special character in it breaks the address, percent-encode it (`@` is `%40`).

At startup the scraper connects once and says which server it is using. If it can't (no server, a refused login, no such database, a server older than 15), it stops there with one sentence saying which.

## Bringing your existing databases in

Turning PostgreSQL on doesn't move what your `user_data.db` files hold. A separate command does:

```
python -m ofscraper.commands.postgres_import <folder>
```

`<folder>` is searched for `user_data.db` files; your profile's `.data` folder is the usual one. `OFSC_DATABASE_URL` says where they go, as above. Don't run the scraper while this runs: a file that is written to while it is being copied is refused.

Run like that, it only reports: how many files, creators and rows it found for each site, and anything that stands in the way. Nothing is written to PostgreSQL. Add `--apply` to bring the files in.

- **Your files are never changed.** Each one is copied to a working folder, and the copy is brought up to date the way a scan would, so files last used by an old version come in too. The working copies need as much room as the files; `--staging <folder>` chooses where they go.
- **All or nothing.** Every file goes in together. If anything fails part way, PostgreSQL keeps none of it, and you can run the command again.
- **Each file goes to its site's tables**, OnlyFans or Fansly.
- **A creator comes from one file.** If two files hold rows for the same creator (after a rename, or a changed `metadata` setting), put them together with Merge Databases first.
- **A creator PostgreSQL already has rows for is refused**, so a file can't be brought in twice. Creators it doesn't have yet can be brought in later.
- **A value PostgreSQL's column can't hold stops the file**, and is listed with its table, row and column: an id that isn't a number, a yes/no column holding something else, a date that can't be read. Empty dates become empty. Two rows that would be the same row once a missing creator is filled in stop it too.
- **`--skip-bad-files`** brings in the files that can be, and leaves out (and lists) the ones that can't.

Afterwards the `user_data.db` files are no longer used. Keep them: there is no command yet for going back.

## What is different

- **One database for every creator.** Each site gets its own schema (`onlyfans`, `fansly`), holding the same tables a `user_data.db` has. Every row carries its creator's `model_id`.
- **Real column types.** Ids are 64-bit numbers (media, post and label ids are text: a few of them are words or hashes), yes/no columns are booleans and dates are timestamps, so other tools can query the database directly.
- **Already-downloaded media is still judged per creator.** A run skips media the database says is downloaded. A SQLite file is one creator's, so media was never skipped because another creator had it, and it isn't with PostgreSQL either: only the creator's own rows count. (`--force-model-unique` therefore changes nothing here.)
- **No automatic backup copies.** The scraper copies a SQLite file before it upgrades it. For PostgreSQL, back up with `pg_dump`.
- **Your SQLite files are left alone.** They are not read, changed or deleted while PostgreSQL is on.

## What doesn't work with it yet

- **Existing libraries start empty** until you bring your `user_data.db` files in (see above). Until then the scraper treats everything as new.
- **Tools that read `user_data.db` files** keep reading those files and don't see PostgreSQL: Merge Databases, `stash_sync`, `recover_collisions`, `scripts/creator_names.py`, and the GUI patch. Nothing scraped since you turned PostgreSQL on is in those files, and what a tool changes in them does not reach PostgreSQL.
  - `stash_sync`, `recover_collisions` and `scripts/creator_names.py` say so when they start, if `OFSC_DATABASE_URL` is set in the environment they are run in. They don't read the scraper's settings, so they say nothing when the address is only in an env file that `config.json` names.
  - Merge Databases says so on its screen.
  - The GUI patch doesn't say so.
- **Going back** to SQLite files with what PostgreSQL holds isn't built. Unsetting `OFSC_DATABASE_URL` returns to your SQLite files as they were.

## Developing

`test/test_db_postgres_live.py` runs the engine against a real server. It is skipped unless `OFSC_TEST_POSTGRES_URL` names one the tests may use; each test works in a schema of its own and drops it. CI runs it against the oldest and newest supported PostgreSQL.

A column added to a SQLite table also needs adding to `TABLES` in `ofscraper/db/postgres.py`, with the step that adds it to PostgreSQL databases made before. `test/test_db_postgres.py` fails until the two match.
