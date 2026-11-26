# Check your library against the database

The database records each file the scraper downloaded. If a file is later deleted, cut short or lost with a drive, the database still says it's downloaded, so the scraper never fetches it again. `ofscraper verify` finds those files without logging in, and can mark them so the next normal run downloads them again.

**Before you start:** stop the scraper while you run `--apply` or `--undo`.

## 1. Preview

```sh
ofscraper verify "<profile>/.data"
```

Give a profile's `.data` folder to check every creator in it, or one creator's `user_data.db`. Nothing is changed. The JSON report has, for each creator:

| Finding | Meaning | Reset by `--apply` |
|---|---|---|
| `missing` | the recorded file isn't there | yes |
| `empty` | the file is 0 bytes | yes |
| `size_differs` | the file's size isn't the recorded size | only with `--reset-size-differs` |
| `no_file_recorded` | marked downloaded with no file | never |
| `ok` | present and the right size | — |

- **`no_file_recorded`** is how the scraper marks an item it has given up on for good (a bad link, an empty file from the server, a permanent skip by your script). Resetting those would make every run try them again, so they're only counted.
- **`size_differs`** isn't reset by default, because you may have edited or re-encoded the file yourself.
- **`not_recoverable`** marks a finding that downloading again can't fix: an expired story or highlight, a deleted post, a locked item, or a profile picture or header. A media in several posts is recoverable if any of them is. A recorded path that is a link to a file that isn't there, or a folder, is also `not_recoverable`. `--apply` leaves these alone.
- **`folders_missing`** lists recorded folders that aren't there, which often means a drive or share isn't connected.
- **`media_to_reset`** and **`files_to_move_aside`** say what `--apply` would do.

Up to 20 findings per creator are listed with their paths (`--sample N` for more); the counts always cover everything.

## 2. Apply

```sh
ofscraper verify "<profile>/.data" --apply
```

- Every database row of each `missing` or `empty` media is set to not downloaded, so the next normal run downloads it again.
- An `empty` file (or a `size_differs` one, with `--reset-size-differs`) is renamed with `.bad` added, so the new download gets the original name. Delete the `.bad` files once you're happy with the new ones.
- An undo file is written beside each database first (`user_data.db.verify-undo-<...>.json`), and its path is in the report. If the run is stopped before it finishes a creator, nothing is changed for that creator and its files are renamed back. Creators finished before it stay changed: their report is printed, and their undo files are listed.

**If a drive is unplugged:** a creator is left alone when its folder isn't there or can't be read, when the nearest folder of a missing file that is there is a place drives are mounted (such as `/mnt` or `/Volumes`) or is empty (an unplugged drive often leaves its empty mount folder), or when more than half of its files are missing, and `left_alone` in the report says why (nothing of that creator is then reset). The creator's folder is the folder all its recorded folders on a drive are in, so a deleted post folder inside it doesn't stop the reset, while a library spread over several drives isn't reset when only one of them is unplugged. Files `--apply` leaves alone anyway, such as expired stories, aren't counted. Each creator is judged on its own rows, also when several creators share one database: the others are still reset. Connect the drive and run it again. If the files really are gone (a folder you deleted, say), add `--allow-missing`.

**Names spelt otherwise:** a file whose name on disk is its recorded name in another Unicode form (a Mac writes names decomposed), or in another case on a disk that doesn't tell case apart, is found, not reported missing. A file moved aside is renamed under the name it has on disk.

## 3. Download again

Run the scraper as usual. Only the reset files are downloaded; everything else is still marked downloaded.

No `--after` is needed. In the timeline, messages, archived posts and streams, a normal run starts its scan at the oldest not-downloaded file, so it goes back far enough by itself. Purchases, pinned posts, highlights and stories are scanned in full every run, and on Fansly a run keeps paging until it has passed the oldest not-downloaded post.

A reset media isn't downloaded while another creator's row for the same media is still marked downloaded. That only happens when files are shared between creators (unique-across-models mode) or with PostgreSQL.

## Undo

```sh
ofscraper verify --undo "<profile>/.data/<model_id>/user_data.db.verify-undo-<...>.json"
ofscraper verify --undo "<...>.json" --apply
```

The first line previews; `--apply` does it. Rows still marked not downloaded are marked downloaded again, and files moved aside get their names back. Rows downloaded again since are left as they are, so it's safe to run at any time, and running it twice changes nothing the second time. If a file can't be renamed back, nothing is changed and the files renamed back so far are moved aside again; run it again once the file is free.

## Files the database doesn't know

```sh
ofscraper verify "<profile>/.data" --untracked
```

Lists files in each creator's folders that no database row points to, such as files you copied in by hand. Files the scraper writes without a row (post text, live recordings and their chat, unfinished `.part` downloads, `.duplicate` and `.bad` files, undo files) are only counted, as `not_in_database`. Nothing is moved or deleted.

## Checking file contents

```sh
ofscraper verify "<profile>/.data" --hash
```

A file can be the right size and still be damaged. `--hash` compares each file with the hash recorded when it was saved, and reports `hash_differs`. Hashes are only recorded while `remove_hash_match` is on, so `hash_not_recorded` says how many files couldn't be checked. It reads every file, so it takes a while on a big library. Add `--reset-hash-differs --apply` to download those again; the damaged files are moved aside with `.bad` added.

## Libraries seen from elsewhere

If the database was written in Docker and you run `verify` on the host, the recorded paths are the container's. Map them:

```sh
ofscraper verify "<profile>/.data" --path-map /data=/mnt/library
```

`--path-map` can be given more than once. A database written on Windows and checked on Linux or macOS (or the other way round) also needs `--path-map`; without it, verify stops with an error rather than report every file missing. If the database holds relative paths, give the folder the scraper ran in with `--path-root`.

## PostgreSQL

```sh
ofscraper verify --postgres --creator "<name or id>"
ofscraper verify --postgres --creator "<name or id>" --apply --undo-dir "<folder>"
ofscraper verify --postgres --creator "<name or id>" --undo "<folder>/postgresql-...json" --apply
```

`OFSC_DATABASE_URL` must be set where you run it (see [POSTGRESQL.md](POSTGRESQL.md)). `--apply` needs `--undo-dir`, a folder that is kept (in Docker, a mounted one). Add `--site` if both sites have a creator by that name. A row the scraper changed while this ran stops it with nothing changed. `--undo` restores all the rows of its undo file or none: if one is no longer as the reset left it (downloaded again to another file, or the undo file is from another database), nothing is restored.

Giving `user_data.db` files while `OFSC_DATABASE_URL` is set prints a warning: those files hold nothing scraped since PostgreSQL was turned on.

## Exit status

`0` with the report, `1` on failure, `2` on bad arguments, `130` when interrupted.
