#!/usr/bin/env python3
"""Generate an animated GitHub contribution pulse from GitHub-owned data."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import urllib.request
from collections import defaultdict
from pathlib import Path


USERNAME = os.getenv("GITHUB_USERNAME", "waleed-khan-743726")
OUTPUT = Path("assets/github-signal.svg")
SNAPSHOT = Path("data/contributions-snapshot.json")


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fetch_contributions(today: dt.date):
    start = today - dt.timedelta(days=364)
    token = os.getenv("PROFILE_TOKEN", "")

    if token:
        query = """
        query($login:String!, $from:DateTime!, $to:DateTime!) {
          user(login:$login) {
            contributionsCollection(from:$from, to:$to) {
              contributionCalendar {
                totalContributions
                weeks { contributionDays { date contributionCount } }
              }
            }
          }
        }
        """
        payload = json.dumps(
            {
                "query": query,
                "variables": {
                    "login": USERNAME,
                    "from": f"{start.isoformat()}T00:00:00Z",
                    "to": f"{today.isoformat()}T23:59:59Z",
                },
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "waleed-contribution-pulse",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("errors"):
            raise RuntimeError(result["errors"])
        calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        days = {}
        for week in calendar["weeks"]:
            for item in week["contributionDays"]:
                day = dt.date.fromisoformat(item["date"])
                if start <= day <= today:
                    count = int(item["contributionCount"])
                    days[day] = {"level": min(4, count), "count": count, "id": ""}
        total = int(calendar["totalContributions"])
    elif SNAPSHOT.exists():
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        total = int(snapshot["total"])
        days = {
            dt.date.fromisoformat(item["date"]): {
                "level": min(4, int(item["count"])),
                "count": int(item["count"]),
                "id": "",
            }
            for item in snapshot["active"]
        }
    else:
        total, days = fetch_public_contributions(today, start)

    cursor = start
    while cursor <= today:
        days.setdefault(cursor, {"level": 0, "count": 0, "id": ""})
        cursor += dt.timedelta(days=1)
    return start, total, days


def fetch_public_contributions(today: dt.date, start: dt.date):
    # GitHub's unfiltered contribution view is the same rolling-year dataset
    # shown on the public profile. Supplying from/to switches the page into a
    # calendar-year mode, which would incorrectly omit the previous months.
    url = f"https://github.com/users/{USERNAME}/contributions"
    local_source = os.getenv("GITHUB_CONTRIBUTIONS_FILE", "")
    if local_source:
        page = Path(local_source).read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(
            url,
            headers={"Accept": "text/html", "User-Agent": "waleed-contribution-pulse"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8")

    total_match = re.search(
        r'<h2[^>]+id="js-contribution-activity-description"[^>]*>\s*([\d,]+)',
        page,
        re.S,
    )
    total = int(total_match.group(1).replace(",", "")) if total_match else 0

    days = {}
    for cell in re.findall(r'<td[^>]+data-date="\d{4}-\d{2}-\d{2}"[^>]*>', page, re.S):
        date_match = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', cell)
        level_match = re.search(r'data-level="([0-4])"', cell)
        id_match = re.search(r'id="([^"]+)"', cell)
        if not (date_match and level_match and id_match):
            continue
        day = dt.date.fromisoformat(date_match.group(1))
        if not start <= day <= today:
            continue
        days[day] = {
            "level": int(level_match.group(1)),
            "count": 0,
            "id": id_match.group(1),
        }

    counts_by_id = {}
    for element_id, label in re.findall(
        r'<tool-tip[^>]+for="([^"]+)"[^>]*>([^<]+)</tool-tip>', page, re.S
    ):
        count_match = re.search(r"([\d,]+) contribution", label)
        counts_by_id[element_id] = (
            int(count_match.group(1).replace(",", "")) if count_match else 0
        )
    for item in days.values():
        item["count"] = counts_by_id.get(item["id"], 0)

    return total, days


def metrics(today: dt.date, days):
    active_days = sum(item["count"] > 0 for item in days.values())
    current_streak = 0
    cursor = today
    while days.get(cursor, {}).get("count", 0) > 0:
        current_streak += 1
        cursor -= dt.timedelta(days=1)
    peak_day, peak_item = max(days.items(), key=lambda pair: pair[1]["count"])
    last_30 = sum(
        days.get(today - dt.timedelta(days=offset), {}).get("count", 0)
        for offset in range(30)
    )
    return active_days, current_streak, peak_day, peak_item["count"], last_30


def month_key(day: dt.date):
    return day.year, day.month


def recent_months(today: dt.date):
    months = []
    year, month = today.year, today.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def text(x, y, value, *, size=16, fill="#dbeafe", weight=500, anchor="start", cls="sans"):
    return (
        f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def stat_card(x, label, value, note, color):
    return f"""
    <g class="rise">
      <rect x="{x}" y="112" width="252" height="112" rx="18" class="card"/>
      {text(x + 18, 140, label.upper(), size=10, fill="#8194af", weight=700, cls="mono")}
      {text(x + 18, 181, value, size=31, fill=color, weight=800)}
      {text(x + 18, 207, note, size=9, fill="#8da0bb", cls="mono")}
    </g>
    """


def line_path(values, x, y, width, height, maximum):
    if len(values) == 1:
        return f"M{x},{y + height / 2}"
    points = []
    for index, value in enumerate(values):
        px = x + width * index / (len(values) - 1)
        py = y + height - (value / maximum * height if maximum else 0)
        points.append((px, py))
    return "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in points), points


def generate_svg():
    today = dt.datetime.now(dt.timezone.utc).date()
    start, total, days = fetch_contributions(today)
    active_days, current_streak, peak_day, peak_count, last_30_total = metrics(today, days)

    daily_dates = [today - dt.timedelta(days=offset) for offset in reversed(range(30))]
    daily_values = [days[day]["count"] for day in daily_dates]
    daily_max = max(max(daily_values), 1)
    daily_path, daily_points = line_path(daily_values, 88, 314, 1004, 182, daily_max)
    daily_area = daily_path + " L1092,496 L88,496 Z"

    monthly_counts = defaultdict(int)
    for day, item in days.items():
        monthly_counts[month_key(day)] += item["count"]
    months = recent_months(today)
    monthly_values = [monthly_counts[key] for key in months]
    monthly_max = max(max(monthly_values), 1)
    monthly_path, monthly_points = line_path(monthly_values, 88, 594, 1004, 92, monthly_max)
    monthly_area = monthly_path + " L1092,686 L88,686 Z"

    parts = [f"""<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="760" viewBox="0 0 1180 760" role="img" aria-labelledby="title desc">
<title id="title">Animated GitHub contribution pulse for Muhammad Waleed</title>
<desc id="desc">Live rolling contribution totals with animated daily and monthly line graphs, generated from GitHub contribution data.</desc>
<defs>
  <linearGradient id="background" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#050b18"/><stop offset=".55" stop-color="#0b1830"/><stop offset="1" stop-color="#07111f"/></linearGradient>
  <linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset=".52" stop-color="#a78bfa"/><stop offset="1" stop-color="#f6c85f"/></linearGradient>
  <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22d3ee" stop-opacity=".32"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></linearGradient>
  <linearGradient id="area2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a78bfa" stop-opacity=".26"/><stop offset="1" stop-color="#a78bfa" stop-opacity="0"/></linearGradient>
  <radialGradient id="glow"><stop offset="0" stop-color="#22d3ee" stop-opacity=".2"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient>
  <pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#8ca0c0" stroke-opacity=".055"/></pattern>
  <filter id="soft"><feGaussianBlur stdDeviation="5"/></filter>
  <style>
    .sans {{font-family:"Segoe UI",Inter,Arial,sans-serif}}
    .mono {{font-family:"Cascadia Code",Consolas,monospace}}
    .card {{fill:#0c1b30;stroke:#263e60;stroke-width:1.5}}
    .chart {{fill:#09172a;stroke:#263e60;stroke-width:1.5}}
    .draw {{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2.4s cubic-bezier(.2,.8,.2,1) forwards}}
    .draw2 {{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2s .45s cubic-bezier(.2,.8,.2,1) forwards}}
    .fade {{opacity:0;animation:fade .8s 1.25s ease-out forwards}}
    .fade2 {{opacity:0;animation:fade .8s 1.55s ease-out forwards}}
    .point {{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .32s ease-out forwards}}
    .pulse {{animation:pulse 1.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
    .rise {{animation:rise .65s ease-out both}}
    @keyframes draw {{to {{stroke-dashoffset:0}}}}
    @keyframes fade {{to {{opacity:1}}}}
    @keyframes pop {{0% {{opacity:0;transform:scale(0)}} 70% {{opacity:1;transform:scale(1.35)}} 100% {{opacity:1;transform:scale(1)}}}}
    @keyframes pulse {{0%,100% {{opacity:.55;transform:scale(.8)}} 50% {{opacity:1;transform:scale(1.25)}}}}
    @keyframes rise {{from {{opacity:0;transform:translateY(10px)}} to {{opacity:1;transform:translateY(0)}}}}
  </style>
</defs>
<rect width="1180" height="760" rx="26" fill="url(#background)"/>
<rect width="1180" height="760" rx="26" fill="url(#grid)"/>
<circle cx="1035" cy="30" r="260" fill="url(#glow)"/>
<rect y="754" width="1180" height="6" fill="url(#line)"/>

{text(56, 52, "GITHUB CONTRIBUTION PULSE", size=26, fill="#f8fafc", weight=800)}
{text(56, 78, "REAL DAILY ACTIVITY  //  ANIMATED  //  AUTO-REFRESHED", size=10, fill="#22d3ee", weight=750, cls="mono")}
<circle cx="970" cy="48" r="7" fill="#39e58c" class="pulse"/>
{text(988, 52, "LIVE", size=10, fill="#a7f3d0", weight=800, cls="mono")}
{text(1124, 77, f"UPDATED {today.isoformat()} UTC", size=9, fill="#8194af", anchor="end", cls="mono")}

{stat_card(56, "Last 365 days", total, f"{start.strftime('%d %b %Y')} — {today.strftime('%d %b %Y')}", "#22d3ee")}
{stat_card(326, "Last 30 days", last_30_total, "ROLLING CONTRIBUTIONS", "#f6c85f")}
{stat_card(596, "Current streak", current_streak, f"{active_days} ACTIVE DAYS / YEAR", "#39e58c")}
{stat_card(866, "Peak day", peak_count, peak_day.strftime("%d %b %Y").upper(), "#a78bfa")}

{text(56, 270, "DAILY ACTIVITY", size=14, fill="#f8fafc", weight=750)}
{text(1124, 270, "ROLLING 30 DAYS  •  EACH POINT = ONE DAY", size=9, fill="#8194af", anchor="end", cls="mono")}
<rect x="56" y="286" width="1068" height="246" rx="18" class="chart"/>
"""]

    for index in range(5):
        y = 314 + index * (182 / 4)
        value = round(daily_max * (4 - index) / 4)
        parts.append(f'<path d="M88 {y:.1f}H1092" stroke="#28405f" stroke-opacity=".45" stroke-dasharray="4 7"/>')
        parts.append(text(78, y + 4, value, size=8, fill="#60738f", anchor="end", cls="mono"))

    parts.append(f'<path d="{daily_area}" fill="url(#area)" class="fade"/>')
    parts.append(f'<path d="{daily_path}" pathLength="1" fill="none" stroke="url(#line)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" class="draw"/>')
    parts.append(f'<path d="{daily_path}" fill="none" stroke="#22d3ee" stroke-opacity=".22" stroke-width="13" filter="url(#soft)"/>')

    for index, ((px, py), value, day) in enumerate(zip(daily_points, daily_values, daily_dates)):
        delay = 0.7 + index * 0.045
        radius = 5 if value else 2.5
        color = "#f6c85f" if value == daily_max and value > 0 else "#67e8f9"
        parts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius}" fill="{color}" stroke="#07101f" stroke-width="2" class="point" style="animation-delay:{delay:.2f}s">'
            f'<title>{day.isoformat()} — {value} contribution{"s" if value != 1 else ""}</title></circle>'
        )
        if index % 5 == 0 or index == len(daily_dates) - 1:
            parts.append(text(px, 517, day.strftime("%d %b").upper(), size=8, fill="#687b97", anchor="middle", cls="mono"))

    parts.extend([f"""
{text(56, 570, "12-MONTH TREND", size=14, fill="#f8fafc", weight=750)}
{text(1124, 570, "MONTHLY CONTRIBUTION TOTALS", size=9, fill="#8194af", anchor="end", cls="mono")}
<rect x="56" y="584" width="1068" height="136" rx="18" class="chart"/>
<path d="M88 686H1092" stroke="#28405f" stroke-opacity=".65"/>
"""])

    for index, (point, value, key) in enumerate(zip(monthly_points, monthly_values, months)):
        px, py = point
        bar_height = (value / monthly_max * 82) if monthly_max else 0
        parts.append(f'<rect x="{px - 17:.1f}" y="{686 - bar_height:.1f}" width="34" height="{bar_height:.1f}" rx="8" fill="#22d3ee" fill-opacity=".1"/>')
        parts.append(text(px, 709, dt.date(key[0], key[1], 1).strftime("%b").upper(), size=8, fill="#687b97", anchor="middle", cls="mono"))

    parts.append(f'<path d="{monthly_area}" fill="url(#area2)" class="fade2"/>')
    parts.append(f'<path d="{monthly_path}" pathLength="1" fill="none" stroke="url(#line)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" class="draw2"/>')
    for index, ((px, py), value, key) in enumerate(zip(monthly_points, monthly_values, months)):
        parts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#a78bfa" stroke="#07101f" stroke-width="2" class="point" style="animation-delay:{1.25 + index * .08:.2f}s">'
            f'<title>{dt.date(key[0], key[1], 1).strftime("%B %Y")} — {value} contributions</title></circle>'
        )

    parts.append(text(590, 744, f"github.com/{USERNAME}  •  sourced directly from GitHub  •  refreshes automatically every hour", size=9, fill="#61738e", anchor="middle", cls="mono"))
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate_svg(), encoding="utf-8")
    print(f"Wrote {OUTPUT.resolve()}")
