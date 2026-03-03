"""
probe_statview.py — Inspect modulekit/statviewtype for TOI data.
Run: python pwhl/probe_statview.py
"""

import requests, json

API_BASE    = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY     = "446521baf8c38984"
CLIENT_CODE = "pwhl"
SEASON_ID   = 8  # current season

def api_get(params):
    params.update({"key": API_KEY, "client_code": CLIENT_CODE, "fmt": "json"})
    r = requests.get(API_BASE, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# Fetch all teams' skater stats for season 8
# Try without team_id first to get all players
print("=== All skaters, season 8, no team filter ===")
try:
    data = api_get({
        "feed": "modulekit", "view": "statviewtype",
        "type": "skaters", "season_id": SEASON_ID,
        "league_id": 1
    })
    raw  = json.dumps(data)
    toi_keys = [k for k in ["toi", "ice_time", "icetime", "time_on_ice",
                             "ice_time_per_game", "ice_time_per_game_avg",
                             "avg", "average"]
                if k.lower() in raw.lower()]
    print(f"TOI-related keys in response: {toi_keys}")

    # Navigate to first player
    sk = data.get("SiteKit", {})
    print(f"SiteKit keys: {list(sk.keys())}")

    players = None
    for k in sk:
        if isinstance(sk[k], list) and len(sk[k]) > 0:
            players = sk[k]
            print(f"\nPlayer list at SiteKit.{k} ({len(players)} players)")
            break

    if players:
        print(f"\nAll fields on first player:")
        print(json.dumps(players[0], indent=2))

except Exception as e:
    print(f"ERROR: {e}")

# Also try per-team for all 6 teams
print("\n\n=== Per-team, all teams, season 8 ===")
for team_id in range(1, 9):
    try:
        data = api_get({
            "feed": "modulekit", "view": "statviewtype",
            "type": "skaters", "season_id": SEASON_ID,
            "league_id": 1, "team_id": team_id
        })
        raw = json.dumps(data)
        if "ice_time" in raw.lower() or "toi" in raw.lower():
            print(f"  Team {team_id}: ✅ TOI found")
            sk = data.get("SiteKit", {})
            for k in sk:
                if isinstance(sk[k], list) and len(sk[k]) > 0:
                    p = sk[k][0]
                    toi_fields = {key: val for key, val in p.items()
                                  if "ice" in key.lower() or "toi" in key.lower()
                                  or "time" in key.lower() or "avg" in key.lower()}
                    print(f"    TOI fields: {toi_fields}")
                    break
        else:
            print(f"  Team {team_id}: — no TOI")
    except Exception as e:
        print(f"  Team {team_id}: ERROR {e}")

print("\nDone.")