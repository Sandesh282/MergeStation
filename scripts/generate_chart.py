import json
import math
import os
import requests
import base64

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

# Styling
COLOR_MERGED = "#a371f7"
COLOR_OPEN = "#3fb950"
TEXT_COLOR = "#c9d1d9"
COLOR_LINE = "#30363d"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def fetch_image_as_base64(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            encoded = base64.b64encode(response.content).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
    except Exception:
        pass
    return ""


def generate_svg():
    config = load_config()
    username = config["username"]
    excluded = config.get("excluded_orgs", [])
    max_orgs = config.get("max_orgs", 8)
    output_dir = config.get("output_dir", "charts")

    data_path = os.path.join(output_dir, "data.json")
    with open(data_path) as f:
        data = json.load(f)

    # Filter and sort
    active_orgs = {
        k: v for k, v in data.items()
        if k not in excluded and (v["MERGED"] > 0 or v["OPEN"] > 0)
    }

    sorted_orgs = sorted(
        active_orgs.keys(),
        key=lambda x: (active_orgs[x]["MERGED"], active_orgs[x]["OPEN"]),
        reverse=True,
    )[:max_orgs]

    if not sorted_orgs:
        print("No active organizations found.")
        return

    # TODO: implement SVG generation
    print(f"Found {len(sorted_orgs)} active orgs: {sorted_orgs}")
    print("SVG generation not yet implemented.")


if __name__ == "__main__":
    generate_svg()
