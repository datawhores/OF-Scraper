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
