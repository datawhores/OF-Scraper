# Move a creator's files to the folder of their current name

When a creator changes their username, the scraper saves new files in a folder named after the new name while earlier files stay in the old folder. This command moves those earlier files to the current name's folder and updates the folders recorded in the database.

The command is offline: it does not contact OnlyFans or Fansly, and it does not read the scraper's settings (`config.json`). It goes only by the paths the database records.

## Run it

1. Close the scraper.
2. Preview what would move (nothing is changed without `--apply`):
   ```sh
   ofscraper move_creator_files "<profile>/.data/<model_id>/user_data.db"
   ```
3. Apply the move:
   ```sh
   ofscraper move_creator_files "<profile>/.data/<model_id>/user_data.db" --apply
   ```

`python -m ofscraper.commands.move_creator_files` also works.

The JSON report includes:

| Field | Meaning |
|---|---|
| `to`, `why` | The name the files go to and why |
| `folders` | Each folder that would be moved and how many of its files would move |
| `left` | Every recorded file that would stay, with the reason |

## How it decides what to move

- **Target name:** Uses the name the scraper saw last (`ofscraper creator_names --all` lists the names and their dates). If the names have no dates and there is more than one, the command asks for `--to NAME`. `--to` must be a name the database records for the creator.
- **Matching folders:** A recorded folder is moved when exactly one part of its path is one of the creator's other names (in small letters, as the scraper writes it), followed by one or two of the scraper's own folders (`Posts`, `Images`). That part becomes the new name.
  - A library laid out by ID has no name in its paths, so there is nothing to do.
  - A folder above the library that only has the same name (your own user folder, say) is not followed by those folders, so its files are left and listed.
- **Layouts not handled:**
  - A layout with the name inside a folder's name (`{model_username}_{model_id}`) shows as nothing to do.
  - A layout with `{first_letter}` above the name is left and listed when the new name starts with another letter.

## How files are handled

Each file is handled on its own:

| Where the file is | What happens |
|---|---|
| At the old place, and the new place is free | Moved to the new place and the database row is updated. |
| Already at the new place (moved by hand) | Only the database row is updated, if the file's size matches the recorded size. |
| At both places | Both files stay where they are and the row is left unchanged. |
| At neither place | Listed in the report. |

- **No files replaced or deleted:** It only renames (within one disk), and touches only the files the database records for that creator. Everything else in the old folder stays. An old folder is removed only when the move left it empty.
- **Filenames stay the same:** A file's own name is not changed, even when the old username is part of it. Stash and similar tools need a rescan afterwards.
- **Stopped partway through:** Run the same command again. A file that was moved already just gets its row updated. There is no undo file.
- **Going back:** Run it with `--to <old name> --apply`. That gathers all of the creator's files under the old name, including the ones that were under the new name before, so it is the way back, not an exact undo.

## Other environments and options

- **Relative recorded paths:** Pass `--path-root`, as with `recover_collisions`.
- **With PostgreSQL:** Give `--postgres --creator <username or id>` in place of the database path. See [Moving a creator's files](POSTGRESQL.md#moving-a-creators-files) in `POSTGRESQL.md`.
- **In Docker:** Run it in the scraper's container, so that the recorded paths are the files' own.
