# Organize downloads in Stash

[Stash](https://stashapp.cc) is a self-hosted media library. It indexes your download folders, but on its own it only knows file names. `stash_sync` copies what OF-Scraper recorded about each file into Stash, for both OnlyFans and Fansly downloads:

| Field | OnlyFans | Fansly |
|---|---|---|
| **Performers** | The creator, with a link to their OnlyFans page | The creator, with a link to their Fansly page, plus anyone @mentioned in the caption |
| **Studio** | `OnlyFans` | `Fansly` |
| **Date** | When the post or message was posted | Same |
| **Title and details** | The caption's first line (title) and the full caption (details) | Same |
| **Code** | The post ID (none for profile pictures) | The Fansly media ID |
| **URL** | The post's page, for timeline posts and bought posts | `https://fansly.com/post/<id>` for timeline posts, and `https://fansly.com/messages/<conversation>` for messages |
| **Tags** | Where the file came from (e.g. `OnlyFans Timeline`, `OnlyFans Messages`, or `OnlyFans Paid`) | Same with `Fansly`, plus `Fansly Preview` for preview media and the caption's #hashtags, lowercased |
| **Gallery** | None | One per post or message, holding its images and scenes |

- **Fansly galleries:** Each gallery gets the post or message ID as its code, along with the same studio, performers, date, title, details, URL, and tags (without `Fansly Preview`). Fansly purchases are not posts, so their files get no gallery.
- **Message URLs:** OnlyFans messages have no public page, so they get no URL. A Fansly message link needs its conversation ID. Databases written by older versions of OF-Scraper don't have it, so those messages get no URL until a messages scan fills it in; the next sync run then adds the link.
- **Custom studio and tags:** `--studio` and `--tag-prefix` replace the studio and tag prefix for every site, and `--no-tags` turns off all of these tags. A `--studio` used for both sites in one run is created without a site link.
- **Existing Stash data is kept:** The command only fills in empty fields and adds performers, the studio, tags, and galleries. Anything you already set in Stash is kept, so running it again changes nothing that is already there.
  - *One exception:* earlier versions linked a Fansly message as `https://fansly.com/messages/<conversation>/<id>`, which is not a Fansly page. That exact link is replaced by the conversation's link; any other link is kept.
- **Offline database read:** The command reads OF-Scraper's databases offline and never contacts OnlyFans or Fansly. A Fansly database is recognised by the site OF-Scraper records in it; Fansly runs keep their databases in a `Fansly` folder under `.data` by default. It can also read a PostgreSQL database (see [With PostgreSQL](#with-postgresql) below).

## Run it

1. Make sure Stash is running and has already scanned your download folders (or add `--scan` when running with `--apply` below to have Stash scan them first).
2. Preview what would change:
   ```sh
   python -m ofscraper.commands.stash_sync "<profile>/.data"
   ```
3. Apply the changes:
   ```sh
   python -m ofscraper.commands.stash_sync "<profile>/.data" --apply
   ```

`<profile>/.data` holds one folder per creator, each with a `user_data.db`. To sync a single creator, pass that creator's `user_data.db` instead.

The report is JSON. For each creator, it counts:

| Count | Meaning |
|---|---|
| `to_update` / `updated` | Files that would be, or were, changed in Stash |
| `up_to_date` | Files that already had everything |
| `not_in_stash` | Downloaded files Stash hasn't indexed; scan, or check `--path-map` |
| `unsupported_type` | Audio, which Stash doesn't index |
| `galleries_to_create` / `galleries_created`, `galleries_to_update` / `galleries_updated`, `galleries_up_to_date` | Fansly galleries, counted the same way |

A few of the missing paths are listed under `not_in_stash_sample`.

### With PostgreSQL

If the scraper keeps its data in PostgreSQL (see [POSTGRESQL.md](POSTGRESQL.md)), the `user_data.db` files stop being updated. Pass `--postgres` in place of file paths to read PostgreSQL instead:

```sh
OFSC_DATABASE_URL=postgresql://user:password@host:5432/database \
  python -m ofscraper.commands.stash_sync --postgres --apply
```

- **Database address:** Uses `OFSC_DATABASE_URL` from the environment where the command is run. An address listed only in one of the scraper's `.env` files is not seen, because this command doesn't read the scraper's settings (`config.json`).
- **Filtering by site:** Every creator of both sites is synced by default. Add `--site onlyfans` or `--site fansly` to keep one site.
- **Filtering by creator:** `--creator NAME` keeps the creators `NAME` matches, and can be given more than once. `NAME` matches a creator's ID on either site, and any username a creator has or once had (in any case). It can match more than one creator, such as an ID used on both sites or a username that is also another creator's ID.
- **Read-only access:** PostgreSQL is only read. The login only needs `USAGE` on each site's schema and `SELECT` on its tables, and a login that may not read a site's tables is told so. The password is never printed; an error names the host, port, and database.
- **File paths:** Paths are the ones the scraper recorded where it ran. If this command or Stash runs somewhere else, use `--path-map` (see below).
- **Passing file paths:** Given paths, the command reads the files as before, and says so if `OFSC_DATABASE_URL` is set. Passing paths and `--postgres` together is refused.

The same rows produce the same results as from files, with these differences:

| Item | Difference with PostgreSQL |
|---|---|
| **Report `database` field** | Names the site and creator ID (`PostgreSQL: onlyfans, creator 123`) instead of a file path. |
| **Order** | Creators are processed a site at a time (OnlyFans first), and by ID within a site. From files, they follow folder order. |
| **Dates in another time zone** | PostgreSQL stores dates as moments and returns them in UTC. A date saved with another time zone can land on the previous or next day. For a file in two posts, this can also change which post's text is used. |
| **Empty dates** | An empty posted date in a file leaves the item without a date. PostgreSQL uses the day the media was made. |
| **Creator with no saved username** | Named by ID. From a file, named by the file's folder. |
| **File with two creators' rows** | From a file holding two creators (for example, from Merge Databases): both creators become one performer. PostgreSQL gives each creator their own performer. |
| **Creator with only a username saved** | Listed with no files when reading from a file, and left out when reading from PostgreSQL. |

## Options

| Option | Use |
|---|---|
| `--apply` | Write to Stash; without it, nothing is created or changed |
| `--postgres` | Read the PostgreSQL database `$OFSC_DATABASE_URL` names instead of `user_data.db` files; give no paths with it |
| `--site`, `--creator` | With `--postgres`: sync one site (`onlyfans` or `fansly`), or only creators matching an ID or username (see [With PostgreSQL](#with-postgresql)) |
| `--scan` | With `--apply`, have Stash scan the download folders first and wait for it |
| `--url` | Stash's GraphQL address (default `http://localhost:9999/graphql`, or `$STASH_URL`) |
| `--api-key` | Needed if Stash has a password: Settings → Security → API Key (or `$STASH_API_KEY`) |
| `--path-map LOCAL=STASH` | Map paths when Stash sees files under a different path, e.g. in Docker; repeatable |
| `--organized` | Also mark the items as organized in Stash |
| `--studio`, `--tag-prefix`, `--no-tags` | Change the studio and tags |

### Stash in Docker

If OF-Scraper saved files under `D:\OnlyFans` and Stash's container mounts that folder as `/data`:

```sh
python -m ofscraper.commands.stash_sync "<profile>/.data" --apply --path-map "D:\OnlyFans=/data"
```

A Windows `LOCAL` path ignores case and accepts `/` or `\` (`d:/onlyfans` works too); other paths must match exactly. The mapping also applies to `--scan`. Without it, Stash can't find any of the files: the report then says so in a `hint`, and nothing is created in Stash.

## Notes

- **Downloaded files only:** Only files OF-Scraper marked as downloaded are matched, by their exact path. Files you moved or renamed since won't be found.
- **Files posted more than once:** A file posted in multiple places (for example, in a message and again as a purchase) gets one item in Stash with the earliest date and all of its tags.
- **OnlyFans purchase URLs:** An OnlyFans bought message gets no URL, since a message has no public page. A file recorded only as a purchase gets its post's link when the database says the purchase was a post. Databases written by older versions of OF-Scraper don't record this, so those files get no link until a scan of your purchases fills the purchase type in. Since nothing is overwritten, the next run then adds the link.
- **Performer matching:** The creator's performer is matched by name (their username). Names are matched as Stash matches them: ignoring case and checking aliases, so a performer whose alias is the username is used for that creator. A performer you created under another name without that alias gets a second performer; merge them in Stash if so. The same goes for @mentioned Fansly creators.
- **Fansly @mentions:** Mentions come from `@name` in the caption. OF-Scraper also saves the post's list of tagged accounts, but this command doesn't read it yet: no real tagged post has been checked to see which field holds the username.
- **Wildcard characters (`_` and `%`) in names:** Stash reads `_` and `%` as wildcards when checking a new performer or studio, so it would take `pal_one` for an existing `Pal One`. Such a performer is created with the disambiguation `OnlyFans` or `Fansly`, and found again by its name on later runs. A studio has no disambiguation, so a `--studio` name like that stops the run with a message before anything in Stash is changed, in preview too; pick another name.
- **Finding Fansly galleries again:** A Fansly gallery is found again by its code (the post or message ID) in any studio, so you can move it to another studio. Only a gallery with no links or a `fansly.com` link is taken; one with the same code but another site's link is left alone and a Fansly gallery is created beside it. Changing a gallery's code makes the next run create a new one.
