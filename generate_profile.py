#!/usr/bin/env python3
'''
Generate a recruiter-focused GitHub profile SVG for:
    waleed-khan-743726

All GitHub metrics are fetched live when this script runs.
No profile numbers are manually invented.
'''

from __future__ import annotations

import datetime as dt
import html
import json
import os
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path


USERNAME = os.getenv("GITHUB_USERNAME", "waleed-khan-743726")
TOKEN = os.getenv("GITHUB_TOKEN", "")

OUT = Path("profile.svg")


def api(url: str, method="GET", payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "waleed-profile-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()

    req = urllib.request.Request(url, headers=headers, data=data, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def gql(query, variables):
    return api(
        "https://api.github.com/graphql",
        method="POST",
        payload={"query": query, "variables": variables},
    )


def esc(x):
    return html.escape(str(x), quote=True)


def iso(d):
    return d.isoformat()


def contribution_data():
    today = dt.date.today()
    start = dt.date(today.year, 1, 1)

    query = '''
    query($login:String!, $from:DateTime!, $to:DateTime!) {
      user(login:$login) {
        contributionsCollection(from:$from, to:$to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
        }
      }
    }
    '''

    result = gql(
        query,
        {
            "login": USERNAME,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
        },
    )

    if "errors" in result:
        raise RuntimeError(result["errors"])

    calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]

    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])

    # Keep only the requested calendar year.
    days = [
        d for d in days
        if dt.date.fromisoformat(d["date"]).year == today.year
    ]

    return today, calendar["totalContributions"], days


def profile_data():
    user = api(f"https://api.github.com/users/{USERNAME}")

    repos = api(
        f"https://api.github.com/users/{USERNAME}/repos"
        "?per_page=100&sort=updated&type=owner"
    )

    stars = sum(r.get("stargazers_count", 0) for r in repos)

    language_bytes = Counter()

    for repo in repos:
        # Forks are excluded from the language profile because they are not
        # the user's authored codebase.
        if repo.get("fork"):
            continue

        try:
            langs = api(repo["languages_url"])
            for name, amount in langs.items():
                language_bytes[name] += amount
        except Exception:
            pass

    return user, repos, stars, language_bytes


def streaks(days):
    counts = {
        dt.date.fromisoformat(d["date"]): d["contributionCount"]
        for d in days
    }

    today = dt.date.today()

    current = 0
    cursor = today
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= dt.timedelta(days=1)

    best = 0
    run = 0
    ordered = sorted(counts)

    for day in ordered:
        if counts.get(day, 0) > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0

    active_days = sum(1 for v in counts.values() if v > 0)
    best_day = max(counts.items(), key=lambda x: x[1], default=(today, 0))

    return current, best, active_days, best_day


def monthly(days):
    out = defaultdict(int)
    for d in days:
        day = dt.date.fromisoformat(d["date"])
        out[day.month] += d["contributionCount"]
    return out


def svg():
    today, total, days = contribution_data()
    user, repos, stars, language_bytes = profile_data()

    followers = user["followers"]
    following = user["following"]
    avatar = user.get("avatar_url", "")
    name = user.get("name") or "Muhammad Waleed"
    bio = user.get("bio") or "AI Engineer"
    location = user.get("location") or "Pakistan"

    current_streak, best_streak, active_days, best_day = streaks(days)
    month_totals = monthly(days)

    total_lang = sum(language_bytes.values())
    langs = language_bytes.most_common(5)

    # GitHub contribution color levels.
    level_color = {
        "NONE": "#0b2927",
        "FIRST_QUARTILE": "#0d514a",
        "SECOND_QUARTILE": "#08776d",
        "THIRD_QUARTILE": "#00aa98",
        "FOURTH_QUARTILE": "#6ffff0",
    }

    # Grid starts on Sunday and contains the complete current-year calendar.
    start = dt.date(today.year, 1, 1)
    grid_start = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    grid_end = today + dt.timedelta(days=(6 - today.weekday() - 1) % 7)

    day_map = {
        dt.date.fromisoformat(d["date"]): d
        for d in days
    }

    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        weeks.append([cursor + dt.timedelta(days=i) for i in range(7)])
        cursor += dt.timedelta(days=7)

    W = 1180
    H = 2650

    parts = []

    def add(x):
        parts.append(x)

    add(f'''<svg xmlns="http://www.w3.org/2000/svg"
      width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#031817"/>
    <stop offset=".5" stop-color="#062d2a"/>
    <stop offset="1" stop-color="#031c1b"/>
  </linearGradient>

  <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0a403c"/>
    <stop offset=".45" stop-color="#062d2b"/>
    <stop offset="1" stop-color="#05221f"/>
  </linearGradient>

  <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#00b9a5"/>
    <stop offset=".5" stop-color="#6ffff0"/>
    <stop offset="1" stop-color="#00b9a5"/>
  </linearGradient>

  <linearGradient id="orange" x1="0" x2="1">
    <stop stop-color="#ff6f00"/>
    <stop offset="1" stop-color="#ff9c2e"/>
  </linearGradient>

  <linearGradient id="purple" x1="0" x2="1">
    <stop stop-color="#866cff"/>
    <stop offset="1" stop-color="#bd9cff"/>
  </linearGradient>

  <linearGradient id="blue" x1="0" x2="1">
    <stop stop-color="#4d79ff"/>
    <stop offset="1" stop-color="#72a8ff"/>
  </linearGradient>

  <filter id="glow">
    <feGaussianBlur stdDeviation="5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>

  <filter id="bigGlow">
    <feGaussianBlur stdDeviation="24"/>
  </filter>

  <pattern id="microgrid" width="26" height="26" patternUnits="userSpaceOnUse">
    <path d="M26 0H0V26" fill="none" stroke="#0b4945" stroke-width="1" opacity=".35"/>
  </pattern>

  <style>
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .sans {{ font-family: Inter, Arial, sans-serif; }}
    .small {{ font-size: 11px; letter-spacing: 1.2px; }}
    .muted {{ fill:#6fa9a2; }}
    .white {{ fill:#e4fffb; }}
    .cyan {{ fill:#6ffff0; }}
    .panel {{ fill:url(#panel); stroke:#08776d; stroke-width:2; }}
    .card {{ fill:#062a28; stroke:#0b665f; stroke-width:1.5; }}
    .pulse {{ animation:pulse 2.2s ease-in-out infinite; transform-origin:center; }}
    .scan {{ animation:scan 5s linear infinite; }}
    .float {{ animation:float 4s ease-in-out infinite; }}
    @keyframes pulse {{
      0%,100% {{ opacity:.55; }}
      50% {{ opacity:1; }}
    }}
    @keyframes scan {{
      from {{ transform:translateY(-12px); opacity:.1; }}
      50% {{ opacity:.7; }}
      to {{ transform:translateY(300px); opacity:0; }}
    }}
    @keyframes float {{
      0%,100% {{ transform:translateY(0); }}
      50% {{ transform:translateY(-4px); }}
    }}
  </style>
</defs>

<rect width="{W}" height="{H}" fill="#ffffff"/>

<!-- HEADER -->
<rect x="24" y="22" width="1132" height="235" rx="24" class="panel"/>
<rect x="24" y="22" width="1132" height="235" rx="24"
      fill="url(#microgrid)" opacity=".35"/>

<ellipse cx="960" cy="110" rx="300" ry="150"
         fill="#00d9c0" opacity=".07" filter="url(#bigGlow)"/>

<circle cx="88" cy="86" r="50" fill="#041e1c" stroke="#6ffff0" stroke-width="2"/>
<image href="{esc(avatar)}" x="41" y="39" width="94" height="94"
       preserveAspectRatio="xMidYMid slice"
       clip-path="circle(47px at 47px 47px)"/>

<text x="165" y="56" class="mono small cyan">@{esc(USERNAME)}</text>
<text x="165" y="103" class="sans white"
      font-size="43" font-weight="800">MUHAMMAD WALEED</text>
<text x="165" y="131" class="mono cyan" font-size="15">AI ENGINEER</text>
<text x="165" y="158" class="mono muted" font-size="12">
  Voice AI • LLMs • Deep Learning • Real-Time AI Systems • Automation
</text>

<rect x="165" y="180" width="82" height="30" rx="8" fill="#052522" stroke="#168f83"/>
<text x="206" y="199" text-anchor="middle" class="mono" font-size="10" fill="#b9fff7">GitHub</text>

<rect x="257" y="180" width="82" height="30" rx="8" fill="#052522" stroke="#168f83"/>
<text x="298" y="199" text-anchor="middle" class="mono" font-size="10" fill="#b9fff7">LinkedIn</text>

<rect x="349" y="180" width="82" height="30" rx="8" fill="#052522" stroke="#168f83"/>
<text x="390" y="199" text-anchor="middle" class="mono" font-size="10" fill="#b9fff7">Python</text>

<circle cx="1112" cy="55" r="7" fill="#00e7ce" class="pulse"/>
<text x="1095" y="82" text-anchor="end" class="mono" font-size="9" fill="#54aaa1">
  PROFILE ONLINE
</text>

<!-- DIVIDER -->
<text x="590" y="293" text-anchor="middle"
      class="sans" font-size="19" fill="#182321">GitHub · X</text>

<!-- HIGHLIGHTS -->
<rect x="24" y="320" width="1132" height="190" rx="22" class="panel"/>
<text x="52" y="355" class="mono white" font-size="15" font-weight="700">HIGHLIGHTS</text>
<text x="52" y="374" class="mono muted small">PUBLIC ACCOUNT SNAPSHOT • LIVE DATA</text>

{metric_card(52, 395, 330, 92, "REPOSITORIES", user["public_repos"], "PUBLIC PROJECTS", "#6ffff0")}
{metric_card(425, 395, 330, 92, "FOLLOWERS", followers, "COMMUNITY", "#a990ff")}
{metric_card(798, 395, 330, 92, "STARS", stars, "REPOSITORY STARS", "#61a1ff")}

<!-- YEAR -->
<text x="24" y="558" class="sans" font-size="20" fill="#111b1b">The year, so far</text>

<rect x="24" y="580" width="1132" height="620" rx="22" class="panel"/>
<text x="52" y="617" class="mono white" font-size="16" font-weight="700">
  {today.year} // CONTRIBUTION MATRIX
</text>
<text x="52" y="638" class="mono muted small">
  EVERY DAY • EVERY WEEK • EVERY MONTH • YEAR-TO-DATE
</text>

<!-- Year total -->
<rect x="850" y="600" width="270" height="58" rx="12" class="card"/>
<text x="870" y="622" class="mono muted" font-size="9">YEAR-TO-DATE</text>
<text x="870" y="648" class="mono cyan" font-size="24" font-weight="700">{total}</text>
<text x="945" y="646" class="mono muted" font-size="10">contributions</text>

<!-- Contribution grid -->
<text x="72" y="690" class="mono muted" font-size="10">SUN</text>
<text x="72" y="714" class="mono muted" font-size="10">MON</text>
<text x="72" y="738" class="mono muted" font-size="10">TUE</text>
<text x="72" y="762" class="mono muted" font-size="10">WED</text>
<text x="72" y="786" class="mono muted" font-size="10">THU</text>
<text x="72" y="810" class="mono muted" font-size="10">FRI</text>
<text x="72" y="834" class="mono muted" font-size="10">SAT</text>
''')

    # Grid
    gx, gy = 120, 676
    cell, gap = 17, 4
    month_label_positions = {}

    for wi, week in enumerate(weeks):
        x = gx + wi * (cell + gap)

        # Month label at first day of month in a week.
        months_here = [d for d in week if d.month != (d - dt.timedelta(days=1)).month and d.year == today.year]
        if months_here:
            d = months_here[0]
            month_label_positions[wi] = d.strftime("%b").upper()

        for di, day in enumerate(week):
            y = gy + di * (cell + gap)

            if day.year != today.year or day > today:
                fill = "#08221f"
                opacity = ".35"
            else:
                item = day_map.get(day)
                level = item["contributionLevel"] if item else "NONE"
                fill = level_color.get(level, "#0b2927")
                opacity = "1"

            count = day_map.get(day, {}).get("contributionCount", 0)

            add(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" '
                f'fill="{fill}" opacity="{opacity}" class="pulse">'
                f'<title>{day.isoformat()} — {count} contribution{"s" if count != 1 else ""}</title>'
                f'</rect>'
            )

    for wi, label in month_label_positions.items():
        x = gx + wi * (cell + gap)
        add(f'<text x="{x}" y="670" class="mono muted" font-size="9">{label}</text>')

    # Legend
    ly = 880
    add('<text x="120" y="875" class="mono muted" font-size="9">LESS</text>')
    for i, level in enumerate(["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]):
        add(
            f'<rect x="{170+i*24}" y="{862}" width="16" height="16" rx="4" '
            f'fill="{level_color[level]}"/>'
        )
    add('<text x="302" y="875" class="mono muted" font-size="9">MORE</text>')

    # Contribution summary cards
    add(f'''
    <rect x="52" y="925" width="1076" height="225" rx="16" fill="#052623" stroke="#0a5b54"/>
    <text x="76" y="957" class="mono white" font-size="13" font-weight="700">
      CONTRIBUTION SIGNAL
    </text>

    {small_stat(76, 978, "ACTIVE DAYS", active_days, "#6ffff0")}
    {small_stat(330, 978, "CURRENT STREAK", current_streak, "#a990ff")}
    {small_stat(584, 978, "BEST STREAK", best_streak, "#61a1ff")}
    {small_stat(838, 978, "BEST DAY", best_day[1], "#ff9c2e")}

    <text x="76" y="1128" class="mono muted" font-size="9">
      Best day: {best_day[0].isoformat()} • {best_day[1]} contributions
    </text>
    <text x="838" y="1128" text-anchor="end" class="mono muted" font-size="9">
      Updated {today.isoformat()}
    </text>
    ''')

    # SIGNAL
    add('''
<text x="24" y="1245" class="sans" font-size="20" fill="#111b1b">Signal</text>

<rect x="24" y="1265" width="1132" height="240" rx="22" class="panel"/>
<text x="52" y="1302" class="mono white" font-size="16" font-weight="700">PROFILE SIGNAL</text>
<text x="52" y="1322" class="mono muted small">ACCOUNT HEALTH • PUBLIC ACTIVITY • COMMUNITY</text>
''')

    add(metric_signal(52, 1350, 250, "REPOS", user["public_repos"], "#6ffff0"))
    add(metric_signal(320, 1350, 250, "STARS", stars, "#a990ff"))
    add(metric_signal(588, 1350, 250, "FOLLOWERS", followers, "#61a1ff"))
    add(metric_signal(856, 1350, 250, "FOLLOWING", following, "#00d9c0"))

    # LANGUAGES
    add('''
<rect x="24" y="1535" width="1132" height="360" rx="22" class="panel"/>
<text x="52" y="1572" class="mono white" font-size="16" font-weight="700">LANGUAGE STACK</text>
<text x="52" y="1592" class="mono muted small">MEASURED FROM YOUR PUBLIC NON-FORK REPOSITORIES</text>
''')

    lang_colors = ["#ff7b00", "#ffe45c", "#65a2ff", "#ff5d58", "#b57dff"]

    if langs and total_lang:
        for i, (language, amount) in enumerate(langs):
            pct = amount / total_lang * 100
            y = 1635 + i * 47
            width = max(10, min(820, 820 * pct / 100))
            color = lang_colors[i]

            add(f'''
<text x="62" y="{y+11}" class="mono white" font-size="11">● {esc(language)}</text>
<text x="1090" y="{y+11}" text-anchor="end" class="mono muted" font-size="10">{pct:.1f}%</text>
<rect x="240" y="{y}" width="820" height="14" rx="7" fill="#123b38"/>
<rect x="240" y="{y}" width="{width:.1f}" height="14" rx="7" fill="{color}"/>
''')
    else:
        add('<text x="62" y="1650" class="mono muted" font-size="11">No language data returned.</text>')

    # PROFILE SCAN
    add(f'''
<text x="24" y="1940" class="sans" font-size="20" fill="#111b1b">Profile scan</text>

<rect x="24" y="1960" width="1132" height="635" rx="16" fill="#041d1b" stroke="#08776d" stroke-width="2"/>

<rect x="24" y="1960" width="1132" height="40" rx="16" fill="#061816"/>
<circle cx="48" cy="1980" r="6" fill="#ff5f56"/>
<circle cx="68" cy="1980" r="6" fill="#ffbd2e"/>
<circle cx="88" cy="1980" r="6" fill="#27c93f"/>

<text x="590" y="1985" text-anchor="middle" class="mono muted" font-size="9">
  PROFILE_SCAN // github.com/{esc(USERNAME)}
</text>

<rect x="45" y="2025" width="485" height="530" rx="10" fill="#062522" stroke="#0a5b54"/>
<rect x="550" y="2025" width="585" height="530" rx="10" fill="#062522" stroke="#0a5b54"/>

<text x="70" y="2060" class="mono cyan" font-size="11">IDENTITY</text>
<text x="70" y="2100" class="mono muted" font-size="11">NAME</text>
<text x="250" y="2100" class="mono white" font-size="11">{esc(name)}</text>

<text x="70" y="2135" class="mono muted" font-size="11">ROLE</text>
<text x="250" y="2135" class="mono white" font-size="11">AI Engineer</text>

<text x="70" y="2170" class="mono muted" font-size="11">LOCATION</text>
<text x="250" y="2170" class="mono white" font-size="11">{esc(location)}</text>

<text x="70" y="2205" class="mono muted" font-size="11">DOMAIN</text>
<text x="250" y="2205" class="mono white" font-size="11">Artificial Intelligence</text>

<text x="70" y="2240" class="mono muted" font-size="11">PUBLIC REPOS</text>
<text x="250" y="2240" class="mono cyan" font-size="11">{user["public_repos"]}</text>

<text x="70" y="2275" class="mono muted" font-size="11">FOLLOWERS</text>
<text x="250" y="2275" class="mono cyan" font-size="11">{followers}</text>

<text x="70" y="2310" class="mono muted" font-size="11">STARS</text>
<text x="250" y="2310" class="mono cyan" font-size="11">{stars}</text>

<text x="70" y="2345" class="mono muted" font-size="11">YEAR CONTRIBUTIONS</text>
<text x="250" y="2345" class="mono cyan" font-size="11">{total}</text>

<text x="70" y="2380" class="mono muted" font-size="11">ACTIVE DAYS</text>
<text x="250" y="2380" class="mono cyan" font-size="11">{active_days}</text>

<text x="70" y="2415" class="mono muted" font-size="11">CURRENT STREAK</text>
<text x="250" y="2415" class="mono cyan" font-size="11">{current_streak}</text>

<text x="70" y="2450" class="mono muted" font-size="11">BEST STREAK</text>
<text x="250" y="2450" class="mono cyan" font-size="11">{best_streak}</text>

<text x="575" y="2060" class="mono cyan" font-size="11">MISSION</text>

<text x="575" y="2100" class="mono white" font-size="12">
  Building production-oriented intelligent systems.
</text>
<text x="575" y="2130" class="mono muted" font-size="10">
  Focus: real-time AI, voice systems, LLM applications,
</text>
<text x="575" y="2150" class="mono muted" font-size="10">
  computer vision, automation and deployable ML.
</text>

<text x="575" y="2205" class="mono cyan" font-size="11">SIGNALS</text>

<text x="575" y="2245" class="mono muted" font-size="10">
  repositories
</text>
<text x="820" y="2245" class="mono white" font-size="10">{user["public_repos"]}</text>

<text x="575" y="2275" class="mono muted" font-size="10">
  contributions / year
</text>
<text x="820" y="2275" class="mono white" font-size="10">{total}</text>

<text x="575" y="2305" class="mono muted" font-size="10">
  active days
</text>
<text x="820" y="2305" class="mono white" font-size="10">{active_days}</text>

<text x="575" y="2335" class="mono muted" font-size="10">
  best day
</text>
<text x="820" y="2335" class="mono white" font-size="10">{best_day[1]}</text>

<text x="575" y="2365" class="mono muted" font-size="10">
  current streak
</text>
<text x="820" y="2365" class="mono white" font-size="10">{current_streak}</text>

<text x="575" y="2395" class="mono muted" font-size="10">
  best streak
</text>
<text x="820" y="2395" class="mono white" font-size="10">{best_streak}</text>

<text x="575" y="2425" class="mono muted" font-size="10">
  last updated
</text>
<text x="820" y="2425" class="mono white" font-size="10">{today.isoformat()}</text>

<text x="575" y="2480" class="mono cyan" font-size="11">TECHNICAL FOCUS</text>
<text x="575" y="2515" class="mono muted" font-size="10">
  Python • PyTorch • OpenCV • LLMs • RAG • Voice AI
</text>
<text x="575" y="2540" class="mono muted" font-size="10">
  STT • TTS • Computer Vision • Real-Time Inference
</text>

<text x="45" y="2580" class="mono muted" font-size="8">
  $ github-profile --scan --live-data
</text>
<text x="1135" y="2580" text-anchor="end" class="mono cyan" font-size="8">
  ONLINE
</text>

</svg>
''')

    return "".join(parts)


def metric_card(x, y, w, h, title, value, sub, color):
    return f'''
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" class="card"/>
<text x="{x+20}" y="{y+27}" class="mono muted" font-size="9">{esc(title)}</text>
<text x="{x+20}" y="{y+63}" class="mono" font-size="29" font-weight="700" fill="{color}">{value}</text>
<text x="{x+110}" y="{y+61}" class="mono muted" font-size="8">{esc(sub)}</text>
'''


def small_stat(x, y, label, value, color):
    return f'''
<rect x="{x}" y="{y}" width="220" height="105" rx="12" class="card"/>
<text x="{x+18}" y="{y+28}" class="mono muted" font-size="9">{label}</text>
<text x="{x+18}" y="{y+70}" class="mono" font-size="27" font-weight="700" fill="{color}">{value}</text>
'''


def metric_signal(x, y, w, title, value, color):
    return f'''
<rect x="{x}" y="{y}" width="{w}" height="125" rx="14" class="card"/>
<text x="{x+18}" y="{y+28}" class="mono muted" font-size="9">{title}</text>
<text x="{x+18}" y="{y+76}" class="mono" font-size="32" font-weight="700" fill="{color}">{value}</text>
<rect x="{x+18}" y="{y+98}" width="{w-36}" height="7" rx="4" fill="#123b38"/>
<rect x="{x+18}" y="{y+98}" width="{max(12, min(w-36, 20 + len(str(value))*8))}" height="7" rx="4" fill="{color}"/>
'''


if __name__ == "__main__":
    OUT.write_text(svg(), encoding="utf-8")
    print(f"Wrote {OUT.resolve()}")
