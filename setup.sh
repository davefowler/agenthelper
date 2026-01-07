#!/bin/bash
# Setup script for agenthelper - installs as a launchd service on macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.agenthelper.plist"
PLIST_PATH="$SCRIPT_DIR/$PLIST_NAME"
LAUNCHD_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Setting up agenthelper..."

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

# Make scripts executable
chmod +x "$SCRIPT_DIR/agenthelper.py"
chmod +x "$SCRIPT_DIR/run.sh"

# Stop and unload existing service if it exists
if launchctl list | grep -q "com.agenthelper"; then
    echo "Stopping existing service..."
    launchctl unload "$LAUNCHD_PATH" 2>/dev/null || true
fi

# Copy plist to LaunchAgents
echo "Installing launchd service..."
cp "$PLIST_PATH" "$LAUNCHD_PATH"

# Load the service
launchctl load "$LAUNCHD_PATH"

echo ""
echo "✓ agenthelper installed successfully!"
echo ""
echo "To check status: launchctl list | grep agenthelper"
echo "To view logs: tail -f $SCRIPT_DIR/agenthelper.out.log"
echo "To stop: launchctl unload $LAUNCHD_PATH"
echo "To start: launchctl load $LAUNCHD_PATH"
echo ""
echo "Don't forget to add repositories to config.json!"

