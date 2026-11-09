# OF-Scraper reference

This reference covers everything the program can be told to do. It is written for coding agents (and people) who need an answer without tracing the code. The user guide is at [cloakedkeys.gitbook.io/ofsc](https://cloakedkeys.gitbook.io/ofsc).

| File | Covers |
|---|---|
| [cli.md](cli.md) | Commands, `--action` modes, and every command-line option: name, type, default, which commands accept it, its `config.json` fallback, and where it's defined |
| [config.md](config.md) | Every `config.json` key: default, getter, older key names still read, the environment default behind it, and the option that overrides it |
| [env.md](env.md) | Every built-in default in `ofscraper/utils/of_env/values/`, the environment variables that override them, and the backoff settings |
| [placeholders.md](placeholders.md) | The names usable in `dir_format`, `file_format`, `metadata` and text file names |
| [database.md](database.md) | The tables in each creator's `user_data.db`: columns, unique keys, and what writes each row |

`scripts/reference/build_reference.py` generates those five files from the code. It takes the descriptions from `scripts/reference/notes.py`. `test/test_reference.py` fails when the files are out of date or when something has no description. This file is written by hand.

## Where a setting's value comes from

For one run, the app decides a setting in this order. The first source that gives a value wins.

1. **A command-line option**, when the option has a `config.json` fallback ([cli.md](cli.md) lists them).
   - `merged_settings` in `ofscraper/utils/settings.py` does the merge.
   - Most options are merged with `option or config`: the config value is used when the option is not set. An option set to a false value (0 or an empty string) is treated as not set, so the config value is used.
   - A flag that only turns something on can't turn a config setting off.
2. **`config.json`**, read by the getters in `ofscraper/utils/config/data.py` and `ofscraper/utils/paths/common.py`. A getter also accepts older key names and locations (see [config.md](config.md)).
3. **The built-in default**, used when the key is missing or empty.
   - The app reads it with `of_env.getattr`, so an environment variable can change it (see [env.md](env.md)).
   - Two kinds of variable work. The listed variable (usually `OFSC_<NAME>`) is read when the defaults load. The bare key name is read on every lookup.
   - Environment variables change only defaults. They don't override a value that is in `config.json`.

Environment variables come from these sources, each overriding the one before:
1. The process environment.
2. A `.env` file found by python-dotenv. It searches upward from `ofscraper/utils/of_env/`. It searches from the working folder only in the standalone binaries, the REPL or a debugger.
3. The files in `advanced_options.env_files`.

The `--env-files` option is not loaded at present.

Some settings have no `config.json` key. These are the backoff values, the timeouts, the API URLs and most of [env.md](env.md). Only the environment can change them.

Which site a run uses is decided in this order:
1. `--site`.
2. `site.json` in the profile folder (`{"site": "fansly"}`).
3. OnlyFans (`ofscraper/sites/__init__.py`).

## What writes files

- **`config.json`:** `auto_update_config` rewrites it from the getters when its keys differ from the current schema. The getter's return value is what gets saved, so a getter must return what belongs in the file. The interactive Config menu also writes it.
- **`auth.json` and `fansly_auth.json`:** the Auth menu and the login prompts write them.
- **Each creator's `user_data.db`:** any scrape writes it. That covers the `download`, `like` and `unlike` actions, `manual`, the `*_check` commands and `metadata`. [database.md](database.md) lists which rows each one writes, and the backups made beside the database.
- **Media:** files go under the save location, through `dir_format` and `file_format`. Downloads are written as `.part` files (in `advanced_options.temp_dir` when set) and then moved into place. `--no-auto-resume` deletes leftover `.part` files instead of resuming them.
- **`db --export PATH`:** writes a CSV.
- **`recover_collisions --apply`:** resets `downloaded` flags and writes an undo file beside the database.
- **Logs and cache:** logs go to the `logging` folder. The cache goes to the profile's cache folder. `--no-cache` and `--no-api-cache` stop cache writes.

## Default folder layout

```
{home_directory}/.config/ofscraper/        config home (--config changes it)
├── config.json
├── logging/                              <profile>_<date>/ofscraper_<profile>_<time>.log
│                                         (one file per day when rotate_logs is off)
└── main_profile/                         one folder per profile, always ending in _profile
    ├── auth.json                         OnlyFans credentials
    ├── fansly_auth.json                  Fansly credentials
    ├── site.json                         the profile's site, when it isn't OnlyFans
    ├── cache_sql/ or cache_json/         API and scan cache (advanced_options.cache-mode)
    ├── locks/                            lock files
    └── .data/<model_id>/                 metadata template {configpath}/{profile}/.data/{model_id}
        ├── user_data.db                  (plus -wal and -shm files)
        └── backup/                       rotating copies and pre-migration backups

{home_directory}/Data/ofscraper/           file_options.save_location
├── <model_username>/<responsetype>/<mediatype>/<filename>.<ext>
└── Fansly/                               Fansly runs save under here
```

The media path comes from `file_options.dir_format` (`{model_username}/{responsetype}/{mediatype}/`) and `file_options.file_format` (`{filename}.{ext}`). See [placeholders.md](placeholders.md).

## Features only this fork has

Upstream's docs don't cover these:

- **Fansly** as a second site:
  - `--site`, the profile's `site.json` and `fansly_auth.json`.
  - Fansly posts, messages and purchases (`-o timeline,messages,purchased`).
  - Fansly labels (`-o labels`, `labels+`, `labels*`): each wall, a named tab on the creator's profile, is a label. The main "Posts" wall is the whole timeline, so it's skipped. With the default `dir_format`, wall posts are saved with the timeline and their labels are recorded in the `labels` table. Add `{label}` to `dir_format` for a folder per wall. Other areas (pinned, archived, stories, highlights, streams, profile) are skipped on Fansly.
  - HLS/DASH video.
  - Livestream recording (`--live`, `--live-watch`, `--live-interval`, `--live-max`, `--live-chat`).
  - Fansly media save under `<save location>/Fansly`.
  - Fansly databases carry a `site` row in `schema_flags`.
- **`file_options.filename_collision`** (environment default `FILENAME_COLLISION_DEFAULT`): decides what happens when two media would get the same file name.
- **`recover_collisions`** (`python -m ofscraper.commands.recover_collisions`): repairs databases where different media were recorded under one path. See `COLLISION_RECOVERY.md`.
- **`stash_sync`** (`python -m ofscraper.commands.stash_sync`): copies the OnlyFans and Fansly details of downloaded files into Stash. See `STASH.md`.
- **`scripts/creator_names.py`**: lists and records the usernames a creator account has had.
- **`OF_READ_TIMEOUT`**: a default read timeout for requests.
- **`LABELS_CONCURRENCY`**: a concurrency default for label scans.
- **Behaviour changes** listed in the release notes. For example, `--before` and `--after` accept `MM/DD/YYYY` and relative dates, a failed run exits with status 1, and command-line mistakes print a usage message.

## Keeping this up to date

A change that adds, renames or removes a command-line option, `config.json` key, environment default, placeholder or database column must update `scripts/reference/notes.py` and regenerate the files:

```bash
PYTHONPATH=. .venv/Scripts/python scripts/reference/build_reference.py
```

`test/test_reference.py` checks both, so CI fails until it's done.
