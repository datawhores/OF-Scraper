"""Offline Linux container probe: real daemon loop, controlled scraping jobs."""

import logging
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import ofscraper.main.open.load
import ofscraper.commands.scraper.scraper as scraper
import ofscraper.commands.scraper.utils.schedule as scheduler

logging.basicConfig(level=logging.INFO)
scraper.checkers.check_auth = lambda: None
scraper.actions.select_areas = lambda: None
scraper.manager.Manager = SimpleNamespace(
    current_model_manager=SimpleNamespace(sync_models=lambda: None)
)
scraper.settings.get_settings = lambda: SimpleNamespace(daemon=60, output_level="NORMAL")
scheduler.logger.resetLogger = lambda: None
scheduler.logs.printStartValues = lambda: None
scheduler.before_arg.update_before = lambda: None

state = {}
base = scheduler.DaemonWakeup


class ObservedWakeup(base):
    def install(self):
        super().install()
        state["wakeup"] = self


scraper.DaemonWakeup = ObservedWakeup


class Runner:
    count = 0

    def runner(self):
        self.count += 1
        print(f"START {self.count}", flush=True)
        release = Path(os.environ.get("OFS_SIGNAL_PROBE_DIR", "/tmp")) / f"release-{self.count}"
        while not release.exists():
            time.sleep(0.02)
        print(f"END {self.count}", flush=True)


runner = Runner()
scraper.scraperManager = lambda: runner


def observe():
    last = None
    while True:
        wakeup = state.get("wakeup")
        current = (wakeup.state, runner.count) if wakeup else None
        if current != last and current and current[0] == "idle":
            print(f"IDLE {runner.count}", flush=True)
        last = current
        time.sleep(0.02)


threading.Thread(target=observe, daemon=True).start()
try:
    scraper.daemon_process()
except KeyboardInterrupt:
    print("STOPPED", flush=True)
finally:
    wakeup = state.get("wakeup")
    if wakeup is not None:
        print(f"HANDLER_RESTORED {not wakeup.installed}", flush=True)
