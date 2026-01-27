# agenthelper - GitHub PR comment monitor
# Wrapper for the agenthelper CLI

cli := justfile_directory() / "cli.py"

# List available commands
default:
    @just --list

# Start the agenthelper service
start:
    python3 {{cli}} start

# Stop the agenthelper service
stop:
    python3 {{cli}} stop

# Show status of all tracked PRs
status:
    python3 {{cli}} status

# List tracked repositories
repos:
    python3 {{cli}} repos

# View logs (follow mode)
log:
    python3 {{cli}} log -f

# Merge a PR (e.g., just merge davefowler/asql#123)
merge pr:
    python3 {{cli}} merge {{pr}}

# Run directly in foreground (for debugging)
run:
    python3 "{{justfile_directory()}}/agenthelper.py"
