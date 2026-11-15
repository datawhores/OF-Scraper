"""The prompt help opens with Alt+V or Ctrl+V.

Windows Terminal keeps Ctrl+V for paste, so there it never reaches the
prompt; other terminals (Linux: Ctrl+Shift+V pastes, macOS: Cmd+V) pass it
on, and on macOS Terminal Alt+V needs "Use Option as Meta". Both keys stay
bound, and the help text says when Ctrl+V doesn't work.
"""

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.prompts.promptConvert as promptConvert
import ofscraper.prompts.prompt_strings as prompt_strings


class _Prompt:
    def __init__(self):
        self.keys = []

    def register_kb(self, key):
        def register(handler):
            self.keys.append(key)
            return handler

        return register


def test_help_is_bound_to_alt_v_and_ctrl_v():
    prompt = _Prompt()

    promptConvert.register_keys(prompt, None, None, {}, [None])

    assert "alt-v" in prompt.keys
    assert "c-v" in prompt.keys


def test_help_text_says_where_ctrl_v_pastes_instead():
    for name in ("KEY_BOARD", "NUMBER", "SCRAPE_PAID"):
        text = getattr(prompt_strings, name)
        assert "[ALT+V] or [CTRL+V]" in text
        assert "in Windows Terminal, Ctrl+V pastes instead" in text
