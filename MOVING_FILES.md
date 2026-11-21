# Move a creator's files to the folder of their current name

When a creator changes their username, the scraper saves new files in a folder
named after the new name. The files it saved before stay in the old folder.
This command moves them to the current name's folder and updates the folders
the database records.

Close the scraper first. The command is offline: it does not contact OnlyFans
or Fansly, and it does not read the scraper's settings. It goes only by the
paths the database records.

```sh
python -m ofscraper.commands.move_creator_files "<profile>/.data/<model_id>/user_data.db"
python -m ofscraper.commands.move_creator_files "<profile>/.data/<model_id>/user_data.db" --apply
```

Without `--apply` nothing is changed. The JSON report shows the name the files
go to and why (`to`, `why`), each folder that would be moved and how many files
(`folders`), and every recorded file that would stay, with the reason (`left`).

- **Which name.** The name the scraper saw last (`scripts/creator_names.py
  --all` lists the names and their dates). If the names have no dates and
  there is more than one, the command asks for `--to NAME`. `--to` must be a
  name the database records for the creator.
- **Which folders.** A recorded folder is moved when exactly one part of its
  path is one of the creator's other names, in small letters as the scraper
  writes it, and is followed by one or two of the scraper's own folders
  (`Posts`, `Images`). That part becomes the new name. A library laid out by
  id has no name in its paths, so there is nothing to do. A folder above the
  library that only has the same name (your own user folder, say) is not
  followed by those folders: its files are left and listed.
- **Not handled:** a layout with the name inside a folder's name
  (`{model_username}_{model_id}`) shows as nothing to do. A layout with
  `{first_letter}` above the name is left and listed when the new name starts
  with another letter.
- **Each file on its own.** A file at its old place is moved if its new place
  is free. A file that is at the new place already (moved by hand) only gets
  its row updated, if its size is the one recorded. If both places hold a
  file, both stay and the row is left. A file at neither place is listed.
- **It never replaces or deletes a file.** It only renames, within one disk,
  and it touches only the files the database records for that creator.
  Everything else in the old folder stays. An old folder is removed only when
  the move left it empty.
- **A file's own name is not changed**, also when the old username is part of
  it. Stash and similar tools need a rescan afterwards.
- **If it is stopped part way, run the same command again.** A file that was
  moved already just gets its row updated. There is no undo file.
- **To go back**, run it with `--to <old name> --apply`. That gathers all the
  creator's files under the old name, also the ones that were under the new
  name before, so it is the way back and not an exact undo.
- **Relative recorded paths** need `--path-root`, as with `recover_collisions`.
- **With PostgreSQL**, give `--postgres --creator <username or id>` in place of
  the database path. See "Moving a creator's files" in `POSTGRESQL.md`.
- **In Docker**, run it in the scraper's container, so that the recorded paths
  are the files' own.
