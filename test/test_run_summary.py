"""The run's totals (StatsManager.totals) and the end-of-run summary built on them."""

import json
import logging
import queue
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.utils.scrape_context as scrape_context
import ofscraper.main.close.exit_status as exit_status
import ofscraper.main.close.final.run_record as run_record
import ofscraper.scripts.final_script as final_script
import ofscraper.utils.logs.utils.level as log_level
import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.managers.stats import StatsManager
from ofscraper.managers.utils.state import EActivity
from ofscraper.utils.logs.classes.classes import DiscordFormatter
from ofscraper.utils.logs.classes.handlers.discord import DiscordHandler

DOWNLOAD = EActivity.ScrapeActivity.DOWNLOAD
PAID = EActivity.PaidActivity.SCRAPE_PAID_DOWNLOAD
METADATA = EActivity.ScrapeActivity.METADATA
TEXT = EActivity.ScrapeActivity.TEXT


def media(kind="Videos", size=0, attempted=True, succeeded=True, stopped=False):
    return SimpleNamespace(
        mediatype=kind, size=size, download_attempted=attempted,
        download_succeeded=succeeded, download_stopped=stopped,
        metadata_attempted=attempted, metadata_succeeded=succeeded,
    )


def post(status="saved"):
    return SimpleNamespace(text_status=status)


def filled():
    stats = StatsManager()
    stats.update_stats("alice", DOWNLOAD, [
        media("Videos", 1000), media("Images", 10), media("Audios", 5),
        media(attempted=False), media(succeeded=False), media(stopped=True),
    ])
    stats.update_stats("alice", PAID, [media("Videos", 2000)])
    stats.update_stats("bob", DOWNLOAD, [media("Images", 7), media(succeeded=False)])
    stats.update_stats("bob", METADATA, [
        media("Videos"), media("Images"), media(succeeded=None), media(succeeded=False),
    ])
    # a post with no caption (None) isn't counted
    stats.update_stats("bob", TEXT, [post(), post("exists"), post("failed"), post(None)])
    # a creator with nothing done
    stats.update_stats("carol", DOWNLOAD, [])
    return stats


def test_totals_add_up_every_counter_across_creators():
    totals = filled().totals(per_creator=True)
    assert totals["downloads"] == {
        "videos": 2, "audios": 1, "photos": 2, "skipped": 1, "failed": 2, "stopped": 1, "bytes": 3022,
    }
    assert totals["metadata"] == {"videos": 1, "audios": 0, "photos": 1, "unchanged": 1, "failed": 1}
    assert totals["text"] == {"saved": 1, "skipped": 1, "failed": 1}
    assert totals["creators_active"] == 2
    assert totals["per_creator"] == [
        {"username": "alice", "new_files": 4, "bytes": 3015, "failed": 1},
        {"username": "bob", "new_files": 1, "bytes": 7, "failed": 1},
        {"username": "carol", "new_files": 0, "bytes": 0, "failed": 0},
    ]


def test_totals_of_an_empty_run():
    totals = StatsManager().totals(per_creator=True)
    assert totals["creators_active"] == 0 and totals["per_creator"] == []
    assert not any(totals["downloads"].values())
    assert "per_creator" not in StatsManager().totals()


def test_printed_summary_uses_the_totals(caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        filled().print_global_summary()
    text = caplog.text
    assert " ➜ TOTAL ITEMS: 5" in text
    assert " ➜ FAILED:      2 overall" in text
    assert " ➜ TOTAL CHANGED: 2" in text
    assert " ➜ SAVED:         1" in text
    assert " ➜ ALREADY SAVED: 1" in text


# --- the run record ---------------------------------------------------------


class FakeModels:
    def __init__(self, processed=(), unprocessed=()):
        self.processed, self.unprocessed = set(processed), list(unprocessed)

    def get_processed(self, activity):
        return self.processed if activity == DOWNLOAD else set()

    def get_unprocessed(self, activity):
        return self.unprocessed if activity == DOWNLOAD else []


@pytest.fixture
def run(monkeypatch):
    """A run of a filled StatsManager: alice and bob done, carol not."""
    state = SimpleNamespace(
        stats=filled(), models=FakeModels({"alice", "bob"}, ["carol"]),
        settings=SimpleNamespace(site="onlyfans", command="scraper", discord_level="OFF",
                                 post_script=None, profile="main_profile"),
    )
    monkeypatch.setattr(
        run_record, "manager",
        SimpleNamespace(Manager=SimpleNamespace(
            stats_manager=state.stats, current_model_manager=state.models)),
    )
    monkeypatch.setattr(run_record.settings, "get_settings", lambda: state.settings)
    import ofscraper.utils.profiles.data as profile_data

    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")
    run_record.start()
    return state


def test_record_of_a_run(run):
    record = run_record.finish()
    assert record["site"] == "onlyfans" and record["profile"] == "main_profile"
    assert record["command"] == "scraper" and record["outcome"] == "ok"
    assert record["started"] and record["finished"] >= record["started"]
    assert record["totals"] == {k: v for k, v in run.stats.totals().items()}
    assert record["creators"] == {"done": 2, "failed": 1}
    assert [c["username"] for c in record["per_creator"]] == ["alice", "bob", "carol"]
    # built once a run: a later call returns the same record
    assert run_record.finish("failed") is record and run_record.current() is record
    json.dumps(record)  # post_script gets it as JSON


def test_record_of_a_pass_that_raises(run):
    with pytest.raises(RuntimeError):
        with scrape_context.scrape_context_manager():
            raise RuntimeError("database is gone")
    record = run_record.current()
    assert record["outcome"] == "failed" and record["error"] == "database is gone"


def test_record_of_a_stopped_pass(run):
    with pytest.raises(KeyboardInterrupt):
        with scrape_context.scrape_context_manager():
            raise KeyboardInterrupt
    assert run_record.current()["outcome"] == "stopped"


@pytest.mark.parametrize(
    "code,reason",
    [(exit_status.UNAVAILABLE, "site unavailable"), (exit_status.AUTH, "login failed")],
)
def test_pass_ended_by_maintenance_or_auth_fail_says_why(run, code, reason):
    # the maintenance abort and --auth-fail end the pass with SystemExit; that
    # isn't a Ctrl+C, so the summary isn't "stopped, 130 interrupted"
    exit_status.reset()
    with pytest.raises(SystemExit):
        with scrape_context.scrape_context_manager():
            raise SystemExit(code)
    record = run_record.current()
    assert record["outcome"] == "failed"
    assert record["status"] == code and record["status_label"] == reason
    assert f"The run failed: {reason} (exit status {int(code)})." in run_record.message(record)
    exit_status.reset()


def test_each_pass_gets_its_own_record(run):
    with scrape_context.scrape_context_manager():
        first = run_record.finish()
    with scrape_context.scrape_context_manager():
        second = run_record.finish()
    assert first is not second


def test_post_script_gets_the_old_keys_and_the_summary(run, monkeypatch, tmp_path):
    script = tmp_path / "post.py"
    script.write_text("", encoding="utf-8")
    run.settings.post_script = str(script)
    model_manager = SimpleNamespace(
        get_processed=lambda activity: {"alice"} if activity == "download" else set(),
        get_unprocessed=lambda activity: ["carol"] if activity == "download" else [],
    )
    monkeypatch.setattr(
        final_script, "manager", SimpleNamespace(Manager=SimpleNamespace(current_model_manager=model_manager))
    )
    monkeypatch.setattr(final_script.settings, "get_settings", lambda: run.settings)
    sent = []
    monkeypatch.setattr(final_script, "run", lambda cmd, input=None, **k: sent.append(json.loads(input)))
    record = run_record.finish()
    final_script.final_script(record)
    payload = sent[0]
    assert payload["download_processed_users"] == ["alice"]
    assert payload["download_unprocessed_users"] == ["carol"]
    assert set(payload) == {
        "like_processed_users", "like_unprocessed_users", "unlike_processed_users",
        "unlike_unprocessed_users", "download_processed_users", "download_unprocessed_users",
        "scrape_paid_processed_users", "scrape_paid_unprocessed_users", "summary",
    }
    assert payload["summary"] == json.loads(json.dumps(record))


# --- --discord SUMMARY ------------------------------------------------------


@pytest.fixture
def discord(monkeypatch):
    """A Discord handler on the shared log that queues instead of sending."""
    # account ids an earlier test logged in with are masked in every line;
    # one of "1" would turn the counts below into "userid"
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    handler = DiscordHandler.__new__(DiscordHandler)
    logging.Handler.__init__(handler)
    # it has no sending thread to stop: logging's shutdown at exit calls this
    handler.close = lambda: logging.Handler.close(handler)
    handler.queue = queue.Queue()
    handler.setFormatter(DiscordFormatter("%(message)s"))
    handler.setLevel(log_level.getLevel("SUMMARY"))
    shared = logging.getLogger("shared")
    shared.addHandler(handler)
    yield handler
    shared.removeHandler(handler)


def queued(handler):
    out = []
    while not handler.queue.empty():
        out.append(handler.queue.get())
    return out


def test_summary_level_sends_one_message_and_no_log_lines(run, discord):
    run.settings.discord_level = "SUMMARY"
    log = logging.getLogger("shared")
    log.warning("a warning")
    log.error("an error")
    run_record.finish()
    run_record.finish()
    messages = queued(discord)
    assert len(messages) == 1
    assert messages[0].startswith(
        "OnlyFans, main_profile: 3 creators, 5 new files (3.02 KB), 2 failed. 1 creator not finished. Took "
    )
    assert "- alice: 4 new (3.02 KB), 1 failed" in messages[0]
    assert "- bob: 1 new (7 bytes), 1 failed" in messages[0]
    assert "carol" not in messages[0].split("\n", 1)[1]


@pytest.mark.parametrize("level", ["OFF", "LOW", "NORMAL"])
def test_other_levels_send_no_summary(run, discord, level):
    run.settings.discord_level = level
    run_record.finish()
    assert queued(discord) == []


def test_long_creator_list_is_cut_to_fit_one_message(run):
    record = run_record.build()
    record["per_creator"] = [
        {"username": f"creator{i:03}", "new_files": 1, "bytes": 1, "failed": 0} for i in range(300)
    ]
    text = run_record.message(record)
    assert len(text) <= run_record.MESSAGE_LIMIT
    lines = text.split("\n")
    shown = [line for line in lines if line.startswith("- creator")]
    assert lines[-1] == f"... and {300 - len(shown)} more" and shown


def test_failed_run_says_so(run):
    record = run_record.build("failed", "database is gone")
    assert "The run failed: database is gone (exit status 1)." in run_record.message(record)


def test_every_line_shown_when_all_fit_without_the_more_line(run):
    record = run_record.build()
    record["per_creator"] = [{"username": "a creator", "new_files": 1, "bytes": 1, "failed": 0}]
    whole = run_record.message(record, limit=10_000)
    # room for every line, but not for a "... and 1 more" line as well
    text = run_record.message(record, limit=len(whole) + 3)
    assert text == whole and "more" not in text


def test_error_in_the_record_is_redacted_and_bounded(run):
    error = "request failed: sess=abc123secret https://cdn.example/f?Policy=xyz " + "x" * 5000
    record = run_record.build("failed", error)
    assert "abc123secret" not in record["error"] and "xyz" not in record["error"]
    assert len(record["error"]) <= run_record.ERROR_LIMIT
    assert record["error"].startswith("request failed: sess={sess}")
