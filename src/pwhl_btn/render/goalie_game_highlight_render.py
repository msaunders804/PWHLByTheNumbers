"""
goalie_game_highlight_render.py — Render a single-game highlight graphic for a goalie.

Usage:
    python -m pwhl_btn.render.goalie_game_highlight_render --player 222 --date 2026-04-11
    python -m pwhl_btn.render.goalie_game_highlight_render --player 222 --date 2026-04-11 --dry-run
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from sqlalchemy import text

from pwhl_btn.analytics.gsaa import get_league_avg_sv_pct, get_season_gsaa, SEASON_ID
from pwhl_btn.db.db_config import get_engine

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"


def _fmt_pct(v) -> str:
    return f".{int(round(float(v or 0), 3) * 1000):03d}"


def _fmt_gsaa(v) -> str:
    return f"{float(v):+.2f}"


def _fmt_minutes(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def get_game_highlight_data(player_id: int, game_date: date, season_id: int = SEASON_ID) -> dict:
    """
    Pull all data needed to render the highlight graphic for a goalie's game on a given date.
    """
    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        league_sv = get_league_avg_sv_pct(conn, season_id)

        row = conn.execute(text("""
            SELECT
                p.first_name, p.last_name,
                t.team_code                                            AS team_code,
                opp.team_code                                          AS opponent,
                g.date,
                g.home_score, g.away_score,
                g.result_type,
                g.home_score_p1, g.home_score_p2, g.home_score_p3,
                g.away_score_p1, g.away_score_p2, g.away_score_p3,
                CASE WHEN s.team_id = g.home_team_id THEN 'Home' ELSE 'Away' END AS home_away,
                s.shots_against, s.saves, s.goals_against,
                s.minutes_played, s.decision,
                ROUND(s.saves / NULLIF(s.shots_against, 0), 4)        AS game_sv_pct
            FROM goalie_game_stats s
            JOIN games   g   ON g.game_id   = s.game_id
            JOIN players p   ON p.player_id = s.player_id
            JOIN teams   t   ON t.team_id   = s.team_id AND t.season_id = g.season_id
            JOIN teams   opp ON opp.team_id = CASE
                                    WHEN s.team_id = g.home_team_id
                                    THEN g.away_team_id
                                    ELSE g.home_team_id END
                             AND opp.season_id = g.season_id
            WHERE s.player_id   = :pid
              AND g.season_id   = :sid
              AND g.game_status = 'final'
              AND g.date        = :gdate
        """), {"pid": player_id, "sid": season_id, "gdate": str(game_date)}).mappings().fetchone()

        if not row:
            raise ValueError(f"No game found for player_id={player_id} on {game_date}")

        # League average shots against per game (for context line)
        avg_sa_row = conn.execute(text("""
            SELECT ROUND(AVG(s.shots_against), 1) AS avg_sa
            FROM goalie_game_stats s
            JOIN games g ON g.game_id = s.game_id
            WHERE g.season_id = :sid AND g.game_status = 'final'
              AND s.minutes_played >= 55
        """), {"sid": season_id}).fetchone()

    # Season totals for this goalie
    leaderboard  = get_season_gsaa(season_id)
    season_row   = next((g for g in leaderboard if g["player_id"] == player_id), None)

    sa          = float(row["shots_against"] or 0)
    sv          = float(row["saves"] or 0)
    gsaa        = round(sv - (sa * league_sv), 2)
    sv_pct_raw  = float(row["game_sv_pct"] or 0)

    is_home     = row["home_away"] == "Home"
    our_score   = row["home_score"] if is_home else row["away_score"]
    opp_score   = row["away_score"] if is_home else row["home_score"]
    our_p1      = row["home_score_p1"] if is_home else row["away_score_p1"]
    our_p2      = row["home_score_p2"] if is_home else row["away_score_p2"]
    our_p3      = row["home_score_p3"] if is_home else row["away_score_p3"]
    opp_p1      = row["away_score_p1"] if is_home else row["home_score_p1"]
    opp_p2      = row["away_score_p2"] if is_home else row["home_score_p2"]
    opp_p3      = row["away_score_p3"] if is_home else row["home_score_p3"]

    # OT goals (total - regulation)
    our_ot = max(0, (our_score or 0) - ((our_p1 or 0) + (our_p2 or 0) + (our_p3 or 0)))
    opp_ot = max(0, (opp_score or 0) - ((opp_p1 or 0) + (opp_p2 or 0) + (opp_p3 or 0)))

    league_avg_sa = float(avg_sa_row.avg_sa or 0) if avg_sa_row else 0.0

    d = row["date"]
    date_str = d.strftime("%B {day}, %Y").replace("{day}", str(d.day)) if hasattr(d, "strftime") else str(d)

    # Context line
    result_word = "win" if row["decision"] == "W" else "loss"
    shot_diff   = sa - league_avg_sa
    shot_note   = (f"{abs(shot_diff):.0f} {'more' if shot_diff > 0 else 'fewer'} shots than league average"
                   if abs(shot_diff) >= 1 else "exactly average shot volume")
    context_line = (
        f"Phillips faced {int(sa)} shots ({shot_note}) in a {our_score}–{opp_score} "
        f"{result_word} vs {row['opponent']}. "
        f"Her GSAA of {_fmt_gsaa(gsaa)} puts her {'above' if gsaa >= 0 else 'below'} "
        f"an average goalie in the same situation."
    )

    return {
        "player_name":      f"{row['first_name']} {row['last_name']}",
        "team_code":        row["team_code"],
        "opponent":         row["opponent"],
        "game_date":        date_str,
        "home_away":        row["home_away"],
        "our_score":        our_score or 0,
        "opp_score":        opp_score or 0,
        "result_type":      row["result_type"] if row["result_type"] != "REG" else None,
        "our_p1": our_p1 or 0, "our_p2": our_p2 or 0, "our_p3": our_p3 or 0, "our_ot": our_ot,
        "opp_p1": opp_p1 or 0, "opp_p2": opp_p2 or 0, "opp_p3": opp_p3 or 0, "opp_ot": opp_ot,
        "shots_against":    int(sa),
        "saves":            int(sv),
        "goals_against":    int(row["goals_against"] or 0),
        "minutes_fmt":      _fmt_minutes(int(row["minutes_played"] or 0)),
        "decision":         row["decision"] or "—",
        "sv_pct":           _fmt_pct(sv_pct_raw),
        "sv_pct_raw":       sv_pct_raw,
        "gsaa":             _fmt_gsaa(gsaa),
        "league_sv_pct":    league_sv,
        "league_sv_pct_fmt": _fmt_pct(league_sv),
        "league_avg_sa":    f"{league_avg_sa:.1f}",
        "season_sv_pct":    _fmt_pct(season_row["sv_pct"]) if season_row else "—",
        "season_gsaa":      _fmt_gsaa(float(season_row["gsaa"])) if season_row else "—",
        "season_gsaa_raw":  float(season_row["gsaa"]) if season_row else 0.0,
        "context_line":     context_line,
    }


def render_game_highlight(
    player_id: int,
    game_date: date,
    out_dir: Path | None = None,
    season_id: int = SEASON_ID,
) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n── Game Highlight · player_id={player_id} · {game_date} ──────────")
    data = get_game_highlight_data(player_id, game_date, season_id)
    print(f"  {data['player_name']} ({data['team_code']}) vs {data['opponent']} — {data['decision']}")

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("goalie_game_highlight.html")
    html = tmpl.render(**data)

    code      = data["team_code"].upper()
    date_slug = str(game_date).replace("-", "")
    html_path = out_dir / f"_render_highlight_{code}_{date_slug}.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / f"highlight_{code}_{date_slug}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  ✅ {out_path.name}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Render goalie game highlight graphic")
    parser.add_argument("--player", type=int, required=True, help="player_id")
    parser.add_argument("--date",   type=str, required=True, help="Game date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Print data without rendering")
    args = parser.parse_args()

    game_date = date.fromisoformat(args.date)
    data = get_game_highlight_data(args.player, game_date)

    if args.dry_run:
        import pprint
        pprint.pprint(data)
        return

    render_game_highlight(args.player, game_date)


if __name__ == "__main__":
    main()
