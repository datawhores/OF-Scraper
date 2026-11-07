# OF-Scraper-Community

[![codecov](https://codecov.io/gh/cloakedkeys/OF-Scraper-Community/branch/main/graph/badge.svg)](https://codecov.io/gh/cloakedkeys/OF-Scraper-Community)

A community-maintained fork of [datawhores/OF-Scraper](https://github.com/datawhores/OF-Scraper), a command-line tool for downloading media from OnlyFans accounts, and now Fansly Accounts you are subscribed to.

Upstream hasn't been updated since April 2026. This fork collects the fixes users have reported since then, including DRM video, ffmpeg 8+ and Python 3.15 support.

**OF-Scraper can't get past paywalls.** You need a subscription to a model, and you can only download what your account can already see.

## Install

Install from this repo. The `ofscraper` package on PyPI is upstream's last release and doesn't have these fixes.

**With uv (recommended):**

```
uv tool install --force git+https://github.com/cloakedkeys/OF-Scraper-Community
```

**With pip:**

```
pip install git+https://github.com/cloakedkeys/OF-Scraper-Community
```

**Without Python:** download the Windows, macOS or Linux build from the [latest release](https://github.com/cloakedkeys/OF-Scraper-Community/releases/latest).

**Docker:**

```
docker pull ghcr.io/cloakedkeys/of-scraper-community:latest
```

Python 3.11 to 3.15 is supported. Protected (DRM) videos also need ffmpeg 6 or newer.

To update, run the same install command again.

## Getting started

Run `ofscraper` and follow the prompts. The first run asks for your auth details and creates a config file in `~/.config/ofscraper/`.

The [upstream documentation](https://of-scraper.gitbook.io/of-scraper) covers setup, auth, config options and commands. It still applies to this fork, apart from the install steps above.

## FAQ

### Auth keeps failing, or it says "Double check auth info"

- Copy every value (`sess`, `auth_id`, `x-bc`, `user_agent`) again from the same browser while you're logged in to OnlyFans. They expire when you log out.
- `user_agent` must match that browser exactly.
- Make sure you're on the latest version of this fork.
- To stop the auth prompt from looping, add `--auth-fail` and the run quits on an auth error instead.

### "No accounts found during scan"

Usually an auth problem, so check the auth answer above first. Then check you have an active subscription to the model, and that you aren't filtering it out with options like `--expired-subscription`.

### Protected videos don't download, or leave `.part` / `tempvid` files

These videos need a CDM to decrypt them.

- Set up `cdm_options` in your config. See the [CDM guide](https://of-scraper.gitbook.io/of-scraper/cdm-options).
- Install ffmpeg 6 or newer and put its full path in `binary_options` → `ffmpeg`.
- Paths copied with Windows' "Copy as path" (with quotes) work.

### Files download fine but are counted as "failed"

Fixed in 3.15.0. This mostly happened when saving to a mapped or network drive. Update to the latest version.

### Some messages or new posts are missing

A bug that skipped messages when using `--after` is fixed in 3.15.0. Update, then run again. To rescan a date range, add `--after YYYY-MM-DD`. Add `--force-all` as well if you want files you already have downloaded again.

### ffmpeg isn't found even though it's installed

Put the full path to the ffmpeg program in `binary_options` → `ffmpeg` in your config, for example `C:\ffmpeg\bin\ffmpeg.exe`. An empty setting means "not set".

### It says to update to 3.14.7

That's upstream's PyPI version, which is older than this fork. Version 3.15.0 and later no longer show that message.

### Two files saved with the same name overwrote each other

Newer versions save the second one as `name_<media_id>` instead. To recover files lost to this in older versions, see [Collision Recovery](COLLISION_RECOVERY.md).

## Fork-only features

- **Skip a model during `--scrape-paid`:** `--excluded-username` now works with `--scrape-paid`. Separate several names with commas.

  ```
  ofscraper --scrape-paid --excluded-username modelname,othermodel
  ```

- **Start the next daemon pass early (Docker/Linux):** while the daemon is waiting between passes, send `SIGUSR1`.

  ```
  docker kill --signal=SIGUSR1 <container>
  ```

## Reporting a problem

Open an issue [in this repo](https://github.com/cloakedkeys/OF-Scraper-Community/issues), not upstream's.

Include a debug log. Run with `--log debug`, then attach the newest file from `~/.config/ofscraper/logging/`. Check it for personal details before posting.

The GUI is a separate project: [cjb900/OF-Scraper-GUI](https://github.com/cjb900/OF-Scraper-GUI).

## Disclaimer

This tool isn't affiliated with, endorsed by or sponsored by OnlyFans. All OnlyFans trademarks belong to Fenix International Limited. You use it at your own risk and are responsible for how you use it.

## Credits

OF-Scraper was created by [datawhores](https://github.com/datawhores) and its contributors. This fork builds on their work.
