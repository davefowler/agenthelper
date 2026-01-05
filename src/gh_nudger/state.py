from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import os
import sqlite3
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _xdg_state_home() -> Path:
    value = os.environ.get("XDG_STATE_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".local" / "state"


def default_state_path() -> Path:
    return _xdg_state_home() / "gh-nudger" / "state.sqlite3"


@dataclass(frozen=True)
class PrState:
    repo: str
    number: int
    last_seen_review_id: Optional[int]
    last_seen_review_submitted_at: Optional[str]
    last_nudged_review_id: Optional[int]
    last_nudge_at: Optional[str]
    review_nudge_count: int


class StateStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pr_state (
                repo TEXT NOT NULL,
                number INTEGER NOT NULL,
                last_seen_review_id INTEGER NULL,
                last_seen_review_submitted_at TEXT NULL,
                last_nudged_review_id INTEGER NULL,
                last_nudge_at TEXT NULL,
                review_nudge_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (repo, number)
            )
            """
        )
        self._conn.commit()

    def get_pr(self, repo: str, number: int) -> Optional[PrState]:
        cur = self._conn.execute(
            "SELECT * FROM pr_state WHERE repo = ? AND number = ?",
            (repo, number),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return PrState(
            repo=row["repo"],
            number=int(row["number"]),
            last_seen_review_id=row["last_seen_review_id"],
            last_seen_review_submitted_at=row["last_seen_review_submitted_at"],
            last_nudged_review_id=row["last_nudged_review_id"],
            last_nudge_at=row["last_nudge_at"],
            review_nudge_count=int(row["review_nudge_count"]),
        )

    def upsert_pr_seen_review(
        self,
        repo: str,
        number: int,
        last_seen_review_id: Optional[int],
        last_seen_review_submitted_at: Optional[str],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO pr_state (
                repo, number, last_seen_review_id, last_seen_review_submitted_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(repo, number) DO UPDATE SET
                last_seen_review_id = excluded.last_seen_review_id,
                last_seen_review_submitted_at = excluded.last_seen_review_submitted_at,
                updated_at = excluded.updated_at
            """,
            (repo, number, last_seen_review_id, last_seen_review_submitted_at, _utc_now_iso()),
        )
        self._conn.commit()

    def record_review_nudge(self, repo: str, number: int, nudged_review_id: Optional[int]) -> None:
        existing = self.get_pr(repo, number)
        next_count = 1
        if existing is not None:
            next_count = existing.review_nudge_count + 1

        self._conn.execute(
            """
            INSERT INTO pr_state (
                repo, number, last_nudged_review_id, last_nudge_at, review_nudge_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo, number) DO UPDATE SET
                last_nudged_review_id = excluded.last_nudged_review_id,
                last_nudge_at = excluded.last_nudge_at,
                review_nudge_count = excluded.review_nudge_count,
                updated_at = excluded.updated_at
            """,
            (repo, number, nudged_review_id, _utc_now_iso(), next_count, _utc_now_iso()),
        )
        self._conn.commit()
