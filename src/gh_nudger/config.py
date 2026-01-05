from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import os

try:
    import tomllib  # py311+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Config:
    repos: tuple[str, ...]
    use_notifications: bool
    participating_only: bool
    include_all_notifications: bool
    max_review_nudges_per_pr: int
    review_nudge_cooldown_seconds: int
    review_nudge_message: str
    ignore_self_reviews: bool
    ignore_review_states: tuple[str, ...]


DEFAULT_REVIEW_NUDGE_MESSAGE = (
    "@cursor there has been a code review. address the feedback and commit changes if warranted"
)


def _xdg_config_home() -> Path:
    value = os.environ.get("XDG_CONFIG_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".config"


def default_config_path() -> Path:
    return _xdg_config_home() / "gh-nudger" / "config.toml"


def load_config(path: Path) -> Config:
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib not available; requires Python 3.11+")

    raw = path.read_bytes()
    doc = tomllib.loads(raw.decode("utf-8"))

    general = doc.get("general", {})
    repos_value = general.get("repos", [])
    if not isinstance(repos_value, list):
        raise ValueError("[general].repos must be a list of strings")
    repos: list[str] = []
    for repo in repos_value:
        if not isinstance(repo, str):
            raise ValueError("[general].repos must be a list of strings")
        repo_stripped = repo.strip()
        if repo_stripped:
            repos.append(repo_stripped)

    ignore_review_states_value = general.get("ignore_review_states", ["DISMISSED", "PENDING"])
    if not isinstance(ignore_review_states_value, list):
        raise ValueError("[general].ignore_review_states must be a list of strings")
    ignore_review_states: list[str] = []
    for state in ignore_review_states_value:
        if not isinstance(state, str):
            raise ValueError("[general].ignore_review_states must be a list of strings")
        ignore_review_states.append(state.strip().upper())

    return Config(
        repos=tuple(repos),
        use_notifications=bool(general.get("use_notifications", True)),
        participating_only=bool(general.get("participating_only", True)),
        include_all_notifications=bool(general.get("include_all_notifications", True)),
        max_review_nudges_per_pr=int(general.get("max_review_nudges_per_pr", 4)),
        review_nudge_cooldown_seconds=int(general.get("review_nudge_cooldown_seconds", 0)),
        review_nudge_message=str(general.get("review_nudge_message", DEFAULT_REVIEW_NUDGE_MESSAGE)),
        ignore_self_reviews=bool(general.get("ignore_self_reviews", True)),
        ignore_review_states=tuple(ignore_review_states),
    )


def default_config_text() -> str:
    # Keep this simple so init can just write it out.
    repos_block = "\n".join(
        [
            '  "davefowler/annote",',
            '  "NooraHealth/ashai",',
            '  "davefowler/dataface",',
            '  "davefowler/asql",',
            '  "davefowler/AshAI",',
        ]
    )

    return (
        "[general]\n"
        "use_notifications = true\n"
        "participating_only = true\n"
        "include_all_notifications = true\n"
        "\n"
        "# Optional allowlist. If empty, discovery comes solely from notifications.\n"
        "repos = [\n"
        f"{repos_block}\n"
        "]\n"
        "\n"
        "# Stop after nudging this many times per PR.\n"
        "max_review_nudges_per_pr = 4\n"
        "\n"
        "# Optional per-PR cooldown for review nudges.\n"
        "review_nudge_cooldown_seconds = 0\n"
        "\n"
        'review_nudge_message = "'
        + DEFAULT_REVIEW_NUDGE_MESSAGE.replace('"', '\\"')
        + '"\n'
        "\n"
        "# Ignore reviews submitted by your own GitHub user.\n"
        "ignore_self_reviews = true\n"
        "\n"
        "# Ignore review states that are usually noise.\n"
        'ignore_review_states = ["DISMISSED", "PENDING"]\n'
    )


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_default_config(path: Path) -> None:
    ensure_parent_dir(path)
    if path.exists():
        return
    path.write_text(default_config_text(), encoding="utf-8")


def as_dict(config: Config) -> dict[str, Any]:
    return {
        "repos": list(config.repos),
        "use_notifications": config.use_notifications,
        "participating_only": config.participating_only,
        "include_all_notifications": config.include_all_notifications,
        "max_review_nudges_per_pr": config.max_review_nudges_per_pr,
        "review_nudge_cooldown_seconds": config.review_nudge_cooldown_seconds,
        "review_nudge_message": config.review_nudge_message,
        "ignore_self_reviews": config.ignore_self_reviews,
        "ignore_review_states": list(config.ignore_review_states),
    }
