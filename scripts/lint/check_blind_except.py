"""Fail on new blind excepts in ofscraper/data/api and ofscraper/db.

Swallowed errors there hide failed API calls and database writes. The code
already has some, so ruff's BLE001 (blind except) and S110 (try/except/pass)
are checked against a baseline of how many each file has, kept in
blind_except_baseline.json next to this script:

- a file with more hits than its baseline fails, listing every hit in it;
- a file with fewer fails too, so the baseline only goes down: rerun with
  --update and commit the new baseline.

A hit that's intentional can carry ``# noqa: BLE001`` (or S110) with a comment
saying why; ruff doesn't report it, so it doesn't count.

Usage (from the repo root, with the test extra installed):
    python scripts/lint/check_blind_except.py [--update]
"""

import argparse
import collections
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE = pathlib.Path(__file__).with_name("blind_except_baseline.json")
RULES = ["BLE001", "S110"]
PATHS = ["ofscraper/data/api", "ofscraper/db"]


def run_ruff():
    """Return ruff's BLE001/S110 findings for PATHS, as dicts."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            ",".join(RULES),
            "--output-format",
            "json",
            "--exit-zero",
            *PATHS,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def relative(filename):
    return pathlib.Path(filename).resolve().relative_to(ROOT).as_posix()


def count(findings):
    """Map "path:rule" to the number of findings, sorted."""
    counts = collections.Counter(
        f"{relative(f['filename'])}:{f['code']}" for f in findings
    )
    return dict(sorted(counts.items()))


def compare(baseline, current):
    """Return (more, fewer): keys whose count rose or fell against baseline."""
    keys = baseline.keys() | current.keys()
    more = sorted(k for k in keys if current.get(k, 0) > baseline.get(k, 0))
    fewer = sorted(k for k in keys if current.get(k, 0) < baseline.get(k, 0))
    return more, fewer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update", action="store_true", help="rewrite the baseline from the tree"
    )
    args = parser.parse_args(argv)

    findings = run_ruff()
    current = count(findings)
    if args.update:
        BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {sum(current.values())} findings to {BASELINE.name}")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    more, fewer = compare(baseline, current)
    for key in more:
        path, rule = key.rsplit(":", 1)
        print(
            f"{path}: {current[key]} {rule} findings, baseline allows "
            f"{baseline.get(key, 0)}. Handle the specific exceptions, or log "
            "and re-raise, instead of swallowing everything:"
        )
        for f in findings:
            if relative(f["filename"]) == path and f["code"] == rule:
                row = f["location"]["row"]
                print(f"  {path}:{row}: {rule} {f['message']}")
    for key in fewer:
        print(
            f"{key}: {current.get(key, 0)} findings, below the baseline of "
            f"{baseline[key]}. Run `python scripts/lint/check_blind_except.py "
            "--update` and commit the lower baseline."
        )
    if more or fewer:
        return 1
    print(f"{sum(current.values())} baselined findings, no new ones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
