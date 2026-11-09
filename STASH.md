# Organize downloads in Stash

[Stash](https://stashapp.cc) is a self-hosted media library. It indexes your
download folders, but on its own it only knows file names. This command copies
what OF-Scraper recorded about each file into Stash, for OnlyFans and Fansly downloads:

| Field | OnlyFans | Fansly |
|---|---|---|
| **Performers** | the creator, with a link to their OnlyFans page | the creator, with a link to their Fansly page, and anyone @mentioned in the caption |
| **Studio** | `OnlyFans` | `Fansly` |
| **Date** | when the post or message was posted | the same |
| **Title and details** | the caption's first line, and the full caption | the same |
| **Code** | the post ID (none for profile pictures) | the Fansly media ID |
| **URL** | the post's page, for timeline posts and bought posts | `https://fansly.com/post/<id>` for timeline posts, and `https://fansly.com/messages/<conversation>/<id>` for messages |
| **Tags** | where the file came from, e.g. `OnlyFans Timeline`, `OnlyFans Messages` or `OnlyFans Paid` | the same with `Fansly`, plus `Fansly Preview` for preview media and the caption's #hashtags, lowercased |
| **Gallery** | none | one per post or message, holding its images and scenes |

Each Fansly gallery gets the post's or message's ID as its code, and the same
studio, performers, date, title, details, URL and tags (without `Fansly Preview`).
OnlyFans messages get no URL: a message has no public page. A Fansly message's
link needs its conversation ID. Databases written by older versions of
OF-Scraper don't have it, so such a message gets no URL until a messages scan
fills it in; the next run then adds the link. Fansly purchases aren't
posts, so their files get no gallery.

`--studio` and `--tag-prefix` replace the studio and tag prefix for every site;
`--no-tags` turns off all of these tags. A `--studio` used for both sites in one
run is created without a site link.

It only fills in empty fields and adds performers, the studio, tags and galleries.
Anything you've set in Stash is kept, so running it again changes nothing that's
already there.

It reads OF-Scraper's databases offline and never contacts OnlyFans or Fansly.
A Fansly database is recognised by the site OF-Scraper records in it; Fansly runs
keep their databases in a `Fansly` folder under `.data` by default.

## Run it

Stash must be running, and must already have scanned your download folders, or
use `--scan` to have it scan them first.

Preview what would change:

```sh
python -m ofscraper.commands.stash_sync "<profile>/.data"
```

Then apply it:

```sh
python -m ofscraper.commands.stash_sync "<profile>/.data" --apply
```

`<profile>/.data` holds one folder per creator, each with a `user_data.db`.
To do a single creator, pass that creator's `user_data.db` instead.

The report is JSON. For each creator it counts:

| Count | Meaning |
|---|---|
| `to_update` / `updated` | files that were, or would be, changed in Stash |
| `up_to_date` | files that already had everything |
| `not_in_stash` | downloaded files Stash hasn't indexed; scan, or check `--path-map` |
| `unsupported_type` | audio, which Stash doesn't index |
| `galleries_to_create` / `galleries_created`, `galleries_to_update` / `galleries_updated`, `galleries_up_to_date` | Fansly galleries, counted the same way |

A few of the missing paths are listed under `not_in_stash_sample`.

## Options

| Option | Use |
|---|---|
| `--apply` | write to Stash; without it, nothing is created or changed |
| `--scan` | with `--apply`, have Stash scan the download folders first and wait for it |
| `--url` | Stash's GraphQL address (default `http://localhost:9999/graphql`, or `$STASH_URL`) |
| `--api-key` | needed if Stash has a password: Settings → Security → API Key (or `$STASH_API_KEY`) |
| `--path-map LOCAL=STASH` | when Stash sees the files under a different path, e.g. in Docker; repeatable |
| `--organized` | also mark the items as organized in Stash |
| `--studio`, `--tag-prefix`, `--no-tags` | change the studio and tags |

### Stash in Docker

If OF-Scraper saved files under `D:\OnlyFans` and Stash's container mounts that
folder as `/data`:

```sh
python -m ofscraper.commands.stash_sync "<profile>/.data" --apply --path-map "D:\OnlyFans=/data"
```

A Windows `LOCAL` path ignores case and accepts `/` or `\` (`d:/onlyfans` works
too); other paths must match exactly. The mapping also applies to `--scan`. Without it, Stash can't find any of the
files: the report then says so in a `hint`, and nothing is created in Stash.

## Notes

- Only files OF-Scraper marked as downloaded are matched, by their exact path.
  Files you've moved or renamed since won't be found.
- A file posted more than once (for example in a message and again as a
  purchase) gets one item in Stash with the earliest date and all of its tags.
- An OnlyFans bought message gets no URL, since a message has no public page.
  A file recorded only as a purchase gets its post's link when the database
  says the purchase was a post. Databases written by older versions of
  OF-Scraper don't say, so there such a file gets no link until a scan of your
  purchases fills the purchase type in. Since nothing is overwritten, the
  next run then adds the link.
- The creator's performer is matched by name, which is their username. A
  performer you created yourself under another name gets a second one; merge them
  in Stash if so. The same goes for @mentioned Fansly creators.
- Fansly @mentions come from `@name` in the caption. OF-Scraper also saves the
  post's list of tagged accounts, but this command doesn't read it yet: no real
  tagged post has been checked to see which field holds the username.
- Names are matched as Stash matches them: ignoring case, and also by alias, so a
  performer whose alias is the username is used for that creator.
- Stash reads `_` and `%` in a name as wildcards when it checks a new performer or
  studio, so it would take `pal_one` for an existing `Pal One`. Such a performer
  is created with the disambiguation `OnlyFans` or `Fansly`, and found again by its
  name on later runs. A studio has no disambiguation, so a `--studio` name like
  that stops the run with a message before anything in Stash is changed, in
  preview too; pick another name.
- A Fansly gallery is found again by its code (the post or message ID), in any
  studio, so you can move it to another studio. Only a gallery with no links or
  a fansly.com link is taken; one with the same code but another site's link is
  left alone and a Fansly gallery is made beside it. Changing a gallery's code
  makes the next run create a new one.
