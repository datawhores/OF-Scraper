<div align="center">

<img src="media/icon.png" alt="OF-Scraper" width="140">

# OF-Scraper

**Download what you're subscribed to on OnlyFans and Fansly, from the command line.**

[![Latest release](https://img.shields.io/github/v/release/datawhores/OF-Scraper?label=release&color=00a8e8)](https://github.com/datawhores/OF-Scraper/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/ofscraper-community?label=pypi&color=3776ab)](https://pypi.org/project/ofscraper-community/)
[![Python 3.11 to 3.15](https://img.shields.io/badge/python-3.11%20%E2%80%93%203.15-3776ab?logo=python&logoColor=white)](#-install)
[![codecov](https://codecov.io/gh/datawhores/OF-Scraper/branch/main/graph/badge.svg?token=U1F1PQ7LGM)](https://codecov.io/gh/datawhores/OF-Scraper)
[![Discord](https://img.shields.io/badge/discord-join-5865f2?logo=discord&logoColor=white)](https://discord.gg/wN7uxEVHRK)

[Install](#-install) · [Docs](https://cloakedkeys.gitbook.io/ofsc) · [Help](#-help) · [Releases](https://github.com/datawhores/OF-Scraper/releases) · [Discord](https://discord.gg/wN7uxEVHRK) · [Support](#-support)

</div>

---

> [!IMPORTANT]
> **OF-Scraper can't bypass paywalls.** You need a subscription to a creator, free or paid, and you can only download what your account can already see.

![OF-Scraper in a terminal](https://user-images.githubusercontent.com/67020411/227816586-fb685959-cd3f-45af-adea-14773b7154f9.png)

## ✨ Features

| | |
|---|---|
| 📥 **Downloads** | Posts, messages, stories, highlights, purchases, streams and labels. Resumes where it stopped, even after an IP change. |
| 🔐 **DRM video** | Protected videos download and decrypt, with ffmpeg 6, 7 and 8+. |
| 🌐 **Fansly** | Posts, messages, purchases, labels and livestream recording, alongside OnlyFans. |
| 🔎 **Filters** | Choose exactly what to download by date, type, length, size, price, text and more. |
| 🗂️ **Check table** | Browse a creator's media, pick what you want, and download only that. |
| ❤️ **Bulk actions** | Like or unlike posts in bulk. |
| 🐳 **Runs anywhere** | PyPI, Windows/macOS/Linux builds, or Docker, with a daemon mode for scheduled runs. |

## 📦 Install

This version is on PyPI as **`ofscraper-community`**. The command is `ofscraper`.

```
uv tool install ofscraper-community
```

<details>
<summary><b>Other ways to install, update or switch</b></summary>

**Requirements:** Python 3.11 to 3.15, and ffmpeg 6 or newer for DRM-protected videos.

**pipx or pip**

```
pipx install ofscraper-community
pip install ofscraper-community
```

**Update**

```
uv tool upgrade ofscraper-community
pipx upgrade ofscraper-community
pip install -U ofscraper-community
```

**Coming from `ofscraper`:** the old `ofscraper` package on PyPI stops at 3.14.7. Both install the same `ofscraper` command, so uninstall the old one first (`uv tool uninstall ofscraper`, `pipx uninstall ofscraper` or `pip uninstall ofscraper`). Your config, auth and databases are used as they are.

**Without Python:** download the Windows, macOS or Linux build from the [latest release](https://github.com/datawhores/OF-Scraper/releases/latest). A Docker image is also available.

</details>

## 🚀 Getting started

Run `ofscraper` and follow the prompts. The first run asks for your auth details and creates a config file in `~/.config/ofscraper/`.

📖 **[Read the docs](https://cloakedkeys.gitbook.io/ofsc)** for setup, auth, config options and commands. Every command, option and setting is also listed in the [reference](reference/README.md). Docs for 3.14 and earlier are [here](https://of-scraper.gitbook.io/of-scraper).

## 🆘 Help

<details>
<summary><b>Auth keeps failing</b></summary>

- Copy `sess`, `auth_id`, `x-bc` and `user_agent` again from the browser you're logged in with. They stop working when you log out, and `user_agent` must match that browser exactly.
- Make sure you're on the latest release. The auth check says why it failed: a logged-out session, an unusable dynamic rule, or a network error.
- If one dynamic rule keeps failing, try another with `dynamic-mode-default` in your config.

</details>

<details>
<summary><b>Protected videos stay as <code>.part</code> files</b></summary>

- Set up `cdm_options` in your config. See the [CDM guide](https://cloakedkeys.gitbook.io/ofsc/cdm-options).
- Install ffmpeg 6 or newer and put its full path in `binary_options` → `ffmpeg`.

</details>

<details>
<summary><b>Migrating from DIGITALCRIMINALS' script</b></summary>

OF-Scraper is built to make the move easy. See the [Migration Guide](MIGRATION.md).

</details>

<details>
<summary><b>Reporting a bug or asking for a feature</b></summary>

- Open an [issue](https://github.com/datawhores/OF-Scraper/issues), or ask in the [Discord](https://discord.gg/wN7uxEVHRK).
- Bug reports need a log (run with `--log debug`) and your config. Reports without them will be closed.
- Feature requests are welcome as issues or in [Discord Suggestions](https://discord.com/channels/1093562233612673097/1094440464091975780).
- For a private report, open a ticket in the Discord ticket channel. Only you and the admins can see it.

</details>

## 📜 About

OF-Scraper started as a fork of the original onlyfans-scraper. With support from the community and steady updates, the code has been largely rewritten since. Some changes are listed in [CHANGES.md](CHANGES.md); the rest are in the commit history and the [release notes](https://github.com/datawhores/OF-Scraper/releases).

## 💖 Support

If OF-Scraper is useful to you, you can support its development:

<a href="https://www.buymeacoffee.com/datawhores"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" height="41"></a>

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

## ⚖️ Disclaimers

1. This tool isn't affiliated, associated or partnered with OnlyFans or Fansly in any way, and isn't authorized, endorsed or sponsored by them. All OnlyFans trademarks belong to Fenix International Limited.
2. This is a theoretical program for educational purposes only. It may or may not work. If you use it, you accept full responsibility and indemnify the creator, hosts, contributors and everyone else involved from any and all responsibility.
