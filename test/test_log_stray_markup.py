"""A log line with broken Rich markup is still logged, not dropped."""

import io
import logging

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.logs.classes.classes as log_class

STRAY = "done [/bold] here"


def _record(msg):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)


@pytest.mark.parametrize(
    "formatter", [log_class.LogFileFormatter, log_class.DiscordFormatter]
)
def test_formatters_keep_line_with_stray_closing_tag(formatter):
    out = formatter("%(message)s").format(_record(STRAY))
    assert "done" in out and "here" in out


def test_fallback_removes_escapes_like_rich_does():
    fmt = r" \[%(module)s:%(lineno)d]  %(message)s"
    out = log_class.LogFileFormatter(fmt).format(_record(STRAY))
    assert "\\[" not in out
    assert out.startswith(" [")


def test_formatters_still_strip_valid_markup():
    out = log_class.LogFileFormatter("%(message)s").format(
        _record("[bold]ok[/bold] fine")
    )
    assert out == "ok fine"


def _rich_output(msg):
    buf = io.StringIO()
    handler = log_class.SafeRichHandler(
        markup=True,
        show_time=False,
        show_level=False,
        show_path=False,
        console=Console(file=buf, width=200, color_system=None),
    )
    handler.setFormatter(log_class.SensitiveFormatter("%(message)s"))
    logger = logging.getLogger(f"stray-markup-test-{id(buf)}")
    logger.propagate = False
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    raised = []
    handler.handleError = lambda record: raised.append(record)
    logger.info(msg)
    return buf.getvalue(), raised


def test_terminal_handler_keeps_line_with_stray_closing_tag():
    out, raised = _rich_output(STRAY)
    assert not raised
    assert STRAY in out


def test_terminal_fallback_removes_escapes():
    out, raised = _rich_output(r"\[loc] " + STRAY)
    assert not raised
    assert "[loc] " + STRAY in out
    assert "\\[" not in out


def test_terminal_handler_still_renders_valid_markup():
    out, raised = _rich_output("[bold]ok[/bold] fine")
    assert not raised
    assert "ok fine" in out
