import json
import time
from typing import Any, Dict, List, Optional

import requests
from requests_cache import CachedSession
from typing_extensions import TypedDict  # Use from typing_extensions for compatibility with older Python versions

REQUESTS_TIMEOUT = 10  # Timeout in seconds for requests

# Default fields to be dropped from responses
DEFAULT_DROPPED_FIELDS = [
    "_links",
    "base",
    "comments_url",
    "commits_url",
    "diff_url",
    "events_url",
    "head",
    "html_url",
    "labels_url",
    "locked",
    "merge_commit_sha",
    "node_id",
    "patch_url",
    "repository_url",
    "review_comment_url",
    "review_comments_url",
    "statuses_url",
    "timeline_url",
]


class EnvironmentVariableError(Exception):
    """Exception raised for errors in the environment variables."""

    def __init__(self, variable: str, message: str = "is not set in the environment.") -> None:
        self.variable = variable
        self.message = message
        super().__init__(f"{variable} {message}")


class RateLimit(TypedDict):
    limit: int
    remaining: int
    reset: int
    used: int


class RateLimitResponse(TypedDict):
    rate: RateLimit
    resources: Dict[str, RateLimit]


def return_verbatim(input_string: str) -> str:
    """Return the input string."""
    return input_string


def get_rate_limit(token: str, session: CachedSession) -> RateLimitResponse:
    """Fetch current rate limit status from GitHub API."""
    headers = {"Authorization": f"token {token}"}
    response = session.get("https://api.github.com/rate_limit", headers=headers, timeout=REQUESTS_TIMEOUT)
    response.raise_for_status()  # Raises HTTPError for bad requests
    data: RateLimitResponse = response.json()
    return data


def wait_for_rate_limit_reset(reset_time: int) -> None:
    """Wait until the rate limit reset time."""
    wait_time = reset_time - int(time.time()) + 10  # Adding 10 seconds to ensure the reset has occurred
    print(f"Rate limit exceeded. Waiting for {wait_time} seconds.")
    time.sleep(wait_time)


def remove_keys_from_dict(data: Dict[str, Any], keys_to_remove: List[str]) -> Dict[str, Any]:
    """Remove specified keys from a dictionary."""
    return {key: value for key, value in data.items() if key not in keys_to_remove}


def write_json_to_file(json_object: List[Dict[str, Any]], filename: str) -> None:
    """Save data to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(json_object, f, ensure_ascii=False, indent=4)
        print(f"Data saved to {filename}")


def handle_response_errors(response: requests.Response) -> None:
    """Handle HTTP errors from a response."""
    if response.status_code == 404:
        print("Resource not found. Check the requested resource or permissions.")
    elif response.status_code == 403:
        print("Access forbidden. Ensure token has the required scopes or check for rate limits.")
    elif response.status_code == 401:
        print("Unauthorized. Check if the token is valid or expired.")
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
    print("Error message:", response.text)


def github_token_check(token: str, session: CachedSession) -> Optional[Dict[str, Any]]:
    """Validate the GitHub token by fetching user profile."""
    headers = {"Authorization": f"token {token}"}
    response = session.get("https://api.github.com/user", headers=headers, timeout=REQUESTS_TIMEOUT)
    if response.status_code == 200:
        print("Token is valid. User data retrieved successfully.")
        data: Dict[str, Any] = response.json()
        return data
    print(f"Failed to authenticate. Status code: {response.status_code}")
    return None


def list_user_orgs(token: str, session: CachedSession) -> Optional[List[Dict[str, Any]]]:
    """List all organizations the user is a member of."""
    rate_limit = get_rate_limit(token, session)
    if rate_limit["rate"]["remaining"] == 0:
        wait_for_rate_limit_reset(rate_limit["rate"]["reset"])
    headers = {"Authorization": f"token {token}"}
    response = session.get("https://api.github.com/user/orgs", headers=headers, timeout=REQUESTS_TIMEOUT)
    if response.status_code == 200:
        print("Organizations retrieved successfully.")
        data: List[Dict[str, Any]] = response.json()
        return data
    handle_response_errors(response)
    return None


def get_repos(org: str, token: str, session: CachedSession) -> Optional[List[Dict[str, Any]]]:
    """Fetch all repositories for a given organization."""
    rate_limit = get_rate_limit(token, session)
    if rate_limit["rate"]["remaining"] == 0:
        wait_for_rate_limit_reset(rate_limit["rate"]["reset"])
    repos: List[Dict[str, Any]] = []
    url = f"https://api.github.com/orgs/{org}/repos"
    headers = {"Authorization": f"token {token}"}
    while url:
        response = session.get(url, headers=headers, timeout=REQUESTS_TIMEOUT)
        if response.status_code == 200:
            repos.extend(response.json())
            url = response.links.get("next", {}).get("url")
        else:
            handle_response_errors(response)
            return None
    return repos


def fetch_issues(org: str, token: str, session: CachedSession) -> Optional[List[Dict[str, Any]]]:
    """Fetch all issues from all repositories in an organization, handling pagination and rate limits."""
    issues: List[Dict[str, Any]] = []
    repos = get_repos(org, token, session)
    if not repos:
        print("No repositories found or failed to fetch repositories.")
        return None

    for repo in repos:
        # Ensure the URL is constructed to fetch all issues (not just open ones)
        url = repo["issues_url"].replace("{/number}", "?state=all")
        while url:
            rate_limit = get_rate_limit(token, session)  # Check rate limit before each request
            if rate_limit["rate"]["remaining"] == 0:
                wait_for_rate_limit_reset(rate_limit["rate"]["reset"])

            response = session.get(url, headers={"Authorization": f"token {token}"}, timeout=REQUESTS_TIMEOUT)
            if response.status_code == 200:
                issues.extend(response.json())
                links = response.links
                url = links["next"]["url"] if "next" in links else None
            else:
                print(f"Failed to fetch issues for {repo['name']}. Status code: {response.status_code}")
                print("Error message:", response.text)
                return None
    return issues


def sanitize_user_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize user data to keep only the user 'login'."""
    if isinstance(data, dict):
        if "login" in data and set(data.keys()) - {"login"}:
            return {"login": data["login"]}
        else:
            return {key: sanitize_user_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_user_data(item) for item in data]
    return data


def remove_empty_values(data: Any) -> Any:
    """Recursively remove keys with empty values from a dictionary or list."""
    if isinstance(data, dict):
        return {k: remove_empty_values(v) for k, v in data.items() if v or isinstance(v, bool)}
    elif isinstance(data, list):
        return [remove_empty_values(item) for item in data if item or isinstance(item, bool)]
    return data


def process_issues(issues: List[Dict[str, Any]], keys_to_remove: List[str]) -> List[Dict[str, Any]]:
    """Process a list of issues to sanitize user information and remove empty values."""
    processed_issues: List[Dict[str, Any]] = []
    for issue in issues:
        sanitized_issue = sanitize_user_data(issue)
        cleaned_issue = remove_empty_values(sanitized_issue)
        final_issue = remove_keys_from_dict(cleaned_issue, keys_to_remove)
        processed_issues.append(final_issue)
    return processed_issues


def fetch_pull_requests(org: str, token: str, session: CachedSession) -> Optional[List[Dict[str, Any]]]:
    """Fetch all pull requests from all repositories in an organization, handling pagination and rate limits."""
    pull_requests: List[Dict[str, Any]] = []
    repos = get_repos(org, token, session)
    if not repos:
        print("No repositories found or failed to fetch repositories.")
        return None

    for repo in repos:
        url = f"{repo['url']}/pulls?state=all"
        while url:
            rate_limit = get_rate_limit(token, session)  # Check rate limit before each request
            if rate_limit["rate"]["remaining"] == 0:
                wait_for_rate_limit_reset(rate_limit["rate"]["reset"])

            response = session.get(url, headers={"Authorization": f"token {token}"}, timeout=REQUESTS_TIMEOUT)
            if response.status_code == 200:
                pull_requests.extend(response.json())
                links = response.links
                url = links["next"]["url"] if "next" in links else None
            else:
                print(f"Failed to fetch pull requests for {repo['name']}. Status code: {response.status_code}")
                print("Error message:", response.text)
                return None
    return pull_requests


def process_pull_requests(pull_requests: List[Dict[str, Any]], keys_to_remove: List[str]) -> List[Dict[str, Any]]:
    """Process a list of pull requests to sanitize user information and remove empty values."""
    processed_pull_requests: List[Dict[str, Any]] = []
    for pr in pull_requests:
        sanitized_pr = sanitize_user_data(pr)
        cleaned_pr = remove_empty_values(sanitized_pr)
        final_pr = remove_keys_from_dict(cleaned_pr, keys_to_remove)
        processed_pull_requests.append(final_pr)
    return processed_pull_requests


def fetch_all_comments(org: str, token: str, session: CachedSession) -> Optional[List[Dict[str, Any]]]:
    """Fetch all comments from all repositories in an organization,
    distinguishing between issue and PR comments, while handling pagination and rate limits."""
    all_comments: List[Dict[str, Any]] = []
    repos = get_repos(org, token, session)
    if not repos:
        print("No repositories found or failed to fetch repositories.")
        return None

    for repo in repos:
        # Adjusting per_page to fetch more comments per request if needed
        url = f"{repo['url']}/issues/comments?per_page=100"
        while url:
            rate_limit = get_rate_limit(token, session)  # Check rate limit before each request
            if rate_limit["rate"]["remaining"] == 0:
                wait_for_rate_limit_reset(rate_limit["rate"]["reset"])

            response = session.get(url, headers={"Authorization": f"token {token}"}, timeout=REQUESTS_TIMEOUT)
            if response.status_code == 200:
                comments = response.json()
                for comment in comments:
                    if "pull_request" in comment:
                        comment["type"] = "pull_request"
                    else:
                        comment["type"] = "issue"
                all_comments.extend(comments)
                links = response.links
                url = links["next"]["url"] if "next" in links else None
            else:
                print(f"Failed to fetch comments for {repo['name']}. Status code: {response.status_code}")
                print("Error message:", response.text)
                return None
    return all_comments


def process_comments(comments: List[Dict[str, Any]], keys_to_remove: List[str]) -> List[Dict[str, Any]]:
    """Process a list of comments to sanitize user information and remove empty values."""
    processed_comments: List[Dict[str, Any]] = []
    for comment in comments:
        sanitized_comment = sanitize_user_data(comment)
        cleaned_comment = remove_empty_values(sanitized_comment)
        final_comment = remove_keys_from_dict(cleaned_comment, keys_to_remove)
        processed_comments.append(final_comment)
    return processed_comments


def fetch_all_discussions(org: str, token: str, session: CachedSession) -> Optional[List[Dict[str, Any]]]:
    """Fetch discussions from all repositories in the specified organization."""
    all_discussions: List[Dict[str, Any]] = []
    repos = get_repos(org, token, session)
    if repos:
        for repo in repos:
            repo_name = repo["name"] if isinstance(repo, dict) else repo
            print(f"Fetching discussions for repository: {repo_name}")
            discussions = fetch_discussions_graphql(org, repo_name, token)
            if discussions:
                all_discussions.extend(discussions)
            else:
                print(f"No discussions found or an error occurred for repository: {repo_name}")
    return all_discussions


def fetch_discussions_graphql(org: str, repo: str, token: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch discussions using GitHub's GraphQL API."""
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {token}"}
    query = """
    query FetchDiscussions($org: String!, $repo: String!) {
      repository(owner: $org, name: $repo) {
        discussions(first: 100) {
          nodes {
            number
            title
            url
            bodyText
            createdAt
            updatedAt
            author {
              login
            }
            labels(first: 10) {
              nodes {
                name
                description
              }
            }
          }
        }
      }
    }
    """
    variables = {"org": org, "repo": repo}
    # Added a timeout of 10 seconds
    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers, timeout=10)
    if response.status_code == 200:
        data: Any = response.json()
        if "errors" in data:
            print(f"GraphQL Errors: {json.dumps(data['errors'], indent=2)}")
        nodes: Optional[List[Dict[str, Any]]] = (
            data.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
        )
        return nodes
    print(f"Failed to fetch discussions. Status code: {response.status_code}")
    print("Response: ", response.text)
    return None


def process_discussions(discussions: List[Dict[str, Any]], keys_to_remove: List[str]) -> List[Dict[str, Any]]:
    """Process a list of discussions to sanitize user information, remove empty values, and remove specified keys."""
    processed_discussions: List[Dict[str, Any]] = []
    for discussion in discussions:
        sanitized_discussion = sanitize_user_data(discussion)
        cleaned_discussion = remove_empty_values(sanitized_discussion)
        final_discussion = remove_keys_from_dict(cleaned_discussion, keys_to_remove)
        processed_discussions.append(final_discussion)
    return processed_discussions


def force_release() -> None:
    """Force a release of the package to PyPI."""
    # This function is used for demonstration purposes and should not be used in production
    pass
