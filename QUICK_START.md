# Quick Start Guide

## ✅ It's Working!

The service is now running and monitoring your PRs. Here's how to check if it's working:

### Check Status
```bash
# See if service is running
launchctl list | grep agenthelper

# View live logs
tail -f agenthelper.out.log
```

### Test What It Detects
```bash
# Run the debug script to see what it finds
python3 test_debug.py
```

### What It Does

The service automatically:
1. ✅ Checks your PRs every 5 minutes
2. ✅ Detects failed checks (tests, linting, etc.)
3. ✅ Detects review requests requiring changes
4. ✅ Posts `@cursor` comments automatically
5. ✅ Prevents duplicate comments (won't comment more than once per hour per PR)

### Current Configuration

- **Repositories monitored**: `davefowler/agenthelper`, `davefowler/dataface`
- **Check interval**: 5 minutes (300 seconds)
- **Service**: Running as `com.agenthelper` launchd service

### Add More Repositories

Edit `config.json`:
```json
{
  "check_interval": 300,
  "repos": [
    "davefowler/agenthelper",
    "davefowler/dataface",
    "owner/repo-name"
  ]
}
```

Then restart:
```bash
launchctl unload ~/Library/LaunchAgents/com.agenthelper.plist
launchctl load ~/Library/LaunchAgents/com.agenthelper.plist
```

### Troubleshooting

**Not seeing comments?**
1. Check logs: `tail -f agenthelper.out.log`
2. Run debug: `python3 test_debug.py`
3. Verify PRs have failed checks or review requests
4. Check if you commented recently (won't comment again within 1 hour)

**Service not running?**
```bash
# Check status
launchctl list | grep agenthelper

# Restart
launchctl unload ~/Library/LaunchAgents/com.agenthelper.plist
launchctl load ~/Library/LaunchAgents/com.agenthelper.plist

# Check errors
tail -f agenthelper.err.log
```

