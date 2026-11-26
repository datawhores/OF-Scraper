import sys

import ofscraper.commands.tools as tools
import ofscraper.main.open.load as load


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if args and args[0] in tools.TOOLS:
        return tools.run(args[0], args[1:])
    load.main()


if __name__ == "__main__":
    sys.exit(main())
