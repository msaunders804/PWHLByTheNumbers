#!/usr/bin/env python3
"""
Fetch Career Statistics Directly from PWHL API
Uses the same API that powers the official PWHL stats page
"""

import requests
import json
from collections import defaultdict


def fetch_season_stats(stat_type='skater', limit=100, season_id=8):
    """
    Fetch season statistics from PWHL API

    Args:
        stat_type: 'skater' or 'goalie'
        limit: Number of players to return
        season_id: Season ID (1-8)

    Returns:
        List of player stat dicts
    """
    # PWHL Stats API endpoint (same as website uses)
    url = "https://lscluster.hockeytech.com/feed/index.php"

    params = {
        'feed': 'modulekit',
        'view': 'statviewtype',
        'type': 'topscorers' if stat_type == 'skater' else 'topgoalies',
        'key': '446521baf8c38984',
        'client_code': 'pwhl',
        'lang': 'en',
        'league_code': '',
        'season_id': season_id,
        'first': 0,
        'limit': limit,
        'sort': 'points' if stat_type == 'skater' else 'saves',
        'stat': 'all',
        'order_direction': 'DESC'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        # Remove JavaScript wrapper if present
        text = response.text
        if text.startswith('angular.callbacks'):
            text = text[text.find('(')+1:text.rfind(')')]

        data = json.loads(text)

        # Extract player stats
        if 'SiteKit' in data and 'Statviewtype' in data['SiteKit']:
            return data['SiteKit']['Statviewtype']
        else:
            return []

    except Exception as e:
        print(f"Error fetching stats: {e}")
        return []


def fetch_career_stats(stat_type='skater', limit=100):
    """
    Aggregate career stats across all PWHL seasons

    Args:
        stat_type: 'skater' or 'goalie'
        limit: Number of top players to return

    Returns:
        List of player career stat dicts sorted by points/saves
    """
    # Regular seasons to aggregate: 1, 5, 8 (main seasons)
    seasons = [1, 5, 8]

    # Aggregate stats by player ID
    player_stats = defaultdict(lambda: {
        'games_played': 0,
        'goals': 0,
        'assists': 0,
        'points': 0,
        'plus_minus': 0,
        'penalties_in_minutes': 0,
        'shots_against': 0,
        'saves': 0,
        'wins': 0,
        'goals_against': 0
    })

    player_info = {}  # Store name and team

    print(f"Fetching stats from seasons: {seasons}...")

    for season in seasons:
        season_data = fetch_season_stats(stat_type, limit=500, season_id=season)

        for player in season_data:
            player_id = player.get('id') or player.get('player_id')
            if not player_id:
                continue

            # Store player info (use most recent)
            player_info[player_id] = {
                'name': player.get('name', ''),
                'first_name': player.get('first_name', ''),
                'last_name': player.get('last_name', ''),
                'team_code': player.get('team_code', '')
            }

            # Aggregate stats
            stats = player_stats[player_id]
            stats['games_played'] += int(player.get('games_played', 0))
            stats['goals'] += int(player.get('goals', 0))
            stats['assists'] += int(player.get('assists', 0))
            stats['points'] += int(player.get('points', 0))
            stats['plus_minus'] += int(player.get('plus_minus', 0))
            stats['penalties_in_minutes'] += int(player.get('penalties_in_minutes', 0))
            stats['shots_against'] += int(player.get('shots_against', 0))
            stats['saves'] += int(player.get('saves', 0))
            stats['wins'] += int(player.get('wins', 0))
            stats['goals_against'] += int(player.get('goals_against', 0))

    # Combine player info with stats
    career_stats = []
    for player_id, stats in player_stats.items():
        info = player_info.get(player_id, {})
        combined = {**info, **stats}
        combined['id'] = player_id
        career_stats.append(combined)

    # Sort by points (skaters) or saves (goalies)
    sort_key = 'points' if stat_type == 'skater' else 'saves'
    career_stats.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

    return career_stats[:limit]


def print_career_leaders(stat_type='skater', limit=10, season_id='all'):
    """Print career leaders from API"""
    if season_id == 'all':
        stats = fetch_career_stats(stat_type, limit)
    else:
        stats = fetch_season_stats(stat_type, limit, int(season_id))

    if not stats:
        print("No stats found")
        return

    season_text = f"Season {season_id}" if season_id != 'all' else "Career"

    if stat_type == 'skater':
        print(f"\n{season_text} Leaders - POINTS (from PWHL API)")
        print("=" * 100)
        print(f"{'RK':<4} {'PLAYER':<30} {'TEAM':<6} {'GP':<5} {'G':<5} {'A':<5} {'PTS':<5} {'+/-':<6} {'PIM':<5}")
        print("-" * 100)

        for idx, player in enumerate(stats, 1):
            # Use correct field names from API
            name = player.get('name', f"{player.get('first_name', '')} {player.get('last_name', '')}")
            team = player.get('team_code', 'N/A')
            gp = int(player.get('games_played', 0))
            goals = int(player.get('goals', 0))
            assists = int(player.get('assists', 0))
            points = int(player.get('points', 0))
            plus_minus = int(player.get('plus_minus', 0))
            pim = int(player.get('penalties_in_minutes', 0))

            print(f"{idx:<4} {name:<30} {team:<6} {gp:<5} {goals:<5} {assists:<5} {points:<5} "
                  f"{plus_minus:<6} {pim:<5}")

    else:  # goalie
        print(f"\n{season_text} Goalie Leaders - SAVE PERCENTAGE (from PWHL API)")
        print("=" * 100)
        print(f"{'RK':<4} {'GOALIE':<30} {'TEAM':<6} {'GP':<5} {'W':<5} {'SA':<6} {'SV':<6} {'SV%':<7} {'GAA':<6}")
        print("-" * 100)

        for idx, goalie in enumerate(stats, 1):
            # Use correct field names from API
            name = goalie.get('name', f"{goalie.get('first_name', '')} {goalie.get('last_name', '')}")
            team = goalie.get('team_code', 'N/A')
            gp = int(goalie.get('games_played', 0))
            wins = int(goalie.get('wins', 0))
            sa = int(goalie.get('shots_against', 0))
            sv = int(goalie.get('saves', 0))
            svpct = float(goalie.get('save_percentage', 0))
            gaa = float(goalie.get('goals_against_average', 0))

            print(f"{idx:<4} {name:<30} {team:<6} {gp:<5} {wins:<5} {sa:<6} {sv:<6} "
                  f"{svpct:<7.3f} {gaa:<6.2f}")

    print("-" * 100)


def save_stats_to_file(stat_type='skater', season_id='all', filename=None):
    """Save stats to JSON file"""
    stats = fetch_career_stats(stat_type, limit=1000, season_id=season_id)

    if not filename:
        filename = f"pwhl_{stat_type}_stats_{season_id}.json"

    with open(filename, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"✅ Saved {len(stats)} {stat_type} stats to {filename}")
    return filename


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("PWHL CAREER STATISTICS (Official API)")
    print("=" * 60)

    # Parse command line args
    stat_type = 'skater'
    season_id = 'all'
    limit = 10

    if len(sys.argv) > 1:
        if sys.argv[1] in ['skater', 'goalie']:
            stat_type = sys.argv[1]

    if len(sys.argv) > 2:
        season_id = sys.argv[2]

    if len(sys.argv) > 3:
        limit = int(sys.argv[3])

    # Show stats
    print_career_leaders(stat_type, limit, season_id)

    # Also show current season
    if season_id == 'all':
        print_career_leaders(stat_type, limit, season_id='8')

    print("\n💾 Save to file:")
    print(f"  python fetch_career_stats.py {stat_type} all")
    print(f"  This will create: pwhl_{stat_type}_stats_all.json")
