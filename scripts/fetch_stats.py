# MergeStation - PR Stats Fetcher
import os
import sys
import time
import json
import requests
from collections import defaultdict

# ──────────────────────────────────────────────
# MergeStation — PR Stats Fetcher
# Fetches all pull requests for a GitHub user
# using the GraphQL API with cursor pagination.
# ──────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    pullRequests(first: 100, orderBy: {field: CREATED_AT, direction: DESC}, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        state
        createdAt
        repository {
          name
          owner {
            login
          }
        }
      }
    }
  }
}
"""

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def load_config():
    """Load configuration from config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def fetch_pull_requests(username, token):
    """
    Fetch all pull requests for a user using cursor-based pagination.
    Implements retry logic with exponential backoff for rate limiting.
    """
    headers = {"Authorization": f"Bearer {token}"}
    all_prs = []
    cursor = None
    page = 1

    while True:
        variables = {"login": username}
        if cursor:
            variables["after"] = cursor

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    GRAPHQL_URL,
                    json={"query": QUERY, "variables": variables},
                    headers=headers,
                    timeout=30,
                )

                if response.status_code == 200:
                    break
                elif response.status_code == 403:
                    # Rate limited — wait and retry
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    print(f"  Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"  HTTP {response.status_code}: {response.text}")
                    time.sleep(RETRY_DELAY)
            except requests.exceptions.RequestException as e:
                print(f"  Request error: {e}")
                time.sleep(RETRY_DELAY)
        else:
            print("Max retries exceeded. Stopping fetch.")
            break

        data = response.json()

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            break

        pr_data = data["data"]["user"]["pullRequests"]
        nodes = pr_data["nodes"]
        all_prs.extend(nodes)
        print(f"  Page {page}: fetched {len(nodes)} PRs (total: {len(all_prs)})")

        if pr_data["pageInfo"]["hasNextPage"]:
            cursor = pr_data["pageInfo"]["endCursor"]
            page += 1
            time.sleep(0.5)  # Small delay to be respectful of rate limits
        else:
            break

    return all_prs


def aggregate_stats(pull_requests):
    """Aggregate PR stats by organization/owner."""
    org_stats = defaultdict(lambda: {"MERGED": 0, "OPEN": 0, "CLOSED": 0})

    for pr in pull_requests:
        org = pr["repository"]["owner"]["login"]
        state = pr["state"]
        org_stats[org][state] += 1

    return dict(org_stats)


def main():
    config = load_config()
    username = config["username"]

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    print(f"Fetching PR data for user: {username}")
    pull_requests = fetch_pull_requests(username, token)
    print(f"Total PRs fetched: {len(pull_requests)}")

    org_stats = aggregate_stats(pull_requests)

    output_dir = config.get("output_dir", "charts")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "data.json")
    with open(output_path, "w") as f:
        json.dump(org_stats, f, indent=2)

    print(f"Stats saved to {output_path}")
    print("Organization stats:")
    for org, stats in sorted(org_stats.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total = sum(stats.values())
        print(f"  {org}: {total} PRs (Merged: {stats['MERGED']}, Open: {stats['OPEN']}, Closed: {stats['CLOSED']})")


if __name__ == "__main__":
    main()
