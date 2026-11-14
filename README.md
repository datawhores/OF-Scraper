<div align="center">

# OF-Scraper

**A command-line tool to download media from OnlyFans and Fansly, and to like or unlike posts in bulk.**

[![Latest release](https://img.shields.io/github/v/release/datawhores/OF-Scraper?label=release&color=dark_green)](https://github.com/datawhores/OF-Scraper/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/ofscraper-community?label=pypi%20ofscraper-community)](https://pypi.org/project/ofscraper-community/)
[![codecov](https://codecov.io/gh/datawhores/OF-Scraper/branch/main/graph/badge.svg?token=U1F1PQ7LGM)](https://codecov.io/gh/datawhores/OF-Scraper)
[![Discord](https://img.shields.io/badge/discord-join-5865f2?logo=discord&logoColor=white)](https://discord.gg/wN7uxEVHRK)

</div>

> [!IMPORTANT]
> 1. OF-Scraper can't bypass paywalls.
> 2. You need a subscription to a creator, free or paid. Creators can't be scraped anonymously.

![OF-Scraper in a terminal](https://user-images.githubusercontent.com/67020411/227816586-fb685959-cd3f-45af-adea-14773b7154f9.png)

## Contents

- [Install](#install)
- [Documentation](#documentation)
- [Auth problems](#auth-problems)
- [About](#about)
- [Migrating from DIGITALCRIMINALS' script](#migrating-from-digitalcriminals-script)
- [Issues and feature requests](#issues-and-feature-requests)
- [Discord](#discord)
- [Support](#support)
- [Disclaimers](#disclaimers)

## Install

The current version is on PyPI as **`ofscraper-community`**. The command is still `ofscraper`. The older `ofscraper` package on PyPI stops at 3.14.7.

Requirements: Python 3.11 to 3.15, and ffmpeg 6 or newer for DRM-protected videos.

```
uv tool install ofscraper-community
```

`pipx install ofscraper-community` and `pip install ofscraper-community` work too. To update, use `uv tool upgrade`, `pipx upgrade` or `pip install -U` with the same name.

**Coming from `ofscraper`:** both packages install the same `ofscraper` command, so uninstall the old one first (`uv tool uninstall ofscraper`, `pipx uninstall ofscraper` or `pip uninstall ofscraper`). Your config, auth and databases are used as they are.

**Without Python:** Windows, macOS and Linux builds are attached to each [release](https://github.com/datawhores/OF-Scraper/releases). A Docker image is also available.

## Documentation

- [Docs](https://cloakedkeys.gitbook.io/ofsc): installation, running the tool, auth, config options and commands, for the current version.
- [Reference](reference/README.md): every command, option, setting and database table.
- [Older docs](https://of-scraper.gitbook.io/of-scraper) for versions up to 3.14.

## Auth problems

- Copy `sess`, `auth_id`, `x-bc` and `user_agent` again from the browser you're logged in with. They stop working when you log out, and `user_agent` must match that browser exactly.
- Make sure you're on the latest release. The auth check says why it failed: a logged-out session, an unusable dynamic rule, or a network error.
- If one dynamic rule keeps failing, try another with `dynamic-mode-default` in your config.

If it still fails, open an [issue](https://github.com/datawhores/OF-Scraper/issues) with a log from a current build.

## About

OF-Scraper started as a fork of the original onlyfans-scraper. With support from the community and steady updates, the code has been largely rewritten since. Some of the changes are listed in [CHANGES.md](CHANGES.md); the rest are in the commit history and the [release notes](https://github.com/datawhores/OF-Scraper/releases).

It's built for an easy move from DIGITALCRIMINALS' script, and it has a wide range of filters for choosing exactly which content to download.

## Migrating from DIGITALCRIMINALS' script

See the [Migration Guide](MIGRATION.md).

## Issues and feature requests

Open an [issue](https://github.com/datawhores/OF-Scraper/issues) in this repo, or ask in the [Discord](#discord).

- Feature requests are welcome as issues, or in [Discord Suggestions](https://discord.com/channels/1093562233612673097/1094440464091975780).
- Bug reports need a log and your config. Reports without them will be closed.
- For a private report, open a ticket in the Discord ticket channel. Only you and the admins can see it.

## Discord

[Join the Discord](https://discord.gg/wN7uxEVHRK)

## Support

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/datawhores)

<table>
  <tr>
    <th>BTC</th>
    <th>ETH</th>
  </tr>
  <tr>
    <td><a href="https://raw.githubusercontent.com/datawhores/OF-Scraper/main/donate/btc"><img src="https://github.com/datawhores/OF-Scraper/assets/67020411/c96d0c22-b015-4ffc-b09e-6f246ae10fba" alt="BTC address" height="100"></a></td>
    <td><a href="https://raw.githubusercontent.com/datawhores/OF-Scraper/main/donate/eth"><img src="https://github.com/datawhores/OF-Scraper/assets/67020411/d9df33e9-a8ac-4574-91dd-1cb5a20f7201" alt="ETH address" height="100"></a></td>
  </tr>
</table>

## Disclaimers

1. This tool isn't affiliated, associated or partnered with OnlyFans or Fansly in any way, and isn't authorized, endorsed or sponsored by them. All OnlyFans trademarks belong to Fenix International Limited.
2. This is a theoretical program for educational purposes only. It may or may not work. If you use it, you accept full responsibility and indemnify the creator, hosts, contributors and everyone else involved from any and all responsibility.
