import sys

# ofscraper parses sys.argv when settings are first read, so hide pytest's
# own command-line flags from it.
sys.argv = sys.argv[:1]

# The app's entry module imports ofscraper's packages in an order that avoids
# their circular imports; importing a leaf module first fails.
import ofscraper.main.open.load  # noqa: E402,F401
