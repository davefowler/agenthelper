from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import json
import re
import subprocess


class GhError(RuntimeError):
    pass


def _run_gh(args: list[str]) -> str:
    proc = subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GhError(
            "gh command failed: "
            + " ".join(["gh", *args])
            + "\n\n"
            + (proc.stderr.strip() or proc.stdout.strip())
        )
    return proc.stdout


def gh_api_json(
    endpoint: str,
    *,
    fields: Optional[dict[str, str]] = None,
    paginate: bool = False,
    slurp: bool = False,
) -> Any:
    args: list[str] = ["api", endpoint]
    if paginate:
        args.append("--paginate")
    if slurp:
        args.append("--slurp")
    if fields:
        for key, value in fields.items():
            args.extend(["-F", f"{key}={value}"])
    out = _run_gh(args)
    out_stripped = out.strip()
    if not out_stripped:
        return None
    return json.loads(out_stripped)


def gh_api_post_comment(repo: str, number: int, body: str) -> None:
    # PRs are issues for comment purposes.
    _run_gh(
        [
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{number}/comments",
            "-f",
            f"body={body}",
        ]
    )


def gh_current_user_login() -> str:
    out = _run_gh(["api", "user"])
    doc = json.loads(out)
    login = doc.get("login")
    if not isinstance(login, str) or not login:
        raise GhError("Unable to determine current user login from `gh api user`")
    return login


@dataclass(frozen=True)
class PrRef:
    repo: str  # owner/name
    number: int


_PR_API_URL_RE = re.compile(r"^https://api\.github\.com/repos/([^/]+)/([^/]+)/pulls/(\d+)$")


def parse_pr_api_url(url: str) -> Optional[PrRef]:
    match = _PR_API_URL_RE.match(url.strip())
    if match is None:
        return None
    owner, name, number = match.group(1), match.group(2), match.group(3)
    return PrRef(repo=f"{owner}/{name}", number=int(number))


def list_prs_from_notifications(
    *,
    participating_only: bool,
    include_all: bool,
) -> list[PrRef]:
    fields: dict[str, str] = {}
    if participating_only:
        fields["participating"] = "true"
    if include_all:
        fields["all"] = "true"

    notifications = gh_api_json(
        "notifications",
        fields=fields,
        paginate=True,
        slurp=True,
    )
    if not isinstance(notifications, list):
        return []

    prs: list[PrRef] = []
    for notif in notifications:
        if not isinstance(notif, dict):
            continue
        subject = notif.get("subject")
        if not isinstance(subject, dict):
            continue
        if subject.get("type") != "PullRequest":
            continue
        url = subject.get("url")
        if not isinstance(url, str):
            continue
        pr = parse_pr_api_url(url)
        if pr is None:
            continue
        prs.append(pr)

    return prs


def list_open_prs_for_repo(repo: str) -> list[PrRef]:
    pulls = gh_api_json(
        f"repos/{repo}/pulls",
        fields={"state": "open", "per_page": "100"},
        paginate=True,
        slurp=True,
    )
    if not isinstance(pulls, list):
        return []

    prs: list[PrRef] = []
    for pull in pulls:
        if not isinstance(pull, dict):
            continue
        num = pull.get("number")
        if isinstance(num, int):
            prs.append(PrRef(repo=repo, number=num))
    return prs


@dataclass(frozen=True)
class Review:
    id: int
    submitted_at: str
    state: str
    user_login: str


def list_reviews(repo: str, number: int) -> list[Review]:
    reviews = gh_api_json(
        f"repos/{repo}/pulls/{number}/reviews",
        fields={"per_page": "100"},
        paginate=True,
        slurp=True,
    )
    if not isinstance(reviews, list):
        return []

    out: list[Review] = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        submitted_at = review.get("submitted_at")
        if not isinstance(submitted_at, str) or not submitted_at.strip():
            continue
        review_id = review.get("id")
        if not isinstance(review_id, int):
            continue
        state = review.get("state")
        if not isinstance(state, str) or not state.strip():
            continue
        user = review.get("user")
        if not isinstance(user, dict):
            continue
        login = user.get("login")
        if not isinstance(login, str) or not login.strip():
            continue

        out.append(
            Review(
                id=review_id,
                submitted_at=submitted_at,
                state=state.upper().strip(),
                user_login=login.strip(),
            )
        )
    return out
