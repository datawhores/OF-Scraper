import asyncio
import atexit
import os
import shutil
import sys
import tempfile

# ofscraper parses sys.argv when settings are first read, so hide pytest's
# own command-line flags from it.
sys.argv = sys.argv[:1]

# Give every test session (one per xdist worker) its own empty home folder,
# set before ofscraper is imported, so no test can read or write the real
# ~/.config/ofscraper and every run starts like a fresh install. The app finds
# its config folder with Path.home() (HOME, or USERPROFILE on Windows) plus
# OFSC_CONFIG_DIR, so a user's own OFSC_CONFIG_DIR is dropped too.
_scratch_home = tempfile.mkdtemp(
    prefix=f"ofs-test-home-{os.environ.get('PYTEST_XDIST_WORKER', 'main')}-"
)
os.environ["HOME"] = _scratch_home
os.environ["USERPROFILE"] = _scratch_home
os.environ.pop("OFSC_CONFIG_DIR", None)
# Never pip install a missing optional extra (psycopg, Playwright) during tests.
os.environ["OFSC_INSTALL_EXTRAS"] = "False"
atexit.register(shutil.rmtree, _scratch_home, ignore_errors=True)

# The app's entry module imports ofscraper's packages in an order that avoids
# their circular imports; importing a leaf module first fails.
import ofscraper.main.open.load  # noqa: E402,F401

import cloup  # noqa: E402
import pytest  # noqa: E402

import ofscraper.main.close.exit_status as exit_status  # noqa: E402
from ofscraper.utils.args.parse.commands.main import program  # noqa: E402


def _sections():
    """The program's cloup sections, found among its attributes rather than
    by cloup's private names (_default_section, _user_sections)."""
    found = []
    for value in vars(program).values():
        for item in value if isinstance(value, (list, set, tuple)) else [value]:
            if isinstance(item, cloup.Section) and item not in found:
                found.append(item)
    return found


@pytest.fixture(autouse=True)
def _restore_subcommands():
    # parse_args registers the subcommands on the shared program, and cloup
    # refuses to register one twice. A test that parses for real leaves them
    # registered, so a later test whose first settings read parses again fails
    # with 'command "manual" already exists' (#727). Put the program back:
    # its commands, the lists that hold its sections, and each section's.
    state = {k: v.copy() for k, v in vars(program).items() if isinstance(v, (dict, list, set))}
    sections = [(section, dict(section.commands)) for section in _sections()]
    yield
    for key, value in state.items():
        current = getattr(program, key)
        current.clear()
        if isinstance(current, list):
            current.extend(value)
        else:
            current.update(value)
    for section, commands in sections:
        section.commands.clear()
        section.commands.update(commands)


@pytest.fixture(autouse=True)
def _reset_exit_status():
    # exit_status holds process-wide state (e.g. PARTIAL from an incomplete scan
    # or failed creator); reset it around every test so one test can't leak its
    # status into the next test in the same worker (#853).
    exit_status.reset()
    try:
        yield
    finally:
        exit_status.reset()


@pytest.fixture(autouse=True)
def _isolate_event_loop():
    # On Python 3.11-3.13 without uvloop (Windows/macOS), calling
    # asyncio.get_event_loop() on a fresh worker before set_event_loop() emits
    # DeprecationWarning instead of raising RuntimeError (#853). Detaching the
    # loop before each test and closing any loop left behind after prevents
    # both that warning and ResourceWarning on 3.14+.
    asyncio.set_event_loop(None)
    try:
        yield
    finally:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        asyncio.set_event_loop(None)
        if loop is not None and not loop.is_closed():
            loop.close()
