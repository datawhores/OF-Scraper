"""Offline tools runnable as ``ofscraper <tool>`` without normal startup.

Each loader uses a plain ``import`` inside its function so PyInstaller bundles
the tool modules without a hidden-imports list while keeping startup lazy.
"""

import sys


def _stash_sync():
    import ofscraper.commands.stash_sync as mod

    return mod.main


def _recover_collisions():
    import ofscraper.commands.recover_collisions as mod

    return mod.main


def _move_creator_files():
    import ofscraper.commands.move_creator_files as mod

    return mod.main


def _postgres_import():
    import ofscraper.commands.postgres_import as mod

    return mod.main


def _postgres_export():
    import ofscraper.commands.postgres_export as mod

    return mod.main


def _creator_names():
    import ofscraper.commands.creator_names as mod

    return mod.main


def _verify():
    import ofscraper.commands.verify as mod

    return mod.main


def _rename_to_format():
    import ofscraper.commands.rename_to_format as mod

    return mod.main


def _doctor():
    import ofscraper.commands.doctor as mod

    return mod.main


TOOLS = {
    "stash_sync": (
        _stash_sync,
        "Sync downloaded media metadata into Stash",
    ),
    "recover_collisions": (
        _recover_collisions,
        "Find recorded paths shared by different media and reset flags",
    ),
    "move_creator_files": (
        _move_creator_files,
        "Move a creator's downloaded files to another recorded username",
    ),
    "postgres_import": (
        _postgres_import,
        "Import per-creator user_data.db files into PostgreSQL",
    ),
    "postgres_export": (
        _postgres_export,
        "Export creators from PostgreSQL back to user_data.db files",
    ),
    "creator_names": (
        _creator_names,
        "List and record usernames each creator account has had",
    ),
    "verify": (
        _verify,
        "Check downloaded files against the database, offline",
    ),
    "rename_to_format": (
        _rename_to_format,
        "Rename a creator's downloaded files to the current file_format and dir_format",
    ),
    "doctor": (
        _doctor,
        "Check the setup (config, auth files, ffmpeg, keys, folders), offline",
    ),
}


def run(name, argv):
    """Run offline tool ``name`` with ``argv`` and return its exit code (or None)."""
    loader, _summary = TOOLS[name]
    entry = loader()
    saved_argv = sys.argv
    sys.argv = [f"ofscraper {name}", *argv]
    try:
        return entry(list(argv))
    finally:
        sys.argv = saved_argv


def help_section():
    """Return the Offline tools section for ``ofscraper --help``."""
    width = max(len(name) for name in TOOLS) + 2
    lines = ["\b", "Offline tools (run as: ofscraper <tool> [OPTIONS]):"]
    for name, (_loader, summary) in TOOLS.items():
        lines.append(f"  {name:<{width}}{summary}")
    return "\n".join(lines)
