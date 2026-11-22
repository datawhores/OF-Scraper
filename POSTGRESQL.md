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

PostgreSQL's keyword form (`host=... user=... password=...`) works too. In it, quote a password that has spaces (`password='a b'`), or use the URL form above.

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
- **A creator's names come with the dates they were seen at**, where the file has them. A name PostgreSQL already has (the scraper has started on the creator there, and saved nothing yet) keeps its row, and its dates are widened to take the file's in: the earlier first-seen date and the later last-seen date are kept, and a date is never emptied. That adds no row, so it isn't in the count of rows added. A deleted account goes by the name seen last, so a name the file brings with a newer date than any PostgreSQL has becomes that name.
- **A value PostgreSQL's column can't hold stops the file**, and is listed with its table, row and column: an id that isn't a number, a yes/no column holding something else, a date that can't be read. Empty dates become empty. Two rows that would be the same row once a missing creator is filled in stop it too.
- **`--skip-bad-files`** brings in the files that can be, and leaves out (and lists) the ones that can't.

Afterwards the `user_data.db` files are no longer used. Keep them anyway, as your copy from before the switch.

## Going back to SQLite files

Unsetting `OFSC_DATABASE_URL` returns to your `user_data.db` files as they were, without anything scraped since. A second command writes what PostgreSQL holds back to files first:

```
python -m ofscraper.commands.postgres_export <folder>
```

Every creator PostgreSQL has rows for gets a file of their own, `<folder>/<the creator's id>/user_data.db`. A profile's `.data` folder is laid out like that, unless you changed the `metadata` setting: then move each file to where your setting puts it. `OFSC_DATABASE_URL` says which database is read, as above. Don't run the scraper while this runs: what it saves meanwhile isn't in the files.

Run like that, it only reports: how many creators and rows it found, and which creators already have a file. Nothing is written. Add `--apply` to write the files.

- **PostgreSQL is only read.** It holds everything afterwards as it did before.
- **A file that is already there is never changed.** Its creator is left out and listed, and the others are written. To get that creator's rows, run the command again with another folder, an empty one. You then have both files. If you brought the old file into PostgreSQL before, the new one holds everything and can take its place. If you didn't, put the two together with Merge Databases. A `user_data.db-wal` or `user_data.db-journal` file left where a database used to be is in the way too.
- **A file that appears while the command runs is left as it is too**, and its creator is listed. That is certain on Windows, and on any disk that has hard links (most have). On Linux or macOS with a disk that has none (FAT or exFAT, some network shares), the command looks for the file and then names its own: a file another program makes in the moment between is replaced. One more reason not to run the scraper meanwhile.
- **A file is whole or isn't there.** It is made under another name beside its place (`user_data.db.<letters>.partial`) and gets its name once it is complete. A run that is stopped, with Ctrl-C too, removes what it was making and leaves no half-written `user_data.db`. It can be run again: the files already written are left out. A `.partial` file is left only by a run that was killed, or on Windows when another program had it open. It can be deleted.
- **A file is one the scraper would have made today.** The code that makes a new creator's database makes it, so it has the same tables and has had every upgrade step.
- **A file is checked before it gets its name.** It has to hold the rows exactly as PostgreSQL gave them, and the import has to be able to read it. A creator whose file fails that is listed with the reason, and gets no file.
- **A value a `user_data.db` can't keep stops its creator's file**, and is listed with its table, row, column and value. The row's number is its place among the creator's rows of that table, oldest first. That creator gets no file until the value is changed in PostgreSQL; then run the command again. Such values are rare, and the import lets some in: a media, post or label id that is a number but not a whole one (`1.5`, `1e20`), which SQLite would keep as another value, and a whole number SQLite has no room for (2^63 or more).
- **One site at a time.** If PostgreSQL has rows for both OnlyFans and Fansly, add `--site onlyfans` or `--site fansly` and give each site its own folder: an id is a creator of its own on each site.

What comes back is what the scraper reads from PostgreSQL. For files you brought in, those are the same rows, with these differences:

- **A date** is the same moment, written in UTC (`2024-03-01T09:30:00+00:00`), whatever form the old file had: another offset, none, or a number of seconds. Anything finer than a millionth of a second is rounded.
- **The dates of a name PostgreSQL already had** when the file was brought in are the dates of both: the earlier first-seen date and the later last-seen date, whichever side each came from. Dates the scraper has written since are in the file too.
- **Empty text is empty (NULL)** in every column that holds a number, a yes or no or a date: a post's price, a media's size, a message's `user_id`, a label's `post_id`. Columns that hold text keep it.
- **A yes or no** is 1 or 0, however the old file wrote it (`true`, `FALSE`).
- **A whole-number price above 2^53** (9,007,199,254,740,992) comes back rounded: the scraper reads a price from PostgreSQL as a number with a fraction, which has no room for more.
- **Bytes (a BLOB)** come back as text. In a media, post or label id, bytes that spell a whole number come back as that number (`12`).
- **A row that named no creator** names the file's.
- **A row's own `id`** is its place among the creator's rows, oldest first. In a file that held one creator that is usually the id it had. Where it isn't, an undo file that `recover_collisions` wrote for the old file no longer finds its rows.
- **Another creator's rows leave the file.** A file that held several creators comes back as one file for each, in a folder of its own. That goes for a single row too: another creator's `models` or `profiles` row becomes a file that holds little else.
- **Every file has its creator's row in `models`**, also where the old file hadn't.
- **Not carried at all:** rows you added to `schema_flags` (each file gets the upgrade steps of the version that writes it, and nothing else), indexes you added, and tables that aren't the scraper's. A file that held rows in `profiles` and `models` only was never brought in, so it doesn't come back.

## Syncing to Stash

`stash_sync` (see `STASH.md`) reads PostgreSQL when it is given `--postgres` in place of the paths to `user_data.db` files:

```
python -m ofscraper.commands.stash_sync --postgres
```

- **It reads the database that `OFSC_DATABASE_URL` names in the environment the command is run in.** It is a separate tool and doesn't read the scraper's settings, so an address that is only in a `.env` file that `config.json` names is not seen: set the variable for the command. In Docker, an address given under `environment:` is already set for a command run in the container.
- **It needs the PostgreSQL driver**, as the scraper does.
- **Every creator of both sites is synced** unless you narrow it: `--site onlyfans` or `--site fansly` keeps one site, and `--creator <username or id>` keeps the creators it matches and can be given more than once. It matches an id on either site, and any username a creator has had, in any case, so it can match more than one creator.
- **PostgreSQL is only read.** The command opens one read-only connection, sees the database as it was when it started reading, and closes the connection before it sends anything to Stash. Its login only needs `USAGE` on each site's schema and `SELECT` on its tables.
- **A read doesn't wait for ever.** One that waits more than 30 seconds for a table another program has locked, or that takes more than 5 minutes, is ended by the server and the command stops.
- **A few results differ from the files'.** `STASH.md` lists them.
- **Given `user_data.db` files, it still reads those files.** With `OFSC_DATABASE_URL` set it then says that they hold nothing scraped since PostgreSQL was turned on. Files and `--postgres` together are refused.
- **A server it can't use** (not running, a refused login, no such database, no driver, a login that may not read a site's tables) stops it with one sentence and exit code 1, before Stash is contacted. The sentence names the host, the port and the database, never the password.

## Recovering filename collisions

`recover_collisions` (see `COLLISION_RECOVERY.md`) works on PostgreSQL when it is given `--postgres` and a creator in place of the path to a `user_data.db`:

```
python -m ofscraper.commands.recover_collisions --postgres --creator <username or id>
python -m ofscraper.commands.recover_collisions --postgres --creator <username or id> --apply --undo-dir <folder>
python -m ofscraper.commands.recover_collisions --postgres --creator <username or id> --undo <undo file> --apply
```

- **It uses the database that `OFSC_DATABASE_URL` names in the environment the command is run in**, and needs the PostgreSQL driver, as `stash_sync --postgres` does (see above).
- **One creator at a time.** `--creator` names the creator, by username or id. It must fit exactly one creator. If more than one goes by it (an id both sites have, an id that is another creator's username, a username two creators have had), the command changes nothing and lists them: give `--site onlyfans` or `--site fansly`, or a username or id that only one of them has. Only that creator's rows in that site's tables are read and changed. As with files, media of two different creators that share a path are not looked for.
- **The report says which creator it worked on**: the site, the id and the username saved last (`creator`). Look at it before `--apply`: a number can be one creator's id and another's username.
- **It finds and changes what it would in a `user_data.db` with the same rows.** Without `--apply` it only reads, over a read-only connection, and reports. With `--apply` it resets the same download flags, and `--undo <file>` sets them back.
- **Run it where the scraper runs** (with Docker: in the scraper's container), so that the recorded paths are the files' own. Paths recorded on another system (Windows paths read on Linux, or the reverse) are refused. `--path-root` is for relative recorded paths only, as before.
- **Close the scraper first**, as with files. A file locks the scraper out while the command works; PostgreSQL does not. If the scraper changes one of the rows while the command runs, the command changes nothing and says so. Run it again once the scraper is closed. What the scraper saves for the first time while the command runs is not seen by it: a post saved meanwhile for a media that is being reset keeps its download flag.
- **`--apply` needs `--undo-dir <folder>`**, the folder the undo file is written to. The undo file is the only way back, so the folder must be one that is kept. **In Docker, give a mounted folder**: a folder inside the container is gone when the container is. A preview given `--undo-dir` checks that the folder is there and can be written to. The report gives the undo file's full path.
- **All or nothing, until the changes are saved.** The undo file is written first. If it can't be written, or anything fails or the command is stopped before the changes are saved, no row is changed and the undo file is removed.
- **Once the changes are being saved, the undo file is kept whatever happens.** If the connection is lost or the command is stopped (Ctrl-C) at that moment, it can't know whether the server kept the changes. It says so and where the undo file is: run it with `--undo <that file>`, without `--apply`, to see whether there is anything to restore.
- **The undo file** names each row by its media and post, and records what the row held, and the server and database it was made on (not the login).
- **`--undo` restores every row in the undo file, or none.** With a `user_data.db` it skips the rows that no longer fit; here it stops. It is refused for another creator or site, and when a row is no longer as the recovery left it (for example, its media was downloaded again under another name); the message then says if the undo file was made on another database than the one in use. An undo file written for a `user_data.db` only fits that file, also after the file was brought into PostgreSQL; one written from PostgreSQL only fits PostgreSQL.
- **An undo file is trusted as far as the rows agree with it.** As with files, one written by hand can mark as downloaded a row the recovery never touched. Only that creator's rows, only from not downloaded to downloaded, and only a row whose folder, file name, size and hash are the ones the undo file gives.
- **Given a `user_data.db`, it still works on that file.** With `OFSC_DATABASE_URL` set it then says that the file holds nothing scraped since PostgreSQL was turned on. A file and `--postgres` together are refused.
- **Behind a connection pooler** that hands each transaction to another server connection (PgBouncer in transaction mode), the time zone and the timeouts the command sets may not hold. Give it the server's own address.

## Moving a creator's files

`move_creator_files` (see `MOVING_FILES.md`) works on PostgreSQL when it is given `--postgres --creator <username or id>` in place of the path to a `user_data.db`, with `--site` if more than one creator goes by that name. The database and the creator are found as `recover_collisions --postgres` finds them (see above), and it moves what it would with a `user_data.db` that has the same rows. Close the scraper first: PostgreSQL does not lock it out as a file does. The rows are changed in one transaction that is saved at the end. If the scraper changed one of them meanwhile, no row is changed, and the files moved so far stay at their new places. If the connection is lost while the changes are being saved, it isn't known whether they were kept. Either way, run the same command again to finish.

## What is different

- **One database for every creator.** Each site gets its own schema (`onlyfans`, `fansly`), holding the same tables a `user_data.db` has. Every row carries its creator's `model_id`.
- **Real column types.** Ids are 64-bit numbers (media, post and label ids are text: a few of them are words or hashes), yes/no columns are booleans and dates are timestamps, so other tools can query the database directly.
- **Already-downloaded media is still judged per creator.** A run skips media the database says is downloaded. A SQLite file is one creator's, so media was never skipped because another creator had it, and it isn't with PostgreSQL either: only the creator's own rows count. (`--force-model-unique` therefore changes nothing here.)
- **No automatic backup copies.** The scraper copies a SQLite file before it upgrades it. For PostgreSQL, back up with `pg_dump`.
- **A new version adds its new columns when it starts.** Tables an earlier version made get the columns added since (so far `first_seen_at` and `last_seen_at` in `profiles`: when each of a creator's names was seen). The rows already there are kept as they are, with nothing in the new columns. The login has to own the tables, as it does when the scraper made them. The export only reads, so it adds nothing: columns the tables don't have yet come out empty.
- **Your SQLite files are left alone.** They are not read, changed or deleted while PostgreSQL is on.

## What doesn't work with it yet

- **Existing libraries start empty** until you bring your `user_data.db` files in (see above). Until then the scraper treats everything as new.
- **Tools that read `user_data.db` files** keep reading those files and don't see PostgreSQL: Merge Databases and the GUI patch. Nothing scraped since you turned PostgreSQL on is in those files, and what a tool changes in them does not reach PostgreSQL.
  - Merge Databases says so on its screen.
  - The GUI patch doesn't say so.
  - The tools that are run on their own (`stash_sync`, `recover_collisions`, `move_creator_files` and `scripts/creator_names.py`) all work on PostgreSQL when you tell them to with `--postgres`: see "Syncing to Stash", "Recovering filename collisions" and "Moving a creator's files" above, and for `scripts/creator_names.py`, `python scripts/creator_names.py --postgres [--site onlyfans|fansly]` with its usual options (`--all`, `--find`, `--csv`, `--add MODEL_ID NAME [--seen DATE] [--force]`). Each one finds PostgreSQL only through `OFSC_DATABASE_URL` in the environment it is run in, not the scraper's settings. Given files while PostgreSQL is on, each says that it works on the files.

## Developing

`test/test_db_postgres_live.py` runs the engine against a real server, and `test/test_postgres_import_live.py` and `test/test_postgres_export_live.py` the two commands above. They are skipped unless `OFSC_TEST_POSTGRES_URL` names a server the tests may use; each test works in schemas of its own and drops them. CI runs them against the oldest and newest supported PostgreSQL. `test/test_stash_sync_postgres_live.py` does the same for `stash_sync --postgres`, `test/test_collision_recovery_postgres_live.py` for `recover_collisions --postgres`, `test/test_move_creator_files_postgres_live.py` for `move_creator_files --postgres`, and `test/test_creator_names_postgres_live.py` for `scripts/creator_names.py --postgres`.

A column added to a SQLite table also needs adding to `TABLES` in `ofscraper/db/postgres.py`, with the step that adds it to PostgreSQL databases made before: an entry in `ADDED_COLUMNS` there. At each start `create_tables` asks which of those columns the tables have and adds the ones that are missing. `test/test_db_postgres.py` fails until the two match.
