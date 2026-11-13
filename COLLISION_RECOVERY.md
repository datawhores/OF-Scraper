# Recover downloads lost to filename collisions

Install the filename-collision prevention change (#116) before re-downloading.
Stop the scraper while running this offline command. It does not contact OnlyFans
or change media files.

Preview one model's database:

```sh
python -m ofscraper.commands.recover_collisions "<profile>/.data/<model_id>/user_data.db"
```

The JSON report lists paths shared by distinct media and `media_to_mark`.
These are **suspected** losses: old records cannot reliably identify which media
owns the surviving file. All media in an ambiguous group are included, even if
some legitimately contain identical content. Multiple posts referencing the same
media are not, by themselves, a collision. Unshared missing files are outside this
command's scope.

Apply the report by running the command again with `--apply`:

```sh
python -m ofscraper.commands.recover_collisions "<profile>/.data/<model_id>/user_data.db" --apply
```

Apply rechecks the database, writes a small JSON undo file beside it, then sets only
`downloaded = 0` for affected media, including their other post records. It leaves
filenames, hashes, sizes and media files intact. The `undo_file` path is in the
report. It records only changed row identifiers and their previous download flags,
plus the database path. No database copy is created. Running recovery again before
re-downloading makes no further changes or undo file.

To reverse the flag reset **before starting downloads**, preview and apply undo:

```sh
python -m ofscraper.commands.recover_collisions "<database>" --undo "<undo-file.json>"
python -m ofscraper.commands.recover_collisions "<database>" --undo "<undo-file.json>" --apply
```

Undo only restores matching recorded rows whose flags are still zero. It rejects
a different database path and leaves other rows and columns untouched. Keep the
undo file until satisfied with the repair; it is not a general database backup.

Then run a normal download for the affected model and content areas, with
`--after 2000` to include old messages. Do not use `--force-all`: the cleared flags
make affected media eligible while previously downloaded unaffected media stay
skipped. Normal access and content filters still apply; media no longer available
from the service cannot be restored. Do not run metadata update between recovery
and the download, since it can mark existing paths downloaded again.

The prevention change reuses matching content and gives different content a free
name, updating each database row to the final path. This command does not download
anything itself or prove that recovery succeeded.

Existing files are grouped by filesystem identity, including case variants on
case-insensitive storage. Missing files are grouped only by exact normalized
absolute path; missing case aliases cannot reliably be identified. If recorded
paths are relative, supply `--path-root` with the working directory used during
the original downloads. Only the explicitly selected database is scanned; sharing
between separate model databases is not detected. Run this targeted repair on old
affected databases, not as periodic maintenance: legitimate identical downloads
may also share a path.
