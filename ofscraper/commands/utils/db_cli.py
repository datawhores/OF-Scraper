"""Shared helpers for offline database CLI commands (user_data.db or PostgreSQL)."""

import os
import sys
from contextlib import contextmanager
from pathlib import PureWindowsPath

import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites


def files_notice(cmd_name):
    """Warning text when a command is given a file while PostgreSQL is enabled (#631)."""
    return (
        f"PostgreSQL is on ({postgres.URL_KEY} is set), but {cmd_name} works"
        " on the user_data.db file it was given, not PostgreSQL. The file holds"
        " nothing scraped since PostgreSQL was turned on, and what is changed in it"
        " does not reach PostgreSQL. To work on PostgreSQL, give --postgres and"
        " --creator in place of the file. See POSTGRESQL.md."
    )


def from_another_system(path, *, os_name=None):
    """Whether a path that isn't a full path here is one elsewhere: C:\\...
    read on Linux, or /... read on Windows. --path-root is not for those."""
    name = os.name if os_name is None else os_name
    if name == "nt":
        return bool(path.root)
    return PureWindowsPath(str(path)).is_absolute()


def goes_by(rows):
    """A creator for a refusal: the site, the id and every username it has had."""
    names = []
    if "username" in rows.columns("profiles"):
        names = sorted({str(row[0]) for row in rows.select("profiles", ["username"])})
    return f"{rows.site} {rows.model_id}" + (f" ({', '.join(names)})" if names else "")


def validate_db_args(parser, args, notice, *, extra_postgres_only=None):
    """Validate --postgres / --creator / database arguments and return database_url."""
    extra = extra_postgres_only or {}
    # Only this command's own environment says where PostgreSQL is: the
    # scraper's settings and env files aren't read
    database_url = os.environ.get(postgres.URL_KEY, "").strip()
    if args.postgres:
        if args.database:
            parser.error("give a user_data.db or --postgres, not both")
        if not database_url:
            parser.error(
                f"--postgres needs {postgres.URL_KEY} set in the environment this is run in"
                " (an env file of the scraper's isn't read); see POSTGRESQL.md"
            )
        if not args.creator:
            parser.error(
                "--postgres needs --creator: the one creator to work on, by username or id"
            )
    elif (
        args.site is not None
        or args.creator is not None
        or any(v is not None for v in extra.values())
    ):
        names = ["--site", "--creator", *extra]
        pg_only_label = f"{', '.join(names[:-1])} and {names[-1]}"
        parser.error(
            f"{pg_only_label} go with --postgres; with a file, give that creator's user_data.db"
        )
    elif not args.database:
        parser.error("the following arguments are required: database, or --postgres")
    elif database_url:
        print(f"warning: {notice}", file=sys.stderr)
    return database_url


@contextmanager
def single_postgres_creator(database_url, creator, site=None, *, write=False):
    """Open one creator's PostgreSQL rows, refusing ambiguity or missing matches."""
    wanted_sites = [site] if site else list(sites.SITES)
    try:
        with creator_rows.in_postgres(
            database_url, wanted_sites, [creator], write=write
        ) as found:
            if len(found) != 1:
                # an id both sites have, an id that is another creator's
                # username, or a username two creators have had
                raise ValueError(
                    f"PostgreSQL has more than one creator named {creator}:"
                    f" {', '.join(goes_by(rows) for rows in found)}."
                    " Give --site, or a username or id that only one of them has"
                )
            yield found[0]
    except creator_rows.NotFound:
        # the name as it was typed (in_postgres has it in small letters)
        raise creator_rows.NotFound(
            f"PostgreSQL has no creator named {creator} (looked in: {', '.join(wanted_sites)})"
        ) from None
