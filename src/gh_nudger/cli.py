from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .config import default_config_path, load_config, write_default_config
from .nudger import run_once
from .state import StateStore, default_state_path


def _path_from_env_or_default(env_key: str, default: Path) -> Path:
    value = os.environ.get(env_key)
    if value:
        return Path(value).expanduser()
    return default


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gh-nudger")
    sub = p.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Create a default config file if missing")
    init_p.add_argument(
        "--config",
        type=Path,
        default=_path_from_env_or_default("GH_NUDGER_CONFIG", default_config_path()),
        help="Config path to create (default: ~/.config/gh-nudger/config.toml)",
    )

    run_p = sub.add_parser("run", help="Run one cycle or poll continuously")
    run_p.add_argument(
        "--config",
        type=Path,
        default=_path_from_env_or_default("GH_NUDGER_CONFIG", default_config_path()),
        help="Config path (default: ~/.config/gh-nudger/config.toml)",
    )
    run_p.add_argument(
        "--state",
        type=Path,
        default=_path_from_env_or_default("GH_NUDGER_STATE", default_state_path()),
        help="State DB path (default: ~/.local/state/gh-nudger/state.sqlite3)",
    )
    run_p.add_argument("--dry-run", action="store_true", help="Print actions without commenting")
    run_p.add_argument("--verbose", action="store_true", help="Verbose logging")

    mode = run_p.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run a single polling cycle (default)")
    mode.add_argument("--daemon", action="store_true", help="Poll continuously")

    run_p.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Polling interval when --daemon is used (default: 300)",
    )

    return p


def _cmd_init(args: argparse.Namespace) -> int:
    config_path: Path = args.config
    write_default_config(config_path)
    print(f"Wrote config (if missing): {config_path}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config_path: Path = args.config
    state_path: Path = args.state

    if not config_path.exists():
        print(f"Config not found at {config_path}. Run `gh-nudger init` first.", file=sys.stderr)
        return 2

    config = load_config(config_path)

    def run_cycle() -> int:
        store = StateStore(state_path)
        try:
            result = run_once(config, store, dry_run=bool(args.dry_run), verbose=bool(args.verbose))
        finally:
            store.close()

        print(
            "Cycle: "
            f"considered_prs={result.considered_prs} "
            f"new_reviews={result.new_reviews} "
            f"nudges_sent={result.nudges_sent} "
            f"skipped_max={result.nudges_skipped_max} "
            f"skipped_cooldown={result.nudges_skipped_cooldown}"
        )
        return 0

    if args.daemon:
        while True:
            exit_code = run_cycle()
            if exit_code != 0:
                return exit_code
            time.sleep(max(1, int(args.interval_seconds)))

    # default: once
    return run_cycle()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.cmd == "init":
        raise SystemExit(_cmd_init(args))
    if args.cmd == "run":
        raise SystemExit(_cmd_run(args))

    raise SystemExit(2)

