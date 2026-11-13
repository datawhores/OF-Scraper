# Guidance for coding agents

Read this before changing anything in this repository. It's written for AI coding agents, but it applies to anyone. `CLAUDE.md` imports this file.

## What this repo is
`cloakedkeys/OF-Scraper-Community` is a **public**, community-maintained fork of `datawhores/OF-Scraper`, a Python CLI that downloads content from OnlyFans accounts the user has access to, including Widevine-protected (DRM) video. The upstream maintainer has abandoned the project, so fixes are collected here.

Remotes:
- `origin`: this fork. PRs target `main`.
- `contrib`: `cloakedkeys/OF-Scraper-upstream`, a fork used only to open PRs against upstream.
- `upstream`: `datawhores/OF-Scraper`.

Community fixes for the GUI patch go to `cjb900/OF-Scraper-GUI`.

## Hard rules
1. **Upstream PRs carry only the intended fix.** Upstream is unmaintained, and the community shares fixes, DRM fixes included, so the fork's DRM code (`alt_download.py`, `keyhelpers.py`, `media.py` `license()`) may be made public. Cut each upstream PR from upstream's branch and cherry-pick only that fix, so other fork changes don't ride along.
2. **No secrets or personal data in the repo, commits, issues or PR text.** Everything here is public. That covers `auth.json`, cookies, CDM files (`private_key.pem`, `client_id.bin`), content keys, downloaded or captured media, logs, and creator usernames (write "a creator"). Before every push or post, grep the staged diff, commit messages and PR text for usernames, home-directory paths (`C:\Users\...`, `/home/...`) and keys. Editing a description afterwards doesn't remove it: GitHub keeps the earlier version in the edit history. Write paths relative to the repo or use placeholders like `{home_directory}`.
3. **Don't merge.** Open a PR, verify it, state the merge order, and stop. Merge only PRs a maintainer explicitly names in an instruction to you, using a squash merge. Never push code to `main` directly and never force-push it. The exception is `AGENTS.md` (and `CLAUDE.md`): changes to these docs are committed straight to `main` without a PR.
4. **Commit messages carry no AI attribution** (no `Co-Authored-By` agent lines or "generated with" notes). A PR description may say it was AI-generated.
5. **Don't change the TLS fingerprint by accident.** `ofscraper/managers/sessionmanager/cert.py` shapes the ClientHello sent to OnlyFans: a cipher order seeded per account, and `context.options` *assigned*, not or-ed, which leaves the TLS 1.3 session ID empty. Treat any change to SSL options, ciphers, curves or the HTTP client stack as fingerprint-affecting, and compare ClientHellos captured before and after **through the transport that actually sends them** (httpx with HTTP/2 adds ALPN; aiohttp differs from a raw socket). A raw-socket capture isn't representative. The `custom` `ssl_verify` mode is the only one that uses `cert.py`. See issue #110.
6. **Don't send OnlyFans credentials to third parties.** `--key-mode cdrm` posts the request headers, cookies included, to cdrm-project.com. Don't run a live cdrm decrypt without the maintainer's approval.

## Setup
- **Python:** `requires-python` is `>=3.11, <3.16`. CI tests on 3.11 (the minimum) and 3.15.2. On 3.15, lz4 and faust-cchardet have no wheels and build from source, so a C compiler is needed (MSVC on Windows).
- **Environment:** `uv sync --python 3.15 --extra test` (or `--python 3.11` for the minimum) creates `.venv` from `uv.lock`. Don't change `uv.lock` unless you're changing dependencies; when you do, use `uv lock -P <package>` rather than a full upgrade.
- **Parallel work:** use git worktrees, one per branch (e.g. `../ofs-wt/<name>`). Run code from a worktree with `PYTHONPATH=.` and the main checkout's venv.

## Tests
- **Run:** `python -m pytest test` (`test/legacy` is excluded by config). Warnings are errors (`filterwarnings` in `pyproject.toml`), so an invalid escape sequence, an unclosed file or sqlite connection, or an exception in a background thread fails the run. Fix the cause; use raw strings for Windows paths and `closing()` for sqlite connections (`with sqlite3.connect(...)` only commits, it doesn't close). Add a filter only for a third-party warning you can't fix, with a comment saying why. Every fix needs a test that fails without it; check that by running the test against the previous commit.
- **`test/conftest.py` handles two quirks you'll hit in scripts too:**
  - `ofscraper` parses `sys.argv` the first time settings are read, so clear it (`sys.argv = sys.argv[:1]`) before importing the app in a script, and never pass your script's own arguments on the command line. Use environment variables instead.
  - Importing a leaf module first can hit a circular import (`settings` ↔ `console` ↔ `config`). Import `ofscraper.main.open.load` or `ofscraper.__main__` first.
- **Settings in tests:** monkeypatch `settings.get_settings` with a `SimpleNamespace`. When you monkeypatch `of_env.getattr`, pass unknown keys through to the real function; returning `None` for everything breaks unrelated getters.
- **Time:** don't put timestamps exactly on a boundary. Windows' clock resolution hides off-by-milliseconds failures that show up on Linux CI.

## Running the app
```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python -c "from ofscraper.__main__ import main; main()" \
  --action download --posts messages -u <creator> --no-rich -l debug -p normal --force-all --after 2000 -mt images
```
- **Config and auth:** these live in the user's config directory (`~/.config/ofscraper/`, profile `main_profile`). All of the maintainer's creator accounts are approved for live tests. Don't edit their `config.json`; if a test needs different settings, use a temporary profile or environment variables, and restore anything you change.
- **`--after 2000`:** without it, a repeat run only scans messages newer than the last scan and finds nothing. `--force-all` re-downloads files that already exist.
- **Logs:** the console shows only the run summary. Debug output goes to `~/.config/ofscraper/logging/<profile>_<date>/`.
- **Big creators:** raise `--sem` for speed, and keep runs scoped with `-mt` and `--after`.

## Reference
[`reference/`](reference/README.md) lists every command, option, `config.json` key, environment default, output template placeholder and database table, with what each does, its default, and what it interacts with. Look things up there before tracing the code. It also covers where a setting's value comes from, what writes files, and the default folder layout. Most of it is generated by `scripts/reference/build_reference.py`.

## Code areas with non-obvious behaviour
- **Config getters** (`ofscraper/utils/config/data.py`, `utils/paths/common.py`): `auto_update_config` rebuilds `config.json` from these getters and **writes it back**. So a getter must return what belongs in the file. Apply environment fallbacks (e.g. `OFSC_FFMPEG_DEFAULT`) at runtime in `settings.merged_settings`, not in the getter, or they get saved into users' configs.
- **Environment defaults:** `of_env.getattr(key, default=None)` checks environment variables, then the custom config, then the defaults in `ofscraper/utils/of_env/values/`.
- **DRM flow:** the MPD is parsed, then the key comes from `keyhelpers` (manual CDM via pywidevine, or cdrm). `keyhelpers.un_encrypt` then runs `ffmpeg -decryption_key <key> -i x.part -codec copy x.mp4`, and `alt_download` merges the video and audio. A leftover `.part` file doesn't on its own mean DRM failed. The ordinary downloader (`main_download.py`) also writes `.part` files, and a transfer error can leave one behind. Find the failing stage in the debug log (transfer, key, decrypt or move) before diagnosing, and keep the `.part` while you do; it's what the next run resumes from.
- **ffmpeg:** DRM needs ffmpeg 6 or newer. ffmpeg 8+ copies the source's `pssh` box into the decrypted output, and `strip_pssh()` neutralises it. Media decrypted by 7.x and 8+ is otherwise identical (see PR #108). `get_ffmpeg()` tries the config path, then pyffmpeg, then `PATH`.
- **Async:** cached async properties on media objects are always accessed with `await`. Use `ofscraper.utils.context.run_async.run` for top-level coroutines.

## Docker
- **Layout:** two-stage `Dockerfile`; the runtime setup is in `scripts/entry/` (`entrypoint.sh`, `lib_user_setup.sh`, `lib_paths.sh`).
- **`docker compose exec` skips the entrypoint.** Anything the app needs in that workflow must be an `ENV` in the image, not only an entrypoint export.
- **bash always sets `UID`** (0 when running as root), so its value doesn't show whether one was passed in. `lib_user_setup.sh` checks the container's startup environment (`grep -qz '^UID=' /proc/$$/environ`) instead, which also keeps an explicit `UID=0`.
- **Build and test:** `docker buildx build --platform linux/amd64 --load -t ofs:test .`, then `docker run --rm ofs:test sh -c '...'`. arm64 builds run under QEMU, are slow and memory-hungry. For a single step, test it in a small throwaway Dockerfile.
- **From Git Bash on Windows:** set `MSYS_NO_PATHCONV=1`, or `-e VAR=/path` arguments get rewritten into Windows paths.

## CI
- **Tests:** `codecov.yml` runs on pull requests and on pushes to `main` (Python 3.11 and 3.15.2). It installs with `uv sync --frozen` from `uv.lock`, so CI tests exactly the locked versions; a dependency change must update the lockfile.
- **Images and releases:** `commit_bundler.yml` and `docker-daily.yml` run on **pushes to `main` only**, building binaries (kept as workflow artifacts, not released) and pushing images to the fork's registries. PR branches get only the test workflow, so test a branch's binary or image locally.
- **Releases:** pushing a version tag (`3.15.1` or `v3.15.1`) runs `commit_bundler.yml` for that tag and publishes one release named after it, with the binaries and generated notes. The binaries report the plain version, without a commit hash. The same run then publishes the package to PyPI as `ofscraper-community` (trusted publishing, environment `pypi`). A PyPI version can't be replaced, so push only one tag form per release: both forms would run it twice and the second upload fails.
- **Doc-only changes** (`*.md`, `docs/`, `media/`, `LICENSE`, issue templates) start no workflows. A push that also touches code runs everything as usual.
- **If a check fails with no steps run, read its annotation.** A billing or spending-limit refusal isn't a code failure. Report it, and run the test job locally on the PR head instead.

## PRs
- **Reference:** a PR that adds, renames or removes a command-line option, `config.json` key, environment default, placeholder or database column updates `scripts/reference/notes.py` and reruns `scripts/reference/build_reference.py`. `test/test_reference.py` fails until it does.
- **Scope:** one fix per PR, and link the issue (`Fixes #N`) when the PR fully fixes it. Keep diffs minimal and match the surrounding style.
- **Title:** conventional-commit style, e.g. `fix(drm): ...`. Squash merges reuse it as `title (#N)`.
- **Merge strategy:** squash by default. Tests run on a PR's head, not on each commit, and most PRs are one fix with follow-up commits, so only the squashed result is known to work. Use a rebase merge only when a PR's commits are deliberately separate steps and each one passes the test suite on its own (tidy the branch with `git commit --fixup` and `git rebase --autosquash` first). Avoid plain merge commits on `main`.
- **Branches and releases:** PRs target `main`, and there's no long-lived dev branch. A release is a **lightweight** tag on `main` (e.g. `3.15.0`). The version scripts sort tags by committer date, which an annotated tag doesn't have, so they skip it.
- **Description:** say what was tested and how (unit tests, live runs, Docker builds), and say what wasn't tested.
- **Before pushing:** check that the branch merges cleanly with the other open PRs, e.g. `git merge-tree --write-tree origin/<a> origin/<b>`.
- **Editing a PR description:** fetch it to a UTF-8 file, edit the file, check it isn't empty, then use `gh pr edit --body-file`. Piping it through a console with a non-UTF-8 encoding has wiped a description before.
