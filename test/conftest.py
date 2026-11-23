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
atexit.register(shutil.rmtree, _scratch_home, ignore_errors=True)

# The app's entry module imports ofscraper's packages in an order that avoids
# their circular imports; importing a leaf module first fails.
import ofscraper.main.open.load  # noqa: E402,F401
