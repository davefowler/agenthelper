#!/usr/bin/env python3
"""
Find all comments posted by agenthelper
"""
import subprocess
import json
import sys
from typing import List, Dict

def get_pr_comments(repo: str, pr_number: int) -> List[Dict]:
    """Get all comments on a PR"""
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
        print(f"Error fetching comments: {e.stderr}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return []

def find_agenthelper_comments(repo: str, pr_number: int) -> List[Dict]:
    """Find comments posted by agenthelper"""
    comments = get_pr_comments(repo, pr_number)
    agenthelper_comments = [
        c for c in comments
        if '🤖 *agenthelper*' in c.get('body', '') or 'agenthelper' in c.get('body', '').lower()
    ]
    return agenthelper_comments

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 find_comments.py <repo> <pr_number>")
        print("Example: python3 find_comments.py davefowler/dataface 96")
        sys.exit(1)
    
    repo = sys.argv[1]
    try:
        pr_number = int(sys.argv[2])
    except ValueError:
        print(f"Error: PR number must be an integer: {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Searching for agenthelper comments in {repo}#{pr_number}...")
    print("-" * 60)
    
    comments = find_agenthelper_comments(repo, pr_number)
    
    if not comments:
        print("No agenthelper comments found.")
        return
    
    print(f"Found {len(comments)} agenthelper comment(s):\n")
    
    for i, comment in enumerate(comments, 1):
        author = comment.get('author', {}).get('login', 'Unknown')
        created = comment.get('createdAt', 'Unknown')
        body = comment.get('body', '')
        
        print(f"{i}. Posted by {author} on {created}")
        print(f"   {body[:100]}..." if len(body) > 100 else f"   {body}")
        print()

if __name__ == "__main__":
    main()

