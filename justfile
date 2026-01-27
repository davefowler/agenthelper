# agenthelper - GitHub PR comment monitor

plist_name := "com.agenthelper.plist"
launchd_path := env_var('HOME') / "Library/LaunchAgents" / plist_name

# List available commands
default:
    @just --list

# Install and start the launchd service
start:
    #!/usr/bin/env bash
    set -e
    
    # Check if gh CLI is installed
    if ! command -v gh &> /dev/null; then
        echo "Error: GitHub CLI (gh) is not installed."
        echo "Install it with: brew install gh"
        exit 1
    fi
    
    # Check if gh is authenticated
    if ! gh auth status &> /dev/null; then
        echo "Error: GitHub CLI is not authenticated."
        echo "Run: gh auth login"
        exit 1
    fi
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed."
        exit 1
    fi
    
    # Make script executable
    chmod +x "{{justfile_directory()}}/agenthelper.py"
    
    # Stop existing service if running
    if launchctl list | grep -q "com.agenthelper"; then
        echo "Stopping existing service..."
        launchctl unload "{{launchd_path}}" 2>/dev/null || true
    fi
    
    # Copy plist to LaunchAgents
    echo "Installing launchd service..."
    cp "{{justfile_directory()}}/{{plist_name}}" "{{launchd_path}}"
    
    # Load the service
    launchctl load "{{launchd_path}}"
    
    echo ""
    echo "✓ agenthelper started!"
    echo "  View logs: just logs"
    echo "  Check status: just status"
    echo "  Stop: just stop"

# Stop and unload the launchd service
stop:
    #!/usr/bin/env bash
    if launchctl list | grep -q "com.agenthelper"; then
        launchctl unload "{{launchd_path}}" 2>/dev/null || true
        rm -f "{{launchd_path}}"
        echo "✓ agenthelper stopped and unloaded"
    else
        echo "agenthelper is not running"
    fi

# Check if agenthelper is running
status:
    #!/usr/bin/env bash
    if launchctl list | grep -q "com.agenthelper"; then
        echo "✓ agenthelper is running"
        launchctl list | grep agenthelper
    else
        echo "✗ agenthelper is not running"
    fi

# View logs (stdout)
logs:
    tail -f "{{justfile_directory()}}/agenthelper.out.log"

# View error logs
errors:
    tail -f "{{justfile_directory()}}/agenthelper.err.log"

# Run directly in foreground (for debugging)
run:
    python3 "{{justfile_directory()}}/agenthelper.py"
