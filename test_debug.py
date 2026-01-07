#!/usr/bin/env python3
"""
Debug script to test agenthelper and see what it detects
"""
from agenthelper import GitHubMonitor
import json

def main() -> None:
    monitor = GitHubMonitor()
    
    print("=" * 60)
    print("AGENTHELPER DEBUG TEST")
    print("=" * 60)
    print(f"Configured repos: {monitor.repos}")
    print(f"Check interval: {monitor.check_interval}s")
    print()
    
    if not monitor.repos:
        print("⚠️  No repositories configured in config.json")
        return
    
    for repo in monitor.repos:
        print(f"\n📦 Repository: {repo}")
        print("-" * 60)
        
        prs = monitor.get_prs(repo)
        print(f"Found {len(prs)} open PR(s) authored by you")
        
        if not prs:
            print("  No PRs found")
            continue
        
        for pr in prs:
            pr_num = pr.get('number')
            pr_title = pr.get('title', 'Unknown')
            print(f"\n  PR #{pr_num}: {pr_title}")
            print(f"  URL: {pr.get('url', 'N/A')}")
            
            # Check for recent comments
            check_key = f"{repo}#{pr_num}"
            has_recent = monitor.has_recent_cursor_comment(repo, pr_num, monitor.last_checks.get(check_key))
            print(f"  Recent comment check: {has_recent}")
            if check_key in monitor.last_checks:
                print(f"  Last commented: {monitor.last_checks[check_key]}")
            
            # Get checks
            checks = monitor.get_pr_checks(repo, pr_num)
            print(f"  Check runs: {len(checks)}")
            
            if checks:
                for check in checks:
                    name = check.get('name', 'Unknown')
                    status = check.get('status', 'unknown')
                    conclusion = check.get('conclusion', 'N/A')
                    print(f"    - {name}: status={status}, conclusion={conclusion}")
            else:
                print("    (No checks found)")
            
            has_failed = monitor.has_failed_checks(checks)
            print(f"  Has failed checks: {has_failed}")
            
            # Get PR details
            details = monitor.get_pr_details(repo, pr_num)
            if details:
                review_decision = details.get('reviewDecision', '')
                print(f"  Review decision: {review_decision or 'None'}")
                
                # Check merge conflicts
                mergeable = details.get('mergeable')
                mergeable_state = details.get('mergeableState') or 'unknown'
                mergeable_state_lower = mergeable_state.lower() if isinstance(mergeable_state, str) else 'unknown'
                print(f"  Mergeable: {mergeable}, State: {mergeable_state}")
                
                has_conflicts = (
                    mergeable is False or 
                    mergeable_state_lower == 'dirty' or
                    (mergeable is None and mergeable_state_lower == 'dirty')
                )
                print(f"  Has merge conflicts: {has_conflicts}")
            else:
                print(f"  Could not fetch PR details")
            
            # Summary
            should_comment = False
            reason = ""
            if has_failed:
                should_comment = True
                reason = "Failed checks detected"
            elif details:
                if details.get('reviewDecision', '').lower() == 'changes_requested':
                    should_comment = True
                    reason = "Review requests changes"
                mergeable_check = details.get('mergeable')
                mergeable_state_check = details.get('mergeableState') or ''
                mergeable_state_check_lower = mergeable_state_check.lower() if isinstance(mergeable_state_check, str) else ''
                if (
                    mergeable_check is False or 
                    mergeable_state_check_lower == 'dirty' or
                    (mergeable_check is None and mergeable_state_check_lower == 'dirty')
                ):
                    should_comment = True
                    reason = "Merge conflicts detected"
            
            if should_comment and not has_recent:
                print(f"  ✅ WOULD POST COMMENT: {reason}")
            elif should_comment:
                print(f"  ⏸️  WOULD POST COMMENT BUT: Commented recently")
            else:
                print(f"  ⏭️  NO ACTION NEEDED: No issues detected")

if __name__ == "__main__":
    main()

