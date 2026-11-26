# Recover downloads lost to filename collisions

This offline command finds suspected losses (paths shared by distinct media in a creator's database) and resets their download flags with `--apply` so you can re-download lost files. It does not contact OnlyFans or change media files.

**Before you start:**

- Install the filename-collision prevention change (#116) before re-downloading.
- Stop the scraper while running this command.

## Recovery steps

### 1. Preview a creator's database

```sh
ofscraper recover_collisions "<profile>/.data/<model_id>/user_data.db"
```

`python -m ofscraper.commands.recover_collisions` also works.

The JSON report lists paths shared by distinct media and `media_to_mark`:

- These are **suspected** losses: old records cannot reliably identify which media owns the surviving file.
- All media in an ambiguous group are included, even if some legitimately contain identical content.
- Multiple posts referencing the same media are not, by themselves, a collision.
- Unshared missing files are outside this command's scope.

### 2. Apply the flag reset

```sh
ofscraper recover_collisions "<profile>/.data/<model_id>/user_data.db" --apply
```

- Rechecks the database, writes a small JSON undo file beside it, and sets only `downloaded = 0` for affected media (including their other post records).
- Leaves filenames, hashes, sizes, and media files intact. No database copy is created.
- Prints the `undo_file` path in the report. The undo file records only changed row identifiers, their previous download flags, and the database path.
- Running recovery again before re-downloading makes no further changes and writes no new undo file.

### Undoing a reset (before step 3)

To reverse the flag reset **before starting downloads (step 3)**, preview and apply undo:

```sh
# Preview undo
ofscraper recover_collisions "<database>" --undo "<undo-file.json>"

# Apply undo
ofscraper recover_collisions "<database>" --undo "<undo-file.json>" --apply
```

- Undo only restores matching recorded rows whose flags are still zero.
- It rejects a different database path and leaves other rows and columns untouched.
- Keep the undo file until you are satisfied with the repair; it is not a general database backup.

### 3. Re-download the affected media

Run a normal download for the affected model and content areas, with `--after 2000` to include old messages.

- **Do not use `--force-all`:** the cleared flags make affected media eligible while previously downloaded unaffected media stay skipped.
- **Do not run metadata update between recovery and the download:** it can mark existing paths as downloaded again.
- Normal access and content filters still apply; media no longer available from the service cannot be restored.
- The prevention change reuses matching content and gives different content a free name, updating each database row to the final path. This command does not download anything itself or prove that recovery succeeded.

## How paths are matched

- **Existing files:** Grouped by filesystem identity, including case variants on case-insensitive storage.
- **Missing files:** Grouped only by exact normalised absolute path; missing case aliases cannot reliably be identified.
- **Relative paths:** If recorded paths are relative, supply `--path-root` with the working directory used during the original downloads.
- **One database at a time:** Only the explicitly selected database is scanned; sharing between separate model databases is not detected.
- **Targeted repair only:** Run this on old affected databases, not as periodic maintenance, because legitimate identical downloads may also share a path.

## With PostgreSQL

If the scraper stores its data in PostgreSQL (`OFSC_DATABASE_URL`), the `user_data.db` files are no longer updated. Pass `--postgres` and `--creator` in place of the database path:

```sh
# Preview
ofscraper recover_collisions --postgres --creator "<username or id>"

# Apply
ofscraper recover_collisions --postgres --creator "<username or id>" --apply --undo-dir "<folder>"

# Undo
ofscraper recover_collisions --postgres --creator "<username or id>" --undo "<undo-file.json>" --apply
```

- **Same report and changes:** The report also says which creator the name turned out to be.
- **`--apply` requires `--undo-dir`:** The folder where the undo file is written. The undo file is the only way back, so give a folder that is kept. In Docker, use a mounted folder, not one inside the container.
- **Other differences:** See [Recovering filename collisions](POSTGRESQL.md#recovering-filename-collisions) in `POSTGRESQL.md` for where to run it, the scraper running at the same time, and when an undo is refused.
- **Short option names:** `--undo` and `--path-root` can no longer be shortened to `--u`, `--un`, `--und`, or `--p`: with the new options those fit two options, and the command stops without doing anything.
