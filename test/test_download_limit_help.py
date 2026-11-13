"""The download-limit prompt must say the limit is shared by all downloads.

It said "for each thread", but one limit is shared by every download in the
download session (#174, item 2; measured on #172).
"""

import inspect
import re

import ofscraper.prompts.prompt_groups.config as config_prompts


def test_download_limit_help_says_shared():
    source = inspect.getsource(config_prompts)
    lines = [line for line in source.splitlines() if "download speed" in line]
    assert len(lines) == 2, lines  # the config overview and the prompt
    for line in lines:
        assert not re.search(r"each\s+thread", line), line
        assert "shared by all downloads" in line, line
