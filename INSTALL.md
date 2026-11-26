# Install and update

A first install, in order, and how to update without breaking a working one. Use one install tool and stick with it: most broken installs come from mixing pip, pipx and uv, or from having two packages installed at once.

## 1. Install

1. **Python 3.11 or newer.** 3.11 to 3.15 are tested. On 3.15, one dependency (`lz4`) has no prebuilt package yet and is built during the install, which needs a C compiler (on Windows, Microsoft's C++ build tools). On 3.11 to 3.14 it doesn't.
2. **One install tool.** uv is the recommended one; pipx and pip work too. Install OF-Scraper with it:

   ```sh
   uv tool install ofscraper
   ```

   or `pipx install ofscraper`, or `pip install ofscraper`.

This fork's package is **`ofscraper`**. [datawhores/OF-Scraper](https://github.com/datawhores/OF-Scraper) publishes the same code as **`ofscraper`**. Both install the same `ofscraper` command, so have only one of them. If `ofscraper` is already installed, uninstall it first, with the tool that installed it (`uv tool uninstall ofscraper`, `pipx uninstall ofscraper` or `pip uninstall ofscraper`). `uv tool list`, `pipx list` and `pip list` show what each tool has installed. See [Installed as `ofscraper`?](README.md#installed-as-ofscraper) for keeping `ofscraper` instead.

**Optional extras** go in brackets after the name, for example `uv tool install "ofscraper[ffmpeg]"`:

| Extra | What it adds |
|---|---|
| `ffmpeg` | A bundled ffmpeg (pyffmpeg), used when no other ffmpeg is found. |
| `postgres` | [PostgreSQL](POSTGRESQL.md) support. |
| `live` | Recording OnlyFans livestreams. Download its Chromium browser afterwards, as below. |

The `live` extra also needs Playwright's Chromium browser, downloaded with `playwright install chromium`. uv and pipx don't put Playwright's own `playwright` command on your `PATH` unless asked to, so install with:

| Tool | Install | Then |
|---|---|---|
| uv | `uv tool install "ofscraper[live]" --with-executables-from playwright` | `playwright install chromium` |
| pipx | `pipx install --include-deps "ofscraper[live]"` | `playwright install chromium` |
| pip | `pip install "ofscraper[live]"` | `playwright install chromium` |

**Planned** ([#797](https://github.com/datawhores/OF-Scraper/pull/797), [#798](https://github.com/datawhores/OF-Scraper/pull/798), not released yet): at a terminal, the first `--live` run offers to install Playwright and Chromium, and the first run with `OFSC_DATABASE_URL` set offers to install the PostgreSQL driver where it's missing (the daemon, cron and `sudo` runs print the install command instead). The driver also comes with the install on most systems. So the `live` and `postgres` extras are only needed where that offer is turned off (`OFSC_INSTALL_EXTRAS=False`), declined, not made, or fails. Until a release includes them, install the extras as above.

Without Python, download a build for Windows, macOS or Linux from the [releases](https://github.com/datawhores/OF-Scraper/releases), or use the Docker image (`ghcr.io/datawhores/of-scraper`).

The first run of `ofscraper` asks for your auth details and creates `config.json` in `~/.config/ofscraper/`. The settings below go in that file.

## 2. ffmpeg

ffmpeg is needed for protected (DRM) videos, Fansly streams and recording livestreams (`--live`). Everything else downloads without it.

- **Version:** any build of version 6 or newer (6, 7 and 8 all work). A version older than 6 is skipped with a warning.
- **Build:** use the full build.
- **Setting:** put the path to the ffmpeg program itself, not its folder, in `binary_options` → `ffmpeg`. On Windows that is the `.exe`:

  ```json
  "binary_options": {
      "ffmpeg": "C:\\ffmpeg\\bin\\ffmpeg.exe"
  }
  ```

  In JSON, each `\` in a Windows path is written twice. Quotes around the path, as Windows' "Copy as path" adds, are removed.

If the setting is empty, the path in the `OFSC_FFMPEG_DEFAULT` environment variable is used instead. If that path doesn't point to a working ffmpeg 6+, OF-Scraper tries the bundled ffmpeg from the `ffmpeg` extra, and then `ffmpeg` on your `PATH`.

## 3. DRM keys

Protected videos are decrypted with your own Widevine CDM files. Set these in `cdm_options`:

```json
"cdm_options": {
    "key-mode-default": "manual",
    "client-id": "C:\\cdm\\client_id.bin",
    "private-key": "C:\\cdm\\private_key.pem"
}
```

- **`key-mode-default`** should be `manual`. `cdrm` is deprecated, and each run that uses it warns you. Its default server, cdrm-project.com, no longer works and isn't contacted. With `cdrm`, protected videos are skipped when the `OFSC_CDRM_URL` environment variable is empty or left at that default. Only a server you run yourself, set in `OFSC_CDRM_URL` as an `http://` or `https://` address, still works, and it is sent your request headers, cookies included. A config that already says `cdrm` keeps it until you change it, so check this after setting up your CDM files.
- **`client-id`** is the path to `client_id.bin`, and **`private-key`** the path to `private_key.pem`.

See the [CDM guide](https://cloakedkeys.gitbook.io/ofsc/setup/cdm-options) for getting these files.

## 4. Update

Update with the same tool you installed with:

```sh
uv tool upgrade ofscraper
pipx upgrade ofscraper
pip install -U ofscraper
```

Updating replaces the program only. Your config, auth and databases in `~/.config/ofscraper/` stay as they are. To be safe, copy that folder before a big update.

**To go back to a previous version**, install it by its number (the [releases](https://github.com/datawhores/OF-Scraper/releases) list them). For example, for 3.17.1:

| Tool | Install 3.17.1 | Back to the latest |
|---|---|---|
| uv | `uv tool install ofscraper==3.17.1` | `uv tool install ofscraper@latest` |
| pipx | `pipx install --force ofscraper==3.17.1` | `pipx install --force ofscraper` |
| pip | `pip install ofscraper==3.17.1` | `pip install -U ofscraper` |

With uv, a version installed by number stays on it: `uv tool upgrade` leaves it alone, so use the `@latest` command to update again. The release builds and the Docker image are also kept for each version (for example `ghcr.io/datawhores/of-scraper:3.17.1`).

## 5. Check that it works

1. `ofscraper --version` prints the version. If it prints an old one, another install comes first on your `PATH`; see step 1.
2. Do a short run on one creator you're subscribed to, limited to a few recent images:

   ```sh
   ofscraper -a download -o timeline -u <creator> --after "1 week ago" -mt images
   ```

   To check ffmpeg and your DRM keys, run it again with `-mt videos` on a creator who has protected videos.

If something fails, run it again with `--log debug` and look in the newest file in `~/.config/ofscraper/logging/`. To report a problem, see [Reporting a problem](README.md#reporting-a-problem).
