# Rename files after changing file_format or dir_format

When you change `file_format` or `dir_format`, the scraper saves new files under the new names, and the files you've already downloaded keep their old ones. This command gives a creator's downloaded files the names the current formats give them, and updates the names recorded in the database to match.

The command is offline: it doesn't contact OnlyFans or Fansly, and nothing is downloaded. It reads the scraper's `config.json` for the formats and the save location, and never changes it.

## Run it

1. Close the scraper.
2. Preview the new names (nothing is changed without `--apply`):
   ```sh
   ofscraper rename_to_format "<profile>/.data/<model_id>/user_data.db"
   ```
3. Rename:
   ```sh
   ofscraper rename_to_format "<profile>/.data/<model_id>/user_data.db" --apply
   ```

`python -m ofscraper.commands.rename_to_format` also works. If the scraper runs with `--config` or `--profile`, give the same options here.

The JSON report includes:

| Field | Meaning |
|---|---|
| `file_format`, `dir_format`, `save_location` | The settings the new names are built from |
| `username`, `why` | The name used for `{model_username}`, and why |
| `to_rename`, `unchanged`, `already_there` | How many files get a new name, already have it, or were renamed by an earlier run that stopped |
| `renames` | The first 20 renames, old and new path (`--sample N` for more, `--sample 0` for all) |
| `left` | Every file that keeps its name, with the reason |
| `undo_file` | With `--apply`, the undo file written beside the database (none when nothing was changed) |

## How the new names are made

Each name is built by the same code a download uses, from what the database holds about the file: its media row, its post or message, and the creator.

- **Username:** the name the scraper saw last (`ofscraper creator_names --all` lists them). Give `--username NAME` to pick another name the database records.
- **Values the database doesn't hold:** a file whose new name needs one is left and listed, with the placeholders it needs:
  - `{quality}` of a video, and `{filename}` or `{file_name}`, which include it, unless the old name shows the quality (as `{filename}` writes it, `name_720`). `{only_filename}` and `{original_filename}` don't need it.
  - `{text}` of a story or highlight, and of any post when `sanitize_text` is on (the database then holds the text cleaned up, not as the file was named).
  - `{label}` of a post in a label: the database doesn't say which area the file was downloaded from.
  - The count added to the names of a post with several media, when `file_format` has no `{filename}`, `{media_id}` or similar.
  - `{current_price}` and the other prices, `{modelObj}`, `{my_id}`, `{my_username}` and `{args}`.
- **`naming_script`:** if one is set, the command refuses to run, since it can't run the script.

## How files are handled

Each file is handled on its own:

| Where the file is | What happens |
|---|---|
| At the old place, and the new place is free | Renamed, and its database rows updated |
| A folder (not a file) at the old place | Left and listed; the folder isn't moved |
| Already at the new place (renamed by a run that stopped) | Only the rows are updated, if it is a file of the recorded size |
| At the old place, and something is at the new place | Left and listed; nothing is replaced |
| The new place is another file's new name too, or another row records it | Left and listed |
| At neither place | Listed |

- **No file is replaced or deleted.** A rename is never made onto an existing file. The command touches only the files the database records for that creator: `.txt` post text, unfinished `.part` files and anything else in the folders stay where they are.
- **Empty folders:** old folders the renames leave empty are removed, up to the save location.
- **Rows of other media:** a row with `downloaded = 0` that records the same file for another media (see `recover_collisions`) keeps its name.
- **Names that differ only in case:** on a disk that doesn't tell case apart (Windows, macOS), a new name that differs only in case is still made, and the rows that spell one file in different cases are handled as that one file.
- **Moves between disks:** a new name on another disk (after changing `save_location`) can't be made with a rename. Such files are listed.
- **Swaps:** if one file's new name is another file's old one, run the command again after the first run. A pair that swap names stay as they are.
- **Stash and other tools** that index files by path need a rescan afterwards.

## Undo

```sh
ofscraper rename_to_format --undo "<profile>/.data/<model_id>/user_data.db.rename-undo-<...>.json"
ofscraper rename_to_format --undo "<...>.json" --apply
```

The undo file lists every rename and row change, and is written before the first one is made. The first line previews; `--apply` does it. A file still at its new name, with nothing at its old one, gets the old name back, and the rows that still record the new name get the old one. Anything changed since is listed and left alone, so running it twice changes nothing the second time.

If a run is stopped part way (an error, or Ctrl-C), the files renamed so far get their old names back and no row changes. When every file is back at its old name, the undo file is removed, as there is nothing to undo. It is kept when a file couldn't be put back, or a second stop landed while they were; running `--undo` with it then puts back only what is still renamed. If a file can't be renamed (a permissions error, say), it's listed and the rest go on.

## Other environments and options

- **Relative recorded paths:** pass `--path-root`, as with `recover_collisions`.
- **With PostgreSQL:** not supported yet. While `OFSC_DATABASE_URL` is set, a preview warns that the `user_data.db` doesn't reach PostgreSQL, and `--apply` (also with `--undo`) is refused: renaming the files would part them from their PostgreSQL rows.
- **In Docker:** run it in the scraper's container, so that the recorded paths and the config are the scraper's own.
