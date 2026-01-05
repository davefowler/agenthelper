from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .config import Config
from .github import (
    PrRef,
    gh_api_post_comment,
    GhError,
    try_gh_current_user_login,
    list_open_prs_for_repo,
    list_prs_from_notifications,
    list_reviews,
)
from .state import StateStore


def _parse_dt(value: str) -> datetime:
    # GitHub timestamps often look like 2026-01-05T12:34:56Z
    normalized = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _within_cooldown(last_nudge_at: Optional[str], cooldown_seconds: int) -> bool:
    if cooldown_seconds <= 0:
        return False
    if not last_nudge_at:
        return False
    try:
        dt = _parse_dt(last_nudge_at)
    except Exception:
        return False
    return (_utc_now() - dt).total_seconds() < cooldown_seconds


@dataclass(frozen=True)
class CycleResult:
    considered_prs: int
    new_reviews: int
    nudges_sent: int
    nudges_skipped_max: int
    nudges_skipped_cooldown: int


def run_once(config: Config, state: StateStore, *, dry_run: bool, verbose: bool) -> CycleResult:
    current_login = try_gh_current_user_login() if config.ignore_self_reviews else None
    if config.ignore_self_reviews and current_login is None and verbose:
        print("[warn] Unable to determine current user via `gh api user`; not ignoring self reviews")

    candidates: dict[tuple[str, int], PrRef] = {}

    if config.use_notifications:
        try:
            for pr in list_prs_from_notifications(
                participating_only=config.participating_only,
                include_all=config.include_all_notifications,
            ):
                candidates[(pr.repo, pr.number)] = pr
        except GhError as exc:
            if verbose:
                print(f"[warn] Unable to read notifications; falling back to repo allowlist only: {exc}")

    for repo in config.repos:
        try:
            for pr in list_open_prs_for_repo(repo):
                candidates[(pr.repo, pr.number)] = pr
        except GhError as exc:
            if verbose:
                print(f"[warn] Unable to list PRs for {repo}; skipping: {exc}")

    considered = 0
    new_reviews = 0
    nudges_sent = 0
    skipped_max = 0
    skipped_cooldown = 0

    for pr in sorted(candidates.values(), key=lambda x: (x.repo, x.number)):
        considered += 1

        try:
            reviews = list_reviews(pr.repo, pr.number)
        except GhError as exc:
            if verbose:
                print(f"[warn] Unable to read reviews for {pr.repo}#{pr.number}; skipping: {exc}")
            continue
        filtered = []
        for review in reviews:
            if review.state in set(config.ignore_review_states):
                continue
            if current_login and review.user_login == current_login:
                continue
            filtered.append(review)

        if not filtered:
            continue

        latest = max(filtered, key=lambda r: (r.submitted_at, r.id))
        existing = state.get_pr(pr.repo, pr.number)
        last_seen = existing.last_seen_review_id if existing else None
        if last_seen == latest.id:
            continue

        new_reviews += 1

        if existing and existing.review_nudge_count >= config.max_review_nudges_per_pr:
            skipped_max += 1
            # No further nudges will happen; mark as seen to avoid re-processing forever
            if not dry_run:
                state.upsert_pr_seen_review(pr.repo, pr.number, latest.id, latest.submitted_at)
            if verbose:
                print(
                    f"[skip:max] {pr.repo}#{pr.number} reached max_review_nudges_per_pr="
                    f"{config.max_review_nudges_per_pr}"
                )
            continue

        if existing and _within_cooldown(
            existing.last_nudge_at, config.review_nudge_cooldown_seconds
        ):
            skipped_cooldown += 1
            if verbose:
                print(
                    f"[skip:cooldown] {pr.repo}#{pr.number} cooldown "
                    f"{config.review_nudge_cooldown_seconds}s"
                )
            continue

        if existing and existing.last_nudged_review_id == latest.id:
            # Should be rare since we also track last_seen, but keep it safe.
            if not dry_run:
                state.upsert_pr_seen_review(pr.repo, pr.number, latest.id, latest.submitted_at)
            continue

        if verbose or dry_run:
            print(f"[nudge] {pr.repo}#{pr.number} new review {latest.id} ({latest.state})")

        if not dry_run:
            gh_api_post_comment(pr.repo, pr.number, config.review_nudge_message)
            state.upsert_pr_seen_review(pr.repo, pr.number, latest.id, latest.submitted_at)
            state.record_review_nudge(pr.repo, pr.number, latest.id)

        nudges_sent += 1

    return CycleResult(
        considered_prs=considered,
        new_reviews=new_reviews,
        nudges_sent=nudges_sent,
        nudges_skipped_max=skipped_max,
        nudges_skipped_cooldown=skipped_cooldown,
    )
