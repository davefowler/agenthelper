#!/usr/bin/env python3
"""
GitHub PR/Issue Monitor - Automatically comments @cursor when issues are detected
"""
import json
import subprocess
import time
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agenthelper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GitHubMonitor:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.check_interval = self.config.get('check_interval', 300)  # Default 5 minutes
        self.repos = self.config.get('repos', [])
        self.last_check_file = Path('.last_check.json')
        self.last_checks = self.load_last_checks()
        # Track what we've commented on to avoid duplicates
        self.comment_history_file = Path('.comment_history.json')
        self.comment_history = self.load_comment_history()
        
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def load_last_checks(self) -> Dict:
        """Load last check timestamps"""
        if self.last_check_file.exists():
            with open(self.last_check_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_last_checks(self) -> None:
        """Save last check timestamps"""
        with open(self.last_check_file, 'w') as f:
            json.dump(self.last_checks, f, indent=2)
    
    def load_comment_history(self) -> Dict:
        """Load comment history to track what we've already commented on"""
        if self.comment_history_file.exists():
            with open(self.comment_history_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_comment_history(self) -> None:
        """Save comment history"""
        with open(self.comment_history_file, 'w') as f:
            json.dump(self.comment_history, f, indent=2)
    
    def has_commented_on_issue(self, repo: str, pr_number: int, issue_type: str) -> bool:
        """Check if we've already commented on a specific issue type for this PR"""
        check_key = f"{repo}#{pr_number}"
        history_key = f"{check_key}:{issue_type}"
        return history_key in self.comment_history
    
    def run_gh_command(self, command: List[str]) -> Optional[Dict]:
        """Run a GitHub CLI command and return JSON result"""
        try:
            # Check if --json is already in the command
            if '--json' not in command:
                command = command + ['--json']
            
            result = subprocess.run(
                ['gh'] + command,
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout.strip()
            if not output:
                return None
            return json.loads(output)
        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub CLI error: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
    
    def get_prs(self, repo: str) -> List[Dict]:
        """Get open PRs for a repository"""
        owner, repo_name = repo.split('/')
        prs = self.run_gh_command([
            'pr', 'list',
            '--repo', repo,
            '--state', 'open',
            '--author', '@me',
            '--json', 'number,title,url,state'
        ])
        return prs or []
    
    def get_pr_details(self, repo: str, pr_number: int) -> Optional[Dict]:
        """Get detailed information about a PR"""
        owner, repo_name = repo.split('/')
        # Use GitHub API directly to get mergeableState which isn't available via gh pr view
        try:
            result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo_name}/pulls/{pr_number}'],
                capture_output=True,
                text=True,
                check=True
            )
            api_data = json.loads(result.stdout)
            
            # Also get basic PR info via CLI for consistency
            prs = self.run_gh_command([
                'pr', 'view', str(pr_number),
                '--repo', repo,
                '--json', 'number,title,reviewDecision,state,url'
            ])
            
            # Merge API data with CLI data
            if prs:
                pr_data = prs if isinstance(prs, dict) else (prs[0] if isinstance(prs, list) and len(prs) > 0 else {})
                pr_data['mergeable'] = api_data.get('mergeable')
                pr_data['mergeableState'] = api_data.get('mergeable_state')
                return pr_data
            
            # Fallback to API data only
            return {
                'number': api_data.get('number'),
                'title': api_data.get('title'),
                'reviewDecision': api_data.get('review_decision', ''),
                'state': api_data.get('state'),
                'url': api_data.get('html_url'),
                'mergeable': api_data.get('mergeable'),
                'mergeableState': api_data.get('mergeable_state')
            }
        except subprocess.CalledProcessError as e:
            logger.debug(f"Failed to get PR details via API: {e.stderr}")
            # Fallback to CLI only
            prs = self.run_gh_command([
                'pr', 'view', str(pr_number),
                '--repo', repo,
                '--json', 'number,title,reviewDecision,state,url'
            ])
            if prs:
                if isinstance(prs, dict):
                    return prs
                elif isinstance(prs, list) and len(prs) > 0:
                    return prs[0]
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        
        return None
    
    def get_pr_checks(self, repo: str, pr_number: int) -> List[Dict]:
        """Get check runs for a PR using GitHub API"""
        owner, repo_name = repo.split('/')
        # First get the PR to get the head SHA
        try:
            pr_result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo_name}/pulls/{pr_number}'],
                capture_output=True,
                text=True,
                check=True
            )
            pr_data = json.loads(pr_result.stdout)
            head_sha = pr_data.get('head', {}).get('sha')
            
            if not head_sha:
                return []
            
            # Now get check runs for that commit
            result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo_name}/commits/{head_sha}/check-runs'],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            return data.get('check_runs', [])
        except subprocess.CalledProcessError as e:
            logger.debug(f"Failed to get PR checks: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return []
        except KeyError as e:
            logger.error(f"Missing key in API response: {e}")
            return []
    
    def get_pr_comments(self, repo: str, pr_number: int) -> List[Dict]:
        """Get comments on a PR"""
        owner, repo_name = repo.split('/')
        try:
            result = subprocess.run(
                ['gh', 'pr', 'view', str(pr_number),
                 '--repo', repo,
                 '--json', 'comments'],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            return data.get('comments', [])
        except subprocess.CalledProcessError as e:
            logger.debug(f"Failed to get PR comments: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return []
    
    def has_failed_checks(self, checks: List[Dict]) -> bool:
        """Check if any checks have failed"""
        if not checks:
            return False
        
        for check in checks:
            conclusion = check.get('conclusion') or ''
            conclusion_lower = conclusion.lower() if isinstance(conclusion, str) else ''
            status = check.get('status', '').lower()
            
            # Check if the check has completed and failed
            if status == 'completed' and conclusion_lower in ['failure', 'cancelled', 'timed_out', 'action_required']:
                return True
        
        return False
    
    def has_recent_cursor_comment(self, repo: str, pr_number: int, since: datetime) -> bool:
        """Check if there's a recent @cursor comment (from anyone)"""
        # First check if we've commented recently (quick check)
        check_key = f"{repo}#{pr_number}"
        last_comment_time = self.last_checks.get(check_key)
        if last_comment_time:
            last_time = datetime.fromisoformat(last_comment_time)
            if (datetime.now() - last_time) < timedelta(hours=1):
                return True
        
        # Check for any recent @cursor comments from anyone
        comments = self.get_pr_comments(repo, pr_number)
        now = datetime.now()
        
        for comment in comments:
            body = comment.get('body', '').lower()
            created_at_str = comment.get('createdAt', '')
            author = comment.get('author', {}).get('login', '').lower()
            
            # Skip code review comments that mention @cursor (they're reviews, not @cursor commands)
            # Code reviews often mention @cursor but aren't actual @cursor commands
            is_code_review_comment = (
                '## code review' in body or
                '## pull request review' in body or
                ('claude' in author and 'code review' in body[:500])
            )
            
            # Check if comment contains @cursor (but skip if it's a code review comment)
            if '@cursor' in body and not is_code_review_comment:
                try:
                    # Parse ISO format timestamp
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    # Handle timezone-aware datetime
                    if created_at.tzinfo:
                        created_at = created_at.replace(tzinfo=None) - created_at.utcoffset()
                    
                    # Check if comment is within the last hour
                    if (now - created_at) < timedelta(hours=1):
                        logger.info(f"  Found recent @cursor comment from {comment.get('author', {}).get('login', 'unknown')} at {created_at_str}")
                        return True
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse comment timestamp: {e}")
                    continue
        
        return False
    
    def has_review_comment(self, repo: str, pr_number: int) -> Optional[Dict]:
        """Check if there's a code review comment - returns the MOST RECENT one"""
        comments = self.get_pr_comments(repo, pr_number)
        now = datetime.now()
        
        most_recent_review = None
        most_recent_time = None
        
        for comment in comments:
            author = comment.get('author', {}).get('login', '').lower()
            body = comment.get('body', '').lower()
            created_at_str = comment.get('createdAt', '')
            
            # Check if it's from a reviewer (claude, code review bot, etc.)
            # Exclude bugbot and other non-review bots
            is_reviewer = (
                ('claude' in author and 'bugbot' not in author) or
                ('review' in author and 'bugbot' not in author) or
                ('bot' in author and 'bugbot' not in author and 'bug-bot' not in author) or
                '## code review' in body or
                '## pull request review' in body
            )
            
            if not is_reviewer:
                continue
            
            # Check if it contains code review structure
            is_code_review = (
                '## code review' in body or
                '## pull request review' in body or
                'code review' in body[:200]  # Check first 200 chars for review header
            )
            
            if not is_code_review:
                continue
            
            # Found a code review - track the most recent one
            try:
                # Parse timestamp to check if it's recent (within last 24 hours)
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                if created_at.tzinfo:
                    created_at = created_at.replace(tzinfo=None) - created_at.utcoffset()
                
                # Only consider reviews from the last 24 hours
                if (now - created_at) < timedelta(hours=24):
                    # Track the most recent review
                    if most_recent_time is None or created_at > most_recent_time:
                        most_recent_time = created_at
                        most_recent_review = {
                            'author': comment.get('author', {}).get('login', 'unknown'),
                            'createdAt': created_at_str,
                            'body': comment.get('body', '')[:500],  # First 500 chars
                            '_time': created_at
                        }
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse review comment timestamp: {e}")
                continue
        
        # Return the most recent review if found
        if most_recent_review:
            review = {k: v for k, v in most_recent_review.items() if k != '_time'}
            logger.info(f"  Found code review comment from {review.get('author', 'unknown')} at {review.get('createdAt')}")
            return review
        
        return None
    
    def post_comment(self, repo: str, pr_number: int, comment: str) -> bool:
        """Post a comment on a PR with agenthelper tag"""
        # Add tag to identify comments from this bot
        tagged_comment = f"{comment}\n\n---\n🤖 *agenthelper*"
        
        try:
            result = subprocess.run(
                ['gh', 'pr', 'comment', str(pr_number),
                 '--repo', repo,
                 '--body', tagged_comment],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Posted comment on {repo}#{pr_number}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to post comment: {e.stderr}")
            return False
    
    def check_pr(self, repo: str, pr: Dict) -> None:
        """Check a single PR for issues"""
        pr_number = pr.get('number')
        pr_url = pr.get('url', '')
        
        if not pr_number:
            return
        
        check_key = f"{repo}#{pr_number}"
        logger.info(f"Checking {check_key}: {pr.get('title', 'Unknown')}")
        
        # Get the most recent @cursor comment timestamp (if any) to check if we should skip
        comments = self.get_pr_comments(repo, pr_number)
        most_recent_cursor_time = None
        now = datetime.now()
        
        for comment in comments:
            body = comment.get('body', '').lower()
            if '@cursor' in body:
                try:
                    created_at_str = comment.get('createdAt', '')
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    if created_at.tzinfo:
                        created_at = created_at.replace(tzinfo=None) - created_at.utcoffset()
                    if (now - created_at) < timedelta(hours=1):
                        if most_recent_cursor_time is None or created_at > most_recent_cursor_time:
                            most_recent_cursor_time = created_at
                except (ValueError, TypeError):
                    continue
        
        has_recent_cursor = most_recent_cursor_time is not None
        if has_recent_cursor:
            logger.info(f"Found recent @cursor comment at {most_recent_cursor_time.isoformat()}")
        
        # Get PR checks/status
        checks = self.get_pr_checks(repo, pr_number)
        logger.info(f"  Found {len(checks)} check(s) for {check_key}")
        
        if checks:
            for check in checks:
                logger.info(f"    Check: {check.get('name')} - status: {check.get('status')}, conclusion: {check.get('conclusion', 'N/A')}")
        
        # Check for failed checks
        has_failed = self.has_failed_checks(checks)
        logger.info(f"  Has failed checks: {has_failed}")
        
        if has_failed:
            # Check if we've already commented on failed checks for this PR
            if self.has_commented_on_issue(repo, pr_number, 'failed_checks'):
                logger.info(f"  Skipping - already commented on failed checks for {check_key}")
            else:
                failed_checks = [
                    c for c in checks 
                    if c.get('status', '').lower() == 'completed' 
                    and c.get('conclusion', '').lower() in ['failure', 'cancelled', 'timed_out', 'action_required']
                ]
                check_names = [c.get('name', 'Unknown') for c in failed_checks]
                
                comment = f"@cursor there are test/linting/other issues - fix these.\n\nFailed checks: {', '.join(check_names)}"
                
                logger.info(f"  Posting comment for failed checks: {', '.join(check_names)}")
                if self.post_comment(repo, pr_number, comment):
                    self.last_checks[check_key] = datetime.now().isoformat()
                    self.save_last_checks()
                    # Track that we commented on this issue type
                    history_key = f"{check_key}:failed_checks"
                    self.comment_history[history_key] = datetime.now().isoformat()
                    self.save_comment_history()
                    logger.info(f"✓ Posted @cursor comment on {check_key} due to failed checks")
                else:
                    logger.error(f"✗ Failed to post comment on {check_key}")
        
        # Check for review comments (Claude reviews) and merge conflicts
        pr_details = self.get_pr_details(repo, pr_number)
        if pr_details:
            # Check for merge conflicts
            mergeable = pr_details.get('mergeable')
            mergeable_state = pr_details.get('mergeableState', '').lower()
            
            logger.info(f"  Mergeable: {mergeable}, State: {mergeable_state}")
            
            # Check if there are merge conflicts
            # mergeable can be: true, false, or null (null means GitHub hasn't computed it yet)
            # mergeableState can be: "clean", "dirty", "unstable", "blocked", "behind", "unknown"
            has_conflicts = (
                mergeable is False or 
                mergeable_state == 'dirty' or
                (mergeable is None and mergeable_state == 'dirty')
            )
            
            if has_conflicts:
                # Check if we've already commented on merge conflicts for this PR
                if self.has_commented_on_issue(repo, pr_number, 'merge_conflicts'):
                    logger.info(f"  Skipping - already commented on merge conflicts for {check_key}")
                else:
                    comment = "@cursor there are merge conflicts that need to be resolved."
                    logger.info(f"  Posting comment for merge conflicts")
                    if self.post_comment(repo, pr_number, comment):
                        self.last_checks[check_key] = datetime.now().isoformat()
                        self.save_last_checks()
                        # Track that we commented on this issue type
                        history_key = f"{check_key}:merge_conflicts"
                        self.comment_history[history_key] = datetime.now().isoformat()
                        self.save_comment_history()
                        logger.info(f"✓ Posted @cursor comment on {check_key} due to merge conflicts")
                    else:
                        logger.error(f"✗ Failed to post comment on {check_key}")
            
            # Check for review requests
            review_decision = pr_details.get('reviewDecision', '').lower()
            logger.info(f"  Review decision: {review_decision or 'None'}")
            if review_decision == 'changes_requested':
                # Check if we've already commented on review requests for this PR
                if self.has_commented_on_issue(repo, pr_number, 'review_requested'):
                    logger.info(f"  Skipping - already commented on review requests for {check_key}")
                else:
                    comment = "@cursor review and fix the issues claude brought up"
                    logger.info(f"  Posting comment for review requests")
                    if self.post_comment(repo, pr_number, comment):
                        self.last_checks[check_key] = datetime.now().isoformat()
                        self.save_last_checks()
                        # Track that we commented on this issue type
                        history_key = f"{check_key}:review_requested"
                        self.comment_history[history_key] = datetime.now().isoformat()
                        self.save_comment_history()
                        logger.info(f"✓ Posted @cursor comment on {check_key} due to review requests")
                    else:
                        logger.error(f"✗ Failed to post comment on {check_key}")
        else:
            logger.info(f"  Could not get PR details for {check_key}")
        
        # Check for code review comments (like Claude's reviews)
        # This check happens even if there's a recent @cursor comment, but only if the review is newer
        review_comment = self.has_review_comment(repo, pr_number)
        if review_comment:
            reviewer = review_comment.get('author', 'reviewer')
            review_time_str = review_comment.get('createdAt', '')
            
            # Check if review is newer than the most recent @cursor comment
            should_post_review = True
            if most_recent_cursor_time:
                try:
                    review_time = datetime.fromisoformat(review_time_str.replace('Z', '+00:00'))
                    if review_time.tzinfo:
                        review_time = review_time.replace(tzinfo=None) - review_time.utcoffset()
                    if review_time <= most_recent_cursor_time:
                        should_post_review = False
                        logger.info(f"  Skipping review comment - review ({review_time_str}) is older than @cursor comment")
                except (ValueError, TypeError):
                    pass
            
            if should_post_review:
                # Check if we've already commented on code review for this PR
                # But allow commenting again if this review is newer than our last comment
                history_key = f"{check_key}:code_review"
                last_comment_time_str = self.comment_history.get(history_key)
                
                should_comment = True
                if last_comment_time_str:
                    try:
                        last_comment_time = datetime.fromisoformat(last_comment_time_str)
                        review_time = datetime.fromisoformat(review_time_str.replace('Z', '+00:00'))
                        if review_time.tzinfo:
                            review_time = review_time.replace(tzinfo=None) - review_time.utcoffset()
                        
                        # Only skip if this review is older than or equal to our last comment
                        if review_time <= last_comment_time:
                            should_comment = False
                            logger.info(f"  Skipping - review ({review_time_str}) is older than our last comment ({last_comment_time_str})")
                        else:
                            logger.info(f"  Review ({review_time_str}) is newer than our last comment ({last_comment_time_str}) - will comment")
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Could not compare timestamps: {e}")
                
                if should_comment:
                    comment = f"@cursor please review the code review from {reviewer}. If you see critical or serious issues, fix them. If it's just positive feedback with no actionable items, ignore it and don't commit any changes."
                    logger.info(f"  Posting comment for code review from {reviewer}")
                    if self.post_comment(repo, pr_number, comment):
                        self.last_checks[check_key] = datetime.now().isoformat()
                        self.save_last_checks()
                        # Track that we commented on this issue type (update timestamp)
                        self.comment_history[history_key] = datetime.now().isoformat()
                        self.save_comment_history()
                        logger.info(f"✓ Posted @cursor comment on {check_key} due to code review")
                    else:
                        logger.error(f"✗ Failed to post comment on {check_key}")
        
        # Skip other checks if there's a recent @cursor comment (but we already checked reviews above)
        if has_recent_cursor:
            logger.info(f"Skipping other checks for {check_key} - found recent @cursor comment")
            logger.info(f"  Finished checking {check_key}")
            return
        
        logger.info(f"  Finished checking {check_key}")
    
    def check_repo(self, repo: str) -> None:
        """Check all PRs in a repository"""
        logger.info(f"Checking repository: {repo}")
        prs = self.get_prs(repo)
        
        if not prs:
            logger.debug(f"No open PRs found in {repo}")
            return
        
        logger.info(f"Found {len(prs)} open PR(s) in {repo}")
        
        for pr in prs:
            self.check_pr(repo, pr)
    
    def run_once(self) -> None:
        """Run one check cycle"""
        logger.info("Starting check cycle...")
        
        if not self.repos:
            logger.warning("No repositories configured. Please add repos to config.json")
            return
        
        for repo in self.repos:
            try:
                self.check_repo(repo)
            except Exception as e:
                logger.error(f"Error checking repo {repo}: {e}", exc_info=True)
        
        logger.info("Check cycle complete")
    
    def run_forever(self) -> None:
        """Run continuously"""
        logger.info(f"Starting GitHub monitor (check interval: {self.check_interval}s)")
        
        try:
            while True:
                self.run_once()
                logger.info(f"Sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise

def main() -> None:
    """Main entry point"""
    monitor = GitHubMonitor()
    monitor.run_forever()

if __name__ == "__main__":
    main()

