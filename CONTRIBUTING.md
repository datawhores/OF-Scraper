# Contributing to OF-Scraper-Community

Thanks for helping. This is a community-maintained fork of [datawhores/OF-Scraper](https://github.com/datawhores/OF-Scraper), which is no longer updated.

### 🌿 Which branch should I use?

* **Target `main`.** It has the latest code, and all fixes are merged there. There's no separate dev branch, and upstream's `dev/3.XX` branches aren't used here.
* **Releases are tags on `main`**, e.g. `3.15.0`.

### 🚀 Quick start
1. **Branch** off the latest `main`.
2. **Set up** with `uv sync --python 3.15 --extra test`. Python 3.11 is the minimum, and 3.15 is the newest supported version.
3. **Test** with `python -m pytest test`. Warnings count as failures.
4. **Open a PR** against `main`.

### ✅ What a PR needs
* **One fix per PR.** Link the issue it fixes (`Fixes #N`).
* **A test that fails without the fix.**
* **A description of what you tested**, including any live runs, and what you didn't test.
* **No personal data.** Leave out `auth.json`, cookies, CDM files (`private_key.pem`, `client_id.bin`), keys, logs, creator usernames and home-directory paths. That applies to code, commit messages, issues and PR text. Editing text afterwards doesn't remove it, because GitHub keeps the edit history.

Fixes for the GUI patch go to [cjb900/OF-Scraper-GUI](https://github.com/cjb900/OF-Scraper-GUI).
