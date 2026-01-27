#!/usr/bin/env python3
"""
agenthelper CLI - Manage and monitor the GitHub PR helper
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ANSI colors
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def color(text: str, c: str) -> str:
    """Apply color to text"""
    return f"{c}{text}{Colors.RESET}"

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"
PLIST_NAME = "com.agenthelper.plist"
PLIST_PATH = SCRIPT_DIR / PLIST_NAME
LAUNCHD_PATH = Path.home() / "Library/LaunchAgents" / PLIST_NAME
LOG_PATH = SCRIPT_DIR / "agenthelper.log"


def load_config() -> Dict:
    """Load configuration from JSON file"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {}


def get_repos() -> List[str]:
    """Get list of tracked repositories"""
    config = load_config()
    return config.get('repos', [])


def is_macos() -> bool:
    """Check if running on macOS"""
    return platform.system() == 'Darwin'


def is_running() -> bool:
    """Check if agenthelper service is running (macOS only)"""
    if not is_macos():
        return False
    try:
        result = subprocess.run(
            ['launchctl', 'list'],
            capture_output=True, text=True
        )
        return 'com.agenthelper' in result.stdout
    except Exception:
        return False


def cmd_start(args: argparse.Namespace) -> int:
    """Start the agenthelper service (macOS only - uses launchd)"""
    # Check platform
    if not is_macos():
        print(color("Error: The start/stop commands only work on macOS (uses launchd).", Colors.RED))
        print("On other platforms, run the agent directly: python3 agenthelper.py")
        return 1
    
    # Check prerequisites
    if subprocess.run(['which', 'gh'], capture_output=True).returncode != 0:
        print(color("Error: GitHub CLI (gh) is not installed.", Colors.RED))
        print("Install it with: brew install gh")
        return 1
    
    if subprocess.run(['gh', 'auth', 'status'], capture_output=True).returncode != 0:
        print(color("Error: GitHub CLI is not authenticated.", Colors.RED))
        print("Run: gh auth login")
        return 1
    
    # Make script executable
    os.chmod(SCRIPT_DIR / "agenthelper.py", 0o755)
    
    # Stop existing service if running
    if is_running():
        print("Stopping existing service...")
        subprocess.run(['launchctl', 'unload', str(LAUNCHD_PATH)], 
                      capture_output=True)
    
    # Copy plist to LaunchAgents
    print("Installing launchd service...")
    shutil.copy(PLIST_PATH, LAUNCHD_PATH)
    
    # Load the service
    subprocess.run(['launchctl', 'load', str(LAUNCHD_PATH)])
    
    print()
    print(color("✓ agenthelper started!", Colors.GREEN))
    print()
    
    # Show tracked repos
    repos = get_repos()
    if repos:
        print(color("Tracking repositories:", Colors.BOLD))
        for repo in repos:
            print(f"  • {repo}")
    else:
        print(color("Warning: No repositories configured in config.json", Colors.YELLOW))
    
    print()
    print(f"  View logs:    {color('agenthelper log', Colors.CYAN)}")
    print(f"  Check status: {color('agenthelper status', Colors.CYAN)}")
    print(f"  Stop:         {color('agenthelper stop', Colors.CYAN)}")
    
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the agenthelper service (macOS only - uses launchd)"""
    # Check platform
    if not is_macos():
        print(color("Error: The start/stop commands only work on macOS (uses launchd).", Colors.RED))
        print("On other platforms, stop the agent process manually (e.g., pkill -f agenthelper.py)")
        return 1
    
    if is_running():
        subprocess.run(['launchctl', 'unload', str(LAUNCHD_PATH)], capture_output=True)
        if LAUNCHD_PATH.exists():
            LAUNCHD_PATH.unlink()
        print(color("✓ agenthelper stopped", Colors.GREEN))
    else:
        print("agenthelper is not running")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    """Show agenthelper logs"""
    if not LOG_PATH.exists():
        print("No log file found")
        return 1
    
    if args.follow:
        os.execvp('tail', ['tail', '-f', str(LOG_PATH)])
    else:
        lines = args.lines or 50
        os.execvp('tail', ['tail', f'-{lines}', str(LOG_PATH)])
    # Note: os.execvp replaces the process, so this line is only reached on error
    return 1


def cmd_repos(args: argparse.Namespace) -> int:
    """List tracked repositories"""
    repos = get_repos()
    config = load_config()
    interval = config.get('check_interval', 300)
    
    print(color("Tracked repositories:", Colors.BOLD))
    print()
    
    if repos:
        for repo in repos:
            print(f"  • {color(repo, Colors.CYAN)}")
    else:
        print(color("  No repositories configured", Colors.YELLOW))
    
    print()
    print(f"Check interval: {interval}s ({interval // 60} min)")
    print(f"Config file: {CONFIG_PATH}")
    
    return 0


def get_pr_status_emoji(checks: List[Dict], mergeable: Optional[bool], mergeable_state: str) -> str:
    """Get status emoji for a PR"""
    # Check for merge conflicts
    if mergeable is False or mergeable_state == 'dirty':
        return color("⚠️  conflicts", Colors.YELLOW)
    
    # Check for failed checks
    for check in checks:
        conclusion = (check.get('conclusion') or '').lower()
        status = check.get('status', '').lower()
        if status == 'completed' and conclusion in ['failure', 'cancelled', 'timed_out']:
            return color("✗ failing", Colors.RED)
    
    # Check for in-progress checks
    for check in checks:
        status = check.get('status', '').lower()
        if status in ['queued', 'in_progress', 'pending']:
            return color("⏳ running", Colors.YELLOW)
    
    # All checks passed
    if checks:
        return color("✓ passing", Colors.GREEN)
    
    return color("- no checks", Colors.DIM)


def get_pr_checks(repo: str, pr_number: int) -> List[Dict]:
    """Get check runs for a PR"""
    owner, repo_name = repo.split('/')
    try:
        # Get the head SHA
        pr_result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo_name}/pulls/{pr_number}'],
            capture_output=True, text=True, check=True
        )
        pr_data = json.loads(pr_result.stdout)
        head_sha = pr_data.get('head', {}).get('sha')
        
        if not head_sha:
            return []
        
        # Get check runs
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo_name}/commits/{head_sha}/check-runs'],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        return data.get('check_runs', [])
    except Exception:
        return []


def get_pr_details(repo: str, pr_number: int) -> Optional[Dict]:
    """Get PR details including mergeable state"""
    owner, repo_name = repo.split('/')
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo_name}/pulls/{pr_number}'],
            capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except Exception:
        return None


def has_critical_review(repo: str, pr_number: int) -> Optional[str]:
    """Check if PR has critical feedback from a reviewer"""
    try:
        result = subprocess.run(
            ['gh', 'pr', 'view', str(pr_number), '--repo', repo, '--json', 'comments,reviewDecision'],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        
        # Check review decision
        if data.get('reviewDecision') == 'CHANGES_REQUESTED':
            return "changes requested"
        
        # Check for critical/serious issues in comments
        comments = data.get('comments', [])
        for comment in comments:
            body = comment.get('body', '').lower()
            author = comment.get('author', {}).get('login', '').lower()
            
            # Look for reviewer comments with critical issues
            if 'claude' in author or 'review' in author:
                if 'critical' in body or 'serious' in body or 'security' in body:
                    return "critical feedback"
        
        return None
    except Exception:
        return None


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of all tracked PRs"""
    repos = get_repos()
    
    if not repos:
        print(color("No repositories configured", Colors.YELLOW))
        return 1
    
    # Check if service is running
    running = is_running()
    status_text = color("● running", Colors.GREEN) if running else color("○ stopped", Colors.RED)
    print(f"agenthelper: {status_text}")
    print()
    
    for repo in repos:
        print(color(f"📁 {repo}", Colors.BOLD))
        
        # Get open PRs
        try:
            result = subprocess.run(
                ['gh', 'pr', 'list', '--repo', repo, '--state', 'open', 
                 '--author', '@me', '--json', 'number,title,url'],
                capture_output=True, text=True, check=True
            )
            prs = json.loads(result.stdout)
        except Exception:
            print(color("  Error fetching PRs", Colors.RED))
            print()
            continue
        
        if not prs:
            print(color("  No open PRs", Colors.DIM))
            print()
            continue
        
        for pr in prs:
            pr_number = pr.get('number')
            title = pr.get('title', 'Unknown')[:50]
            if len(pr.get('title', '')) > 50:
                title += "..."
            
            # Get checks and details
            checks = get_pr_checks(repo, pr_number)
            details = get_pr_details(repo, pr_number)
            
            mergeable = details.get('mergeable') if details else None
            mergeable_state = (details.get('mergeable_state') or '').lower() if details else ''
            
            status = get_pr_status_emoji(checks, mergeable, mergeable_state)
            
            # Check for critical feedback
            critical = has_critical_review(repo, pr_number)
            critical_badge = ""
            if critical:
                critical_badge = f" {color(f'[{critical}]', Colors.MAGENTA)}"
            
            print(f"  #{pr_number} {title}")
            print(f"      {status}{critical_badge}")
        
        print()
    
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge a PR"""
    pr_ref = args.pr
    
    # Parse PR reference (can be #123 or repo#123 or just 123)
    if '#' in pr_ref:
        parts = pr_ref.split('#')
        if len(parts) == 2 and parts[0]:
            repo = parts[0]
            pr_number = parts[1]
        else:
            pr_number = parts[-1]
            repo = None
    else:
        pr_number = pr_ref
        repo = None
    
    # If no repo specified, try to find which repo has this PR
    if not repo:
        repos = get_repos()
        if len(repos) == 1:
            repo = repos[0]
        else:
            print(color("Error: Multiple repos configured. Specify repo with: repo#number", Colors.RED))
            print("Example: agenthelper merge davefowler/asql#123")
            return 1
    
    # Confirm merge
    if not args.yes:
        print(f"Merge {color(f'{repo}#{pr_number}', Colors.CYAN)}?")
        response = input("Continue? [y/N] ")
        if response.lower() != 'y':
            print("Aborted")
            return 0
    
    # Perform merge
    merge_args = ['gh', 'pr', 'merge', pr_number, '--repo', repo]
    
    if args.squash:
        merge_args.append('--squash')
    elif args.rebase:
        merge_args.append('--rebase')
    else:
        merge_args.append('--merge')
    
    if args.delete_branch:
        merge_args.append('--delete-branch')
    
    print(f"Merging {repo}#{pr_number}...")
    result = subprocess.run(merge_args, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(color(f"✓ Merged {repo}#{pr_number}", Colors.GREEN))
        return 0
    else:
        print(color(f"✗ Failed to merge: {result.stderr}", Colors.RED))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='agenthelper',
        description='Manage and monitor the GitHub PR helper'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # start
    start_parser = subparsers.add_parser('start', help='Start the agenthelper service')
    start_parser.set_defaults(func=cmd_start)
    
    # stop
    stop_parser = subparsers.add_parser('stop', help='Stop the agenthelper service')
    stop_parser.set_defaults(func=cmd_stop)
    
    # log
    log_parser = subparsers.add_parser('log', help='Show agenthelper logs')
    log_parser.add_argument('-f', '--follow', action='store_true', help='Follow log output')
    log_parser.add_argument('-n', '--lines', type=int, help='Number of lines to show')
    log_parser.set_defaults(func=cmd_log)
    
    # repos
    repos_parser = subparsers.add_parser('repos', help='List tracked repositories')
    repos_parser.set_defaults(func=cmd_repos)
    
    # status
    status_parser = subparsers.add_parser('status', help='Show status of all tracked PRs')
    status_parser.set_defaults(func=cmd_status)
    
    # merge
    merge_parser = subparsers.add_parser('merge', help='Merge a PR')
    merge_parser.add_argument('pr', help='PR to merge (e.g., 123 or repo#123)')
    merge_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    merge_parser.add_argument('-s', '--squash', action='store_true', help='Squash merge')
    merge_parser.add_argument('-r', '--rebase', action='store_true', help='Rebase merge')
    merge_parser.add_argument('-d', '--delete-branch', action='store_true', help='Delete branch after merge')
    merge_parser.set_defaults(func=cmd_merge)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
