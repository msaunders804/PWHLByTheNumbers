"""
empty_net_analysis.py — Empty net goalie pull analysis for PWHL Season 8.

Pulls play-by-play data directly from the HockeyTech API for every
Season 8 game, extracts empty net events and goalie pull timing,
and generates four TikTok-format (1080x1920) slides via the HTML renderer.

Outputs (in render/output/):
    en_slide0_overall.png
    en_slide1_scored.png
    en_slide2_allowed.png
    en_slide3_timing.png

Run from: src/pwhl_btn/
    python visualizations/empty_net_analysis.py
"""

import json
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── API config ────────────────────────────────────────────────────────────────
BASE_URL    = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY     = "446521baf8c38984"
CLIENT_CODE = "pwhl"
SEASON_ID   = 8


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        raw = r.read().decode("utf-8").strip()
        if raw.startswith("(") and raw.endswith(")"):
            raw = raw[1:-1]
        return json.loads(raw)



def get_season_game_ids(season_id):
    from datetime import datetime as _dt
    url = (f"{BASE_URL}?feed=modulekit&view=schedule&season_id={season_id}"
           f"&key={API_KEY}&client_code={CLIENT_CODE}&fmt=json")
    data = api_get(url)
    schedule = data.get("SiteKit", {}).get("Schedule", [])
    game_ids  = []
    game_dates = {}   # {game_id: "M/D"}
    for g in schedule:
        is_final = (
            str(g.get("final", "0")) == "1"
            or "final" in str(g.get("game_status", "")).lower()
        )
        if not is_final:
            continue
        gid = g.get("id") or g.get("game_id")
        if not gid:
            continue
        gid = int(gid)
        game_ids.append(gid)
        raw_date = str(g.get("date_played", "")).strip()
        try:
            game_dates[gid] = f"{_dt.strptime(raw_date, '%Y-%m-%d').month}/{_dt.strptime(raw_date, '%Y-%m-%d').day}"
        except (ValueError, TypeError):
            game_dates[gid] = ""
    return game_ids, game_dates


def get_game_summary(game_id):
    url = (f"{BASE_URL}?feed=statviewfeed&view=gameSummary&game_id={game_id}"
           f"&key={API_KEY}&client_code={CLIENT_CODE}&lang=en&league_id=1&fmt=json")
    try:
        return api_get(url)
    except Exception as e:
        print(f"    game {game_id}: error - {e}")
        return None


def parse_time(t):
    try:
        m, s = t.strip().split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


# ── Data analysis ─────────────────────────────────────────────────────────────


def analyze_games(game_ids, game_dates=None):
    team_names        = {}
    en_scored         = defaultdict(int)
    en_allowed        = defaultdict(int)
    pull_times        = []
    pull_scored       = 0   # pulling team scored at least once during the pull window
    pull_no_score     = 0   # pulling team did not score during the pull window
    pull_scored_events = []  # per-event detail records for the list slide

    total = len(game_ids)
    for i, gid in enumerate(game_ids, 1):
        print(f"  [{i}/{total}] game {gid}...")
        data = get_game_summary(gid)
        if not data:
            continue

        home    = data.get("homeTeam",     {})
        away    = data.get("visitingTeam", {})
        periods = data.get("periods",      [])

        home_id   = home.get("info", {}).get("id")
        away_id   = away.get("info", {}).get("id")
        home_abbr = home.get("info", {}).get("abbreviation", "UNK")
        away_abbr = away.get("info", {}).get("abbreviation", "UNK")
        team_names[home_abbr] = home.get("info", {}).get("name", home_abbr)
        team_names[away_abbr] = away.get("info", {}).get("name", away_abbr)

        game_date = (game_dates or {}).get(gid, "")

        # Final score — sum goals across all periods per team
        home_score = sum(
            1 for p in periods for g in p.get("goals", [])
            if g.get("team", {}).get("id") == home_id
        )
        away_score = sum(
            1 for p in periods for g in p.get("goals", [])
            if g.get("team", {}).get("id") == away_id
        )

        # Build 3rd-period goal timeline: {team_id: [time_in_seconds, ...]}
        # Used to check whether the pulling team scored during a pull window.
        third_goals = defaultdict(list)
        for period in periods:
            per_id = str(
                period.get("info", {}).get("id")
                or period.get("id")
                or period.get("number")
                or ""
            )
            if per_id != "3":
                continue
            for goal in period.get("goals", []):
                scoring_id = goal.get("team", {}).get("id")
                # Try multiple field paths — HockeyTech uses "time" but some
                # responses nest it or use alternate names.
                raw_time = (
                    goal.get("time")
                    or goal.get("period_time")
                    or goal.get("goalTime")
                    or "0:00"
                )
                if isinstance(raw_time, dict):
                    raw_time = raw_time.get("formatted", "0:00")
                goal_time = parse_time(str(raw_time))
                if scoring_id is not None:
                    third_goals[scoring_id].append(goal_time)

        # Empty net goals (all periods)
        for period in periods:
            for goal in period.get("goals", []):
                props = goal.get("properties", {})
                if str(props.get("isEmptyNet", "0")) != "1":
                    continue
                scoring_id = goal.get("team", {}).get("id")
                if scoring_id == home_id:
                    en_scored[home_abbr]  += 1
                    en_allowed[away_abbr] += 1
                elif scoring_id == away_id:
                    en_scored[away_abbr]  += 1
                    en_allowed[home_abbr] += 1

        # Goalie pull timing and success in 3rd period.
        # Iterate every log entry (not len-1) so we catch pulls at the end of
        # the game where there is no subsequent entry for the same goalie.
        # We also no longer skip cross-period gaps: a goalie pulled in the 3rd
        # who doesn't return until OT (or at all) is a valid pull.
        for side, team_id in [(home, home_id), (away, away_id)]:
            log = side.get("goalieLog", [])
            for j in range(len(log)):
                curr    = log[j]
                end_per = curr.get("periodEnd", {}).get("id", "0")

                # Only care about shifts that ended during the 3rd period.
                if not (end_per.isdigit() and int(end_per) == 3):
                    continue

                end_t = parse_time(curr.get("timeEnd", "0:00"))

                # Determine the end of the pull window.
                # If the next entry is also in the 3rd, use its start time.
                # Otherwise (cross-period or last entry) treat the pull as
                # lasting until the end of the period.
                pull_end_t = 1200  # end of regulation 3rd period
                if j + 1 < len(log):
                    nxt     = log[j + 1]
                    beg_per = nxt.get("periodStart", {}).get("id", "0")
                    if beg_per == "3":
                        beg_t = parse_time(nxt.get("timeStart", "0:00"))
                        gap   = beg_t - end_t
                        if gap < 5:  # noise — not a real pull
                            continue
                        pull_end_t = beg_t

                pull_times.append(1200 - end_t)

                # How many goals did the pulling team score during [end_t, pull_end_t]?
                goals_in_window = [
                    gt for gt in third_goals.get(team_id, [])
                    if end_t <= gt <= pull_end_t
                ]
                if goals_in_window:
                    pull_scored += 1
                    is_home = (team_id == home_id)
                    score = f"{home_score}-{away_score}"
                    pulling_score   = home_score if is_home else away_score
                    opposing_score  = away_score if is_home else home_score
                    result = "W" if pulling_score > opposing_score else "L"
                    for _ in goals_in_window:
                        pull_scored_events.append({
                            "team":     home_abbr if is_home else away_abbr,
                            "opponent": away_abbr if is_home else home_abbr,
                            "home":     is_home,
                            "date":     game_date,
                            "score":    score,
                            "result":   result,
                            "game_id":  gid,
                        })
                else:
                    pull_no_score += 1

        time.sleep(0.15)

    return {
        "team_names":         team_names,
        "en_scored":          dict(en_scored),
        "en_allowed":         dict(en_allowed),
        "pull_times":         pull_times,
        "pull_scored":        pull_scored,
        "pull_no_score":      pull_no_score,
        "pull_scored_events": pull_scored_events,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    from pwhl_btn.render.empty_net_render import render_all

    print(f"\n-- Empty Net Analysis -- Season {SEASON_ID} ---------------------")

    print("  Fetching season game list...")
    game_ids, game_dates = get_season_game_ids(SEASON_ID)

    if not game_ids:
        print("  ERROR: Could not retrieve game list.")
        return

    print(f"  Found {len(game_ids)} completed games")
    results = analyze_games(game_ids, game_dates)

    print(f"\n  -- Results --")
    print(f"  EN goals scored:  {results['en_scored']}")
    print(f"  EN goals allowed: {results['en_allowed']}")
    n_pulls = len(results["pull_times"])
    if n_pulls:
        avg = np.mean(results["pull_times"])
        print(f"  Pull times (n={n_pulls}): avg {avg:.0f}s remaining")
    else:
        print("  No pull times detected")

    render_all(results, out_dir=OUTPUT_DIR)

    print("\n  Done.")


if __name__ == "__main__":
    main()