# Legacy tests

These tests were written against an older module layout (`ofscraper.classes.posts`,
`ofscraper.utils.args2`, `ofscraper.config.*`, `ofscraper.download.*`, ...) that no
longer exists, and they also need `pytest_check`. They fail at import, so pytest
skips this directory (`norecursedirs` in `pyproject.toml`).

They are kept as a reference for porting individual cases into `test/`.
