# Contributing to OF-Scraper

Thanks for helping.

## Which branch should I use?

- **Target `main`.** It has the latest code, and all fixes are merged there. There is no separate dev branch, and the old `dev/3.XX` branches are not used.
- **Releases are tags on `main`**, for example `3.15.0`.

## Quick start

1. **Branch** off the latest `main`.
2. **Set up** your environment (Python 3.11 is the minimum; 3.15 is the newest supported version):
   ```sh
   uv sync --python 3.15 --extra test
   ```
3. **Run the test suite** (warnings count as failures):
   ```sh
   python -m pytest test
   ```
4. **Open a PR** against `main`.

## What a PR needs

- **One fix per PR.** Link the issue it fixes (`Fixes #N`).
- **A test that fails without the fix.**
- **A description of what you tested**, including any live runs, and what you did not test.
- **No personal data.** Leave out `auth.json`, cookies, CDM files (`private_key.pem`, `client_id.bin`), keys, logs, creator usernames, and home-directory paths. This applies to code, commit messages, issues, and PR text. Editing text afterwards does not remove it, because GitHub keeps the edit history.

Fixes for the GUI patch go to [cjb900/OF-Scraper-GUI](https://github.com/cjb900/OF-Scraper-GUI).
