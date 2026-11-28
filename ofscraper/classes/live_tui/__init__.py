def run_live_tui(*args, **kwargs):
    from ofscraper.classes.live_tui.app import run_live_tui as _run

    return _run(*args, **kwargs)


__all__ = ["run_live_tui"]
