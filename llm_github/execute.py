import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from requests_cache import CachedSession
from requests_cache.backends.sqlite import SQLiteCache

# Fixing import conflicts by adjusting namespace and avoiding re-importing CachedSession
from llm_github.core import (
    DEFAULT_DROPPED_FIELDS,
    EnvironmentVariableError,
    fetch_all_comments,
    fetch_all_discussions,
    fetch_issues,
    fetch_pull_requests,
    get_repos,
    github_token_check,
    list_user_orgs,
    process_comments,
    process_discussions,
    process_issues,
    process_pull_requests,
    write_json_to_file,
)

# Load environment variables from .env file
load_dotenv(dotenv_path="local/.env", verbose=True)

# Global access token for GitHub API
global_token: str = os.getenv("GITHUB_TOKEN", "")
if not global_token:
    raise EnvironmentVariableError("GITHUB_TOKEN")
print("Token loaded successfully.")

# Set up cache with SQLite backend
session: CachedSession = CachedSession(
    cache_name="llm-github-cache",
    backend=SQLiteCache("llm-github.sqlite", timeout=86400),  # Cache expires after 24 hours
)

user_data: Optional[Dict] = github_token_check(global_token, session=session)
orgs: Optional[List[Dict]] = list_user_orgs(global_token, session=session)

org_name: str = "microbiomedata"

print("FETCHING REPOS")
repos: Optional[List[Dict]] = get_repos(org_name, global_token, session=session)
if repos:
    write_json_to_file(repos, f"{org_name}_repos.json")

print("FETCHING ISSUES")
org_issues: Optional[List[Dict]] = fetch_issues(org_name, global_token, session=session)
if org_issues:
    sanitized_issues: List[Dict] = process_issues(org_issues, DEFAULT_DROPPED_FIELDS)
    write_json_to_file(sanitized_issues, f"{org_name}_issues.json")

print("FETCHING PRs")
pull_requests: Optional[List[Dict]] = fetch_pull_requests(org_name, global_token, session=session)
if pull_requests:
    processed_pull_requests: List[Dict] = process_pull_requests(pull_requests, DEFAULT_DROPPED_FIELDS)
    write_json_to_file(processed_pull_requests, f"{org_name}_prs.json")

print("FETCHING COMMENTS")
comments: Optional[List[Dict]] = fetch_all_comments(org_name, global_token, session=session)
if comments:
    processed_comments: List[Dict] = process_comments(comments, DEFAULT_DROPPED_FIELDS)
    write_json_to_file(processed_comments, f"{org_name}_comments.json")

print("FETCHING DISCUSSIONS")
all_discussions: Optional[List[Dict]] = fetch_all_discussions(org_name, global_token, session=session)
if all_discussions:
    processed_discussions: List[Dict] = process_discussions(all_discussions, DEFAULT_DROPPED_FIELDS)
    print(f"Total discussions fetched from all repositories: {len(processed_discussions)}")
    write_json_to_file(processed_discussions, f"{org_name}_discussions.json")
