import os
import sys
import time
import json
import requests
from collections import defaultdict

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
RETRY_DELAY = 3


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def fetch_pull_requests(username, token):
    """Fetch all PRs with pagination and retry logic."""
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
            time.sleep(0.5)
        else:
            break

    return all_prs


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

    org_stats = defaultdict(lambda: {"MERGED": 0, "OPEN": 0, "CLOSED": 0})

    for pr in pull_requests:
        org = pr["repository"]["owner"]["login"]
        org_stats[org][pr["state"]] += 1

    output_dir = config.get("output_dir", "charts")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "data.json")
    with open(output_path, "w") as f:
        json.dump(dict(org_stats), f, indent=2)

    print(f"Stats saved to {output_path}")


if __name__ == "__main__":
    main()
