"""The agent reference in reference/ must match the code (issue #147).

If a test here fails after you add, rename or remove an option, setting,
placeholder or table: add or fix its entry in scripts/reference/notes.py,
then run ``python scripts/reference/build_reference.py`` and commit the
regenerated files in reference/.
"""

import ast
import difflib
import importlib.util
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location(
        "build_reference", ROOT / "scripts" / "reference" / "build_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def notes(build):
    return build.load_notes()


@pytest.fixture(scope="module")
def environment(build):
    with build.clean_environment():
        yield


def test_reference_files_match_the_code(build):
    rendered = build.render_all()
    stale = build.stale_files(rendered)
    diffs = []
    for name in stale:
        path = build.OUT / name
        current = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        diff = difflib.unified_diff(
            current, rendered[name].splitlines(), f"reference/{name}", "generated", lineterm="", n=1
        )
        diffs.append("\n".join(list(diff)[:40]))
    assert stale == [], (
        "reference/ is out of date: run python scripts/reference/build_reference.py\n"
        + "\n".join(diffs)
    )


def test_every_config_key_has_a_description(build, notes, environment):
    from ofscraper.utils.config.schema import get_current_config_schema

    keys = {k for k, _ in build.flatten(get_current_config_schema(False))}
    assert sorted(keys - set(notes.CONFIG)) == [], "config keys missing from notes.CONFIG"
    assert sorted(set(notes.CONFIG) - keys) == [], "notes.CONFIG names keys that don't exist"


def test_every_option_is_described(build, notes, environment):
    options = build.collect_options()
    dests = {e["param"].name for e in options}
    undocumented = sorted(
        e["param"].name
        for e in options
        if not build.clean_help(e["param"].help) and e["param"].name not in notes.CLI
    )
    assert undocumented == [], "options with no help text and no notes.CLI entry"
    assert sorted(set(notes.CLI) - dests) == [], "notes.CLI names options that don't exist"
    assert sorted(set(notes.NOT_MERGED) - dests) == [], "notes.NOT_MERGED names options that don't exist"


def test_the_generator_knows_every_subcommand(build):
    # parse_args registers the subcommands; the generator lists them by hand
    tree = ast.parse((ROOT / "ofscraper/utils/args/main.py").read_text(encoding="utf-8"))
    registered = {
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "add_command"
        and len(node.args) > 1
        and isinstance(node.args[1], ast.Constant)
    }
    assert registered, "no add_command calls found in ofscraper/utils/args/main.py"
    listed = set(build.COMMANDS) - {""}
    assert sorted(registered - listed) == [], "add these to COMMANDS and command_objects()"
    assert sorted(listed - registered) == [], "COMMANDS names commands that aren't registered"
    assert set(build.command_objects()) == set(build.COMMANDS)


def test_every_action_and_command_is_described(build, notes, environment):
    main_program = build.command_objects()[""]
    actions = next(p for p in main_program.params if p.name == "actions").type.choices
    assert sorted(actions) == sorted(notes.ACTIONS)
    commands = {name or "(main)" for name in build.command_objects()} | set(build.SEPARATE_COMMANDS)
    assert commands <= set(notes.COMMANDS)
    scripts = {k for k in notes.COMMANDS if k.startswith("scripts/")}
    assert sorted(set(notes.COMMANDS) - commands - scripts) == []
    for script in scripts:
        assert (ROOT / script).exists(), f"notes.COMMANDS names {script}, which doesn't exist"
    listed = {k.rstrip("/") for k in scripts}
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "scripts").iterdir()
        if p.name != "reference" and not p.name.startswith((".", "__"))
    }
    assert sorted(on_disk - listed) == [], "scripts/ entries missing from notes.COMMANDS"


def test_every_environment_default_is_described(build, notes, environment):
    from ofscraper.utils.of_env import get_all_configs

    keys = set(get_all_configs())
    sources = build.env_sources()
    assert sorted(keys - set(sources)) == [], "defaults whose source wasn't found"
    undocumented = sorted(
        key
        for key, (_path, _section, _envs, comment) in sources.items()
        if not build.env_description(key, comment, notes)
    )
    assert undocumented == [], "defaults with no source comment and no notes.ENV entry"
    assert sorted(set(notes.ENV) - keys) == [], "notes.ENV names defaults that don't exist"
    direct = set(build.direct_env())
    assert sorted(direct - set(notes.ENV_DIRECT)) == [], "os.getenv variables missing from notes.ENV_DIRECT"
    assert sorted(set(notes.ENV_DIRECT) - direct) == [], "notes.ENV_DIRECT names variables that aren't read"
    for pattern, _text in notes.ENV_PATTERNS:
        assert any(re.fullmatch(pattern, key) for key in keys), f"{pattern} matches nothing"


def unused_notes(build, notes):
    """unused key -> the text after "Defined but not read anywhere" (may be empty)"""
    result = {}
    for key, (_path, _section, _envs, comment) in build.env_sources().items():
        note = build.unused_note(build.env_description(key, comment, notes))
        if note is not None:
            result[key] = note
    return result


def test_an_unused_default_keeps_the_rest_of_its_description(build, notes, environment):
    with_text = {k: v for k, v in unused_notes(build, notes).items() if v}
    assert with_text, "expected at least one unused default with a note (MPD_SESSION_SLEEP_INIT)"
    rows = {}
    for line in (build.OUT / "env-unused.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r'\| <a id="([^"]+)"></a>', line)
        if m:
            rows[m.group(1)] = line
    lost = sorted(
        key for key, note in with_text.items() if build.cell(note) not in rows.get(build.anchor(key), "")
    )
    assert lost == [], "env-unused.md drops the note on these unused defaults"


def test_the_details_summary_does_not_stop_at_an_abbreviation(build):
    assert build.first_sentence("Use a list, e.g. `[1, 2]`. Then more.") == "Use a list, e.g. `[1, 2]`."
    assert build.first_sentence("One, i.e. two. Three.") == "One, i.e. two."
    assert build.first_sentence("No full stop") == "No full stop."


# keys read through a name built at run time, not written out in full
def dynamically_read_keys():
    text = (ROOT / "ofscraper/managers/sessionmanager/sleepers.py").read_text(encoding="utf-8")
    prefixes = re.findall(r'_create_sleeper\(\s*"([A-Z0-9_]+)"', text)
    suffixes = re.findall(r'getattr\(f"\{prefix\}(_[A-Z0-9_]+)"\)', text)
    assert prefixes and suffixes, "sleepers.py no longer builds keys the way this test expects"
    return {p + s for p in prefixes for s in suffixes}


def test_every_environment_default_is_read_or_marked_unused(build, notes, environment):
    # a key counts as read when its name appears as a whole word in ofscraper/
    # outside of_env/values (of_env.getattr("KEY"), max_individual="KEY",
    # _value(config, "KEY", ...)), or when sleepers.py builds it from a prefix
    skip = ROOT / "ofscraper/utils/of_env/values"
    code = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "ofscraper").rglob("*.py"))
        if skip not in p.parents
    )
    dynamic = dynamically_read_keys()
    unused = unused_notes(build, notes)
    unread = sorted(
        key
        for key in build.env_sources()
        if key not in unused
        and key not in dynamic
        and not re.search(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])", code)
    )
    assert unread == [], 'defaults nothing reads: say "Defined but not read anywhere." in their description'


def test_a_comment_over_several_lines_is_the_whole_description(build):
    lines = [
        "    # KEY: First line,",
        "    # second line.",
        "    #",
        "    # A note for whoever changes the code.",
        "    # OTHER: Not this one,",
        "    # but this one.",
        "    # Default: 1",
    ]
    assert build.comment_description("KEY", lines) == "First line, second line."
    assert build.comment_description("OTHER", lines) == "Not this one, but this one."


def test_an_environment_default_keeps_the_end_of_its_comment(build, environment):
    comment = build.env_sources()["OF_READ_TIMEOUT"][3]
    assert comment.startswith("Longest wait for the next piece of a response")
    assert comment.endswith("0 means no limit (the session manager turns it into None).")


def test_every_placeholder_is_described(build, notes, environment):
    names = set(build.placeholder_table())
    assert sorted(names - set(notes.PLACEHOLDERS)) == [], "placeholders missing from notes"
    assert sorted(set(notes.PLACEHOLDERS) - names) == [], "notes name placeholders that aren't set"


def test_every_table_and_column_is_described(build, notes, environment):
    tables = build.database_schema()
    assert sorted(tables) == sorted(notes.TABLES)
    for name, (columns, _indexes) in tables.items():
        described = set(notes.TABLES[name]["columns"])
        actual = {c["name"] for c in columns}
        assert sorted(actual - described) == [], f"{name} columns missing from notes"
        assert sorted(described - actual) == [], f"notes name {name} columns that don't exist"
