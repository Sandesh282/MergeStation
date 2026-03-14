import json
import math
import os
import requests
import base64

# ──────────────────────────────────────────────
# MergeStation — Contribution Graph Generator
# Generates a hub-and-spoke SVG visualization
# showing PR contributions across organizations.
#
# Environment variable overrides:
#   MAX_ORGS — override config max_orgs
# ──────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

# --- STYLING ---
COLOR_BG = "transparent"
COLOR_LINE = "#30363d"
COLOR_MERGED = "#a371f7"  # Neon Purple
COLOR_OPEN = "#3fb950"    # Neon Green
TEXT_COLOR = "#c9d1d9"


def load_config():
    """Load configuration from config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_env_override(env_key, config_value, cast_type=str):
    """Return env var value if set, otherwise fall back to config."""
    env_val = os.environ.get(env_key)
    if env_val is not None and env_val != "":
        return cast_type(env_val)
    return config_value


def fetch_image_as_base64(url):
    """Download an image and return it as a base64-encoded data URI."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            encoded = base64.b64encode(response.content).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
    except Exception:
        pass
    return ""


def create_circular_clip_path(id_name, x, y, r):
    """Create an SVG circular clip path definition."""
    return f"""
    <clipPath id="{id_name}">
        <circle cx="{x}" cy="{y}" r="{r}" />
    </clipPath>
    """


def generate_svg():
    """Generate the hub-and-spoke SVG contribution graph."""
    config = load_config()
    username = config["username"]
    excluded = config.get("excluded_orgs", [])
    max_orgs = get_env_override("MAX_ORGS", config.get("max_orgs", 8), cast_type=int)
    output_dir = config.get("output_dir", "charts")

    # 1. Load Data
    data_path = os.path.join(output_dir, "data.json")
    with open(data_path) as f:
        data = json.load(f)

    # 2. Filter & Sort — only include orgs with merged or open PRs
    active_orgs = {
        k: v for k, v in data.items()
        if k not in excluded
        and (v["MERGED"] > 0 or v["OPEN"] > 0)
    }

    sorted_orgs = sorted(
        active_orgs.keys(),
        key=lambda x: (active_orgs[x]["MERGED"], active_orgs[x]["OPEN"]),
        reverse=True,
    )[:max_orgs]

    if not sorted_orgs:
        print("No active organizations found. Skipping chart generation.")
        return

    # 3. Layout Configuration
    width = 800
    height = 500
    center_x = width / 2
    center_y = height / 2
    orbit_radius = 180
    user_r = 40
    org_r = 25
    gap = 10

    # 4. Fetch User Avatar
    user_img_url = f"https://github.com/{username}.png"
    user_b64 = fetch_image_as_base64(user_img_url)

    # 5. Build SVG
    svg_content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<style>.text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: {TEXT_COLOR}; font-weight: 600; }} .sub {{ font-size: 10px; font-weight: 400; }}</style>',
        "<defs>",
        f'<marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">',
        f'<path d="M0,0 L0,6 L9,3 z" fill="{COLOR_LINE}" />',
        "</marker>",
    ]

    main_content = []

    # Central User Avatar
    svg_content.append(create_circular_clip_path("user-clip", center_x, center_y, user_r))

    # Outer glow ring for user
    main_content.append(
        f'<circle cx="{center_x}" cy="{center_y}" r="{user_r + 4}" fill="#21262d" stroke="#30363d" stroke-width="2" />'
    )

    # User image
    main_content.append(
        f'<image href="{user_b64}" x="{center_x - user_r}" y="{center_y - user_r}" '
        f'width="{user_r * 2}" height="{user_r * 2}" clip-path="url(#user-clip)" />'
    )

    # 6. Draw Organizations
    num_orgs = len(sorted_orgs)

    for i, org_name in enumerate(sorted_orgs):
        stats = active_orgs[org_name]
        merged = stats["MERGED"]
        _open = stats["OPEN"]

        # Calculate angle for radial placement
        angle = (2 * math.pi * i / num_orgs) - (math.pi / 2)

        # Line start: center + user_radius + gap
        start_dist = user_r + gap + 5
        x1 = center_x + start_dist * math.cos(angle)
        y1 = center_y + start_dist * math.sin(angle)

        # Line end: center + orbit_radius - org_radius - gap
        end_dist = orbit_radius - org_r - gap
        x2 = center_x + end_dist * math.cos(angle)
        y2 = center_y + end_dist * math.sin(angle)

        # Org center coordinates
        org_x = center_x + orbit_radius * math.cos(angle)
        org_y = center_y + orbit_radius * math.sin(angle)

        # Connector line — solid if merged, dashed if open-only
        stroke_dash = "" if merged > 0 else 'stroke-dasharray="5,5"'

        # Insert lines behind org icons
        main_content.insert(
            0,
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{COLOR_LINE}" stroke-width="2" {stroke_dash} '
            f'marker-end="url(#arrow)" />',
        )

        # Fetch Org Avatar
        org_img_url = f"https://github.com/{org_name}.png"
        org_b64 = fetch_image_as_base64(org_img_url)

        clip_id = f"clip-{i}"
        svg_content.append(create_circular_clip_path(clip_id, org_x, org_y, org_r))

        # Org ring and image
        ring_color = COLOR_MERGED if merged > 0 else COLOR_OPEN
        main_content.append(
            f'<circle cx="{org_x}" cy="{org_y}" r="{org_r + 3}" '
            f'fill="#0d1117" stroke="{ring_color}" stroke-width="2" />'
        )
        main_content.append(
            f'<image href="{org_b64}" x="{org_x - org_r}" y="{org_y - org_r}" '
            f'width="{org_r * 2}" height="{org_r * 2}" clip-path="url(#{clip_id})" />'
        )

        # Stats text
        text_y = org_y + org_r + 20
        stat_text = ""
        if merged > 0:
            stat_text += f'<tspan fill="{COLOR_MERGED}">● {merged}</tspan> '
        if _open > 0:
            stat_text += f'<tspan fill="{COLOR_OPEN}">● {_open}</tspan>'

        main_content.append(
            f'<text x="{org_x}" y="{text_y}" text-anchor="middle" class="text" font-size="12">{org_name}</text>'
        )
        main_content.append(
            f'<text x="{org_x}" y="{text_y + 15}" text-anchor="middle" class="text sub">{stat_text}</text>'
        )

    # 7. Close SVG
    svg_content.append("</defs>")
    svg_content.extend(main_content)
    svg_content.append("</svg>")

    # 8. Write Output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "contribution_graph.svg")
    with open(output_path, "w") as f:
        f.write("".join(svg_content))

    print(f"Generated contribution graph for {num_orgs} orgs → {output_path}")


if __name__ == "__main__":
    generate_svg()
