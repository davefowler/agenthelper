## gh-nudger

Small Python CLI that uses your authenticated `gh` session to **post a nudge comment as you** when a PR receives a **new code review**.

### What it does (MVP)
- **Discovers PRs** via:
  - GitHub **notifications** (`/notifications`) (recommended), and/or
  - An explicit **repo allowlist** in config
- For each open PR it finds, it checks for **new review submissions**
- When a new review is detected, it posts:

`@cursor there has been a code review. address the feedback and commit changes if warranted`

- It will do that **at most 4 times per PR** (configurable)

### What it does not do (yet)
- No LLM triage (documented future feature): in the future we can add an OpenAI/Anthropic policy to decide whether the review is actually actionable and craft a better nudge. For now it always nudges on any new review (with basic de-dupe + max cap).

### Prereqs
- Python 3.11+ (`python3`)
- GitHub CLI authenticated as *you*:

```bash
gh auth status
```

### Install

```bash
python3 -m pip install -e .
```

### Configure

Create `~/.config/gh-nudger/config.toml` if missing:

```bash
gh-nudger init
```

Edit the generated config to add/remove repos as needed.

### Run once (safe dry run)

```bash
gh-nudger run --dry-run --verbose
```

### Run periodically
Use your preferred scheduler. Example `cron` (every 5 minutes):

```cron
*/5 * * * * /usr/bin/python3 -m gh_nudger run >> ~/.local/state/gh-nudger/cron.log 2>&1
```

Or run as a simple loop:

```bash
gh-nudger run --daemon --interval-seconds 300
```

### Config knobs
See the generated `config.toml` for:
- `repos` allowlist
- `use_notifications`
- `max_review_nudges_per_pr` (defaults to 4)
- `review_nudge_cooldown_seconds` (defaults to 0)
