import os

from core import (
    DEFAULT_DROPPED_FIELDS,
    CachedSession,
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
from dotenv import load_dotenv
from requests_cache.backends.sqlite import SQLiteCache

# Load environment variables from .env file
load_dotenv(dotenv_path="local/.env", verbose=True)

# Global access token for GitHub API
global_token = os.environ["GITHUB_TOKEN"]
if not global_token:
    raise EnvironmentVariableError("GITHUB_TOKEN")
print("Token loaded successfully.")

# Set up cache with SQLite backend
session = CachedSession(
    cache_name="llm-github-cache",
    backend=SQLiteCache("llm-github.sqlite", timeout=86400),  # Cache expires after 24 hours
)

user_data = github_token_check(global_token, session=session)
orgs = list_user_orgs(global_token, session=session)

# turbomam: Resource not found. This could be due to incorrect organization name or insufficient access permissions.
# Error message:
# {
#   "message": "Not Found",
#   "documentation_url": "https://docs.github.com/rest/repos/repos#list-organization-repositories",
#   "status": "404"
# }

# microbiomedata: Access forbidden. Check if your token has the required scopes or if there's a rate limit issue.
# Error message:
# {
#   "message": "`microbiomedata` forbids access via a personal access token (classic). Please use a GitHub App, OAuth App, or a personal access token with fine-grained permissions.",
#   "documentation_url": "https://docs.github.com/rest/repos/repos#list-organization-repositories",
#   "status": "403"
# }

# works: berkeleybop

org_name = "microbiomedata"

print("FETCHING REPOS")
repos = get_repos(org_name, global_token, session=session)
write_json_to_file(repos, f"{org_name}_repos.json")

print("FETCHING ISSUES")
org_issues = fetch_issues(org_name, global_token, session=session)
sanitized_issues = process_issues(org_issues, DEFAULT_DROPPED_FIELDS)
write_json_to_file(sanitized_issues, f"{org_name}_issues.json")

print("FETCHING PRs")
pull_requests = fetch_pull_requests(org_name, global_token, session=session)
processed_pull_requests = process_pull_requests(pull_requests, DEFAULT_DROPPED_FIELDS)
write_json_to_file(processed_pull_requests, f"{org_name}_prs.json")

print("FETCHING COMMENTS")
comments = fetch_all_comments(org_name, global_token, session=session)
processed_comments = process_comments(comments, DEFAULT_DROPPED_FIELDS)
write_json_to_file(processed_comments, f"{org_name}_comments.json")

print("FETCHING DISCUSSIONS")
all_discussions = fetch_all_discussions(org_name, global_token, session=session)
processed_discussions = process_discussions(all_discussions, DEFAULT_DROPPED_FIELDS)
print(f"Total discussions fetched from all repositories: {len(processed_discussions)}")
write_json_to_file(processed_discussions, f"{org_name}_discussions.json")
