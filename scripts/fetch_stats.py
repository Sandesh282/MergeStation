import os
import sys
import json
import requests
from collections import defaultdict

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    pullRequests(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
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


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def main():
    config = load_config()
    username = config["username"]

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    print(f"Fetching PR data for user: {username}")
    response = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": {"login": username}},
        headers=headers,
    )

    data = response.json()
    org_stats = defaultdict(lambda: {"MERGED": 0, "OPEN": 0, "CLOSED": 0})

    for pr in data["data"]["user"]["pullRequests"]["nodes"]:
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
