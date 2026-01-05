# GitHub Agent Helper

A Python tool that monitors GitHub PRs and issues, automatically commenting `@cursor` when test/linting failures or review requests are detected.

## Features

- Monitors your GitHub PRs for failed checks (tests, linting, etc.)
- Detects when reviews request changes
- Automatically posts `@cursor` comments to kick off agent work
- **Tags all comments with `🤖 *agenthelper*`** so you can identify them
- Runs continuously as a background service on macOS
- Prevents duplicate comments (won't comment more than once per hour per PR)

## Setup

1. **Install GitHub CLI** (if not already installed):
   ```bash
   brew install gh
   gh auth login
   ```

2. **Configure repositories**:
   Edit `config.json` and add the repositories you want to monitor:
   ```json
   {
     "check_interval": 300,
     "repos": [
       "davefowler/agenthelper",
       "owner/repo-name"
     ]
   }
   ```
   - `check_interval`: How often to check (in seconds). Default: 300 (5 minutes)
   - `repos`: List of repositories in `owner/repo` format

3. **Install as a service**:
   ```bash
   ./setup.sh
   ```

## Usage

### Check Status
```bash
launchctl list | grep agenthelper
```

### View Logs
```bash
# Standard output
tail -f agenthelper.out.log

# Errors
tail -f agenthelper.err.log

# Application log (includes both)
tail -f agenthelper.log
```

### Stop the Service
```bash
launchctl unload ~/Library/LaunchAgents/com.agenthelper.plist
```

### Start the Service
```bash
launchctl load ~/Library/LaunchAgents/com.agenthelper.plist
```

### Run Manually (for testing)
```bash
python3 agenthelper.py
```

### Find Agenthelper Comments
```bash
# Find all agenthelper comments on a specific PR
python3 find_comments.py <repo> <pr_number>

# Example:
python3 find_comments.py davefowler/dataface 96
```

## How It Works

1. Every `check_interval` seconds, the tool:
   - Fetches all open PRs authored by you in configured repositories
   - Checks each PR for:
     - Failed check runs (tests, linting, etc.)
     - Review requests that require changes
   - Posts `@cursor` comments when issues are detected
   - Tracks when comments were posted to avoid duplicates

2. The service runs continuously in the background and will automatically restart if it crashes.

## Configuration

Edit `config.json` to customize:
- **check_interval**: How often to check for updates (in seconds)
- **repos**: List of repositories to monitor (format: `owner/repo`)

## Troubleshooting

### Service not starting
- Check logs: `tail -f agenthelper.err.log`
- Verify GitHub CLI is installed: `which gh`
- Verify GitHub CLI is authenticated: `gh auth status`

### No comments being posted
- Check that repositories are configured in `config.json`
- Verify you have PRs open in those repositories
- Check the logs to see what's being detected
- Ensure the PRs have failed checks or review requests

### Service keeps crashing
- Check error logs: `tail -f agenthelper.err.log`
- Verify Python path in `com.agenthelper.plist` matches your system
- Check that GitHub CLI is in PATH (should be `/opt/homebrew/bin/gh`)

## Comment Tagging

All comments posted by agenthelper are tagged with `🤖 *agenthelper*` at the bottom, making them easy to identify. You can:

1. **Visually identify** them in GitHub PR comments
2. **Search for them** using GitHub's comment search (search for "agenthelper")
3. **Find them programmatically** using the `find_comments.py` script

Example comment format:
```
@cursor there are test/linting/other issues - fix these.

Failed checks: test (3.9), test (3.12)

---
🤖 *agenthelper*
```

## Files

- `agenthelper.py` - Main Python script
- `config.json` - Configuration file
- `com.agenthelper.plist` - macOS launchd service configuration
- `setup.sh` - Installation script
- `test_debug.py` - Debug script to test what the tool detects
- `find_comments.py` - Script to find agenthelper comments on a PR
- `agenthelper.log` - Application log file
- `agenthelper.out.log` - Standard output from service
- `agenthelper.err.log` - Standard error from service
- `.last_check.json` - Tracks when comments were last posted (prevents duplicates)
