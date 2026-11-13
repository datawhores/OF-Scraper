<div align="center">

<img src="https://raw.githubusercontent.com/cloakedkeys/OF-Scraper-Community/main/media/icon.png" alt="OF-Scraper-Community" width="140">

# OF-Scraper-Community

**Download what you're subscribed to on OnlyFans and Fansly, from the command line.**

A community-maintained fork of [datawhores/OF-Scraper](https://github.com/datawhores/OF-Scraper), with the fixes users have reported since upstream stopped updating.

[![Latest release](https://img.shields.io/github/v/release/cloakedkeys/OF-Scraper-Community?label=release&color=00a8e8)](https://github.com/cloakedkeys/OF-Scraper-Community/releases/latest)
[![Tests](https://github.com/cloakedkeys/OF-Scraper-Community/actions/workflows/codecov.yml/badge.svg)](https://github.com/cloakedkeys/OF-Scraper-Community/actions/workflows/codecov.yml)
[![codecov](https://codecov.io/gh/cloakedkeys/OF-Scraper-Community/branch/main/graph/badge.svg)](https://codecov.io/gh/cloakedkeys/OF-Scraper-Community)
[![Python 3.11 to 3.15](https://img.shields.io/badge/python-3.11%20%E2%80%93%203.15-3776ab?logo=python&logoColor=white)](#install)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-2496ed?logo=docker&logoColor=white)](https://github.com/cloakedkeys/OF-Scraper-Community/pkgs/container/of-scraper-community)
[![Docs](https://img.shields.io/badge/docs-gitbook-00a8e8?logo=gitbook&logoColor=white)](https://cloakedkeys.gitbook.io/ofsc)
[![License: MIT](https://img.shields.io/github/license/cloakedkeys/OF-Scraper-Community?color=lightgrey)](https://github.com/cloakedkeys/OF-Scraper-Community/blob/main/LICENSE)

[Install](#install) · [Getting started](#getting-started) · [Docs](https://cloakedkeys.gitbook.io/ofsc) · [FAQ](#faq) · [Reference](https://github.com/cloakedkeys/OF-Scraper-Community/blob/main/reference/README.md) · [Releases](https://github.com/cloakedkeys/OF-Scraper-Community/releases) · [Report a problem](#reporting-a-problem)

</div>

---

> **OF-Scraper can't get past paywalls.** You need a subscription to a creator, and you can only download what your account can already see.

## Why this fork

Upstream hasn't been updated since April 2026. This fork keeps it working:

| | |
|---|---|
| 🔐 **DRM video** | Protected videos download and decrypt again, with ffmpeg 6, 7 and 8+. |
| 🌐 **Fansly** | Posts, messages, purchases, labels (profile walls) and livestreams, alongside OnlyFans. |
| 🐍 **Python 3.11 to 3.15** | Tested in CI on the oldest and newest supported versions. |
| 🛠️ **Bug fixes** | Dozens of reported bugs fixed, with tests that guard them. See the [releases](https://github.com/cloakedkeys/OF-Scraper-Community/releases). |
| 📖 **Full reference** | Every command, option, setting and database table [documented](https://github.com/cloakedkeys/OF-Scraper-Community/blob/main/reference/README.md). |

## Install

This fork is on PyPI as **`ofscraper-community`**. The command is still `ofscraper`.

**Requirements:**
- Python 3.11 or higher.
- ffmpeg 6 or newer, only for protected (DRM) videos.

**With uv (recommended)**

```
uv tool install ofscraper-community
```

**With pipx**

```
pipx install ofscraper-community
```

**With pip**

```
pip install ofscraper-community
```

**Without Python:** download the Windows, macOS or Linux build from the [latest release](https://github.com/cloakedkeys/OF-Scraper-Community/releases/latest).

**Docker**

```
docker pull ghcr.io/cloakedkeys/of-scraper-community:latest
```

### Updating

```
uv tool upgrade ofscraper-community
pipx upgrade ofscraper-community
pip install -U ofscraper-community
```

Use the one that matches how you installed it.

### Switching from `ofscraper`

The `ofscraper` package on PyPI is upstream's old version, without these fixes. It installs the same `ofscraper` command, so uninstall it first, using the tool you installed it with:

- pip: `pip uninstall ofscraper`
- uv (this includes the fork installed from GitHub before it was on PyPI): `uv tool uninstall ofscraper`
- pipx: `pipx uninstall ofscraper`

Then install `ofscraper-community` as above. If pip already has both, uninstall both, then install `ofscraper-community` again.

### Unreleased changes

To get what's on `main` before it's released, install from this repo. To update, run the same command again.

```
uv tool install --force git+https://github.com/cloakedkeys/OF-Scraper-Community
pip install git+https://github.com/cloakedkeys/OF-Scraper-Community
```

## Getting started

Run `ofscraper` and follow the prompts. The first run asks for your auth details and creates a config file in `~/.config/ofscraper/`.

📖 **[Read the docs](https://cloakedkeys.gitbook.io/ofsc)** for setup, auth, config options, commands and the full [technical reference](https://cloakedkeys.gitbook.io/ofsc/reference).

## FAQ

<details>
<summary><b>Auth keeps failing, or it says "Double check auth info"</b></summary>

- Copy every value (`sess`, `auth_id`, `x-bc`, `user_agent`) again from the same browser while you're logged in to OnlyFans. They expire when you log out.
- `user_agent` must match that browser exactly.
- Make sure you're on the latest version of this fork.
- To stop the auth prompt from looping, add `--auth-fail` and the run quits on an auth error instead.

</details>

<details>
<summary><b>"No accounts found during scan"</b></summary>

Usually an auth problem, so check the auth answer above first. Then check you have an active subscription to the model, and that you aren't filtering it out with options like `--expired-subscription`.

</details>

<details>
<summary><b>Protected videos don't download, or leave <code>.part</code> / <code>tempvid</code> files</b></summary>

These videos need a CDM to decrypt them.

- Set up `cdm_options` in your config. See the [CDM guide](https://cloakedkeys.gitbook.io/ofsc/cdm-options).
- Install ffmpeg 6 or newer and put its full path in `binary_options` → `ffmpeg`.
- Paths copied with Windows' "Copy as path" (with quotes) work.

</details>

<details>
<summary><b>Files download fine but are counted as "failed"</b></summary>

Fixed in 3.15.0. This mostly happened when saving to a mapped or network drive. Update to the latest version.

</details>

<details>
<summary><b>Some messages or new posts are missing</b></summary>

A bug that skipped messages when using `--after` is fixed in 3.15.0. Update, then run again. To rescan a date range, add `--after YYYY-MM-DD`. Add `--force-all` as well if you want files you already have downloaded again.

</details>

<details>
<summary><b>ffmpeg isn't found even though it's installed</b></summary>

Put the full path to the ffmpeg program in `binary_options` → `ffmpeg` in your config, for example `C:\ffmpeg\bin\ffmpeg.exe`. An empty setting means "not set".

</details>

<details>
<summary><b>It says to update to 3.14.7</b></summary>

That's upstream's PyPI version, which is older than this fork. Version 3.15.0 and later no longer show that message.

</details>

<details>
<summary><b>Two files saved with the same name overwrote each other</b></summary>

Newer versions save the second one as `name_<media_id>` instead. To recover files lost to this in older versions, see [Collision Recovery](https://github.com/cloakedkeys/OF-Scraper-Community/blob/main/COLLISION_RECOVERY.md).

</details>

## Fork-only features

- **Skip a model during `--scrape-paid`:** `--excluded-username` now works with `--scrape-paid`. Separate several names with commas.

  ```
  ofscraper --scrape-paid --excluded-username modelname,othermodel
  ```

- **Start the next daemon pass early (Docker/Linux):** while the daemon is waiting between passes, send `SIGUSR1`.

  ```
  docker kill --signal=SIGUSR1 <container>
  ```

- **Organize downloads in Stash:** copy each download's creator, date, caption and source into [Stash](https://stashapp.cc). See [Stash](https://github.com/cloakedkeys/OF-Scraper-Community/blob/main/STASH.md).

## Reporting a problem

Open an issue [in this repo](https://github.com/cloakedkeys/OF-Scraper-Community/issues), not upstream's.

Include a debug log. Run with `--log debug`, then attach the newest file from `~/.config/ofscraper/logging/`. Check it for personal details before posting.

The GUI is a separate project: [cjb900/OF-Scraper-GUI](https://github.com/cjb900/OF-Scraper-GUI).

## Disclaimer

This tool isn't affiliated with, endorsed by or sponsored by OnlyFans or Fansly. All OnlyFans trademarks belong to Fenix International Limited. You use it at your own risk and are responsible for how you use it.

## Credits

OF-Scraper was created by [datawhores](https://github.com/datawhores) and its contributors. This fork builds on their work.
