"""
run_playoff_matchup.py — Builds playoff carousel slides for both matchups.
  - MTL vs MIN (slides 01-05): cover, season series, game log, scorers, goaltending
  - OTT vs BOS (slides 01-05): same format
  - Historical (1 slide): past PWHL 1st-seed upsets
Usage: python -m pwhl_btn.jobs.run_playoff_matchup
"""
from __future__ import annotations

import datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.db.db_queries import _logo_uri, _file_to_data_uri, PLAYERS_DIR
from pwhl_btn.render.playoff_matchup_render import (
    render_cover, render_cover_ott,
    render_series, render_games, render_scorers, render_goalie,
    render_mm_stats, render_historical,
)

SEASON_ID  = 8
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

engine = get_engine()


# ── Raw DB helpers ─────────────────────────────────────────────────────────────

def _h2h_games(session, team_a: str, team_b: str) -> list[dict]:
    rows = session.execute(text("""
        SELECT g.game_id, g.date, g.home_score, g.away_score, g.result_type,
               ht.team_code AS home_code, at.team_code AS away_code,
               g.home_score_p1, g.home_score_p2, g.home_score_p3,
               g.away_score_p1, g.away_score_p2, g.away_score_p3
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
        JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
        WHERE g.season_id = :sid AND g.game_status = 'final'
          AND ((ht.team_code = :ta AND at.team_code = :tb)
            OR (ht.team_code = :tb AND at.team_code = :ta))
        ORDER BY g.date ASC
    """), {"sid": SEASON_ID, "ta": team_a, "tb": team_b}).fetchall()
    return [dict(r._mapping) for r in rows]


def _h2h_skaters(session, team_a: str, team_b: str) -> list[dict]:
    rows = session.execute(text("""
        SELECT p.first_name, p.last_name, t.team_code,
               COUNT(DISTINCT pgs.game_id) AS gp,
               SUM(pgs.goals) AS g, SUM(pgs.assists) AS a,
               SUM(pgs.goals + pgs.assists) AS pts
        FROM player_game_stats pgs
        JOIN games gm ON gm.game_id = pgs.game_id
        JOIN players p  ON p.player_id = pgs.player_id
        JOIN teams t    ON t.team_id = pgs.team_id AND t.season_id = :sid
        JOIN teams ht   ON ht.team_id = gm.home_team_id AND ht.season_id = :sid
        JOIN teams at   ON at.team_id = gm.away_team_id AND at.season_id = :sid
        WHERE gm.season_id = :sid AND gm.game_status = 'final'
          AND t.team_code IN (:ta, :tb)
          AND ((ht.team_code = :ta AND at.team_code = :tb)
            OR (ht.team_code = :tb AND at.team_code = :ta))
        GROUP BY p.player_id, p.first_name, p.last_name, t.team_code
        ORDER BY pts DESC, g DESC
    """), {"sid": SEASON_ID, "ta": team_a, "tb": team_b}).fetchall()
    return [dict(r._mapping) for r in rows]


def _goalie_vs(session, goalie_last: str, goalie_team: str, opp: str) -> dict:
    row = session.execute(text("""
        SELECT COUNT(DISTINCT ggs.game_id) AS gp,
               SUM(ggs.saves) AS sv, SUM(ggs.shots_against) AS sa,
               SUM(ggs.goals_against) AS ga,
               ROUND(SUM(ggs.saves) / NULLIF(SUM(ggs.shots_against),0), 3) AS sv_pct
        FROM goalie_game_stats ggs
        JOIN games gm ON gm.game_id = ggs.game_id
        JOIN players p  ON p.player_id = ggs.player_id
        JOIN teams t    ON t.team_id = ggs.team_id AND t.season_id = :sid
        JOIN teams ht   ON ht.team_id = gm.home_team_id AND ht.season_id = :sid
        JOIN teams at   ON at.team_id = gm.away_team_id AND at.season_id = :sid
        WHERE gm.season_id = :sid AND gm.game_status = 'final'
          AND t.team_code = :gteam
          AND LOWER(p.last_name) LIKE :lname
          AND ((ht.team_code = :gteam AND at.team_code = :opp)
            OR (ht.team_code = :opp AND at.team_code = :gteam))
    """), {"sid": SEASON_ID, "gteam": goalie_team, "lname": f"%{goalie_last.lower()}%",
           "opp": opp}).fetchone()
    return dict(row._mapping) if row else {}


def _goalie_season(session, goalie_last: str, goalie_team: str) -> dict:
    row = session.execute(text("""
        SELECT COUNT(DISTINCT ggs.game_id) AS gp,
               SUM(ggs.saves) AS sv, SUM(ggs.shots_against) AS sa,
               SUM(ggs.goals_against) AS ga,
               ROUND(SUM(ggs.saves) / NULLIF(SUM(ggs.shots_against),0), 3) AS sv_pct
        FROM goalie_game_stats ggs
        JOIN games gm ON gm.game_id = ggs.game_id
        JOIN players p  ON p.player_id = ggs.player_id
        JOIN teams t    ON t.team_id = ggs.team_id AND t.season_id = :sid
        WHERE gm.season_id = :sid AND gm.game_status = 'final'
          AND t.team_code = :gteam
          AND LOWER(p.last_name) LIKE :lname
    """), {"sid": SEASON_ID, "gteam": goalie_team,
           "lname": f"%{goalie_last.lower()}%"}).fetchone()
    return dict(row._mapping) if row else {}


# ── Data builders ──────────────────────────────────────────────────────────────

def _gf_ga(games: list[dict], team: str) -> tuple[int, int]:
    gf = sum(g["home_score"] if g["home_code"] == team else g["away_score"] for g in games)
    ga = sum(g["away_score"] if g["home_code"] == team else g["home_score"] for g in games)
    return gf, ga


def _period_data(games: list[dict], team: str) -> list[dict]:
    periods = []
    for label, hk, ak in [("P1", "home_score_p1", "away_score_p1"),
                           ("P2", "home_score_p2", "away_score_p2"),
                           ("P3", "home_score_p3", "away_score_p3")]:
        gf = sum((g[hk] or 0) if g["home_code"] == team else (g[ak] or 0) for g in games)
        ga = sum((g[ak] or 0) if g["home_code"] == team else (g[hk] or 0) for g in games)
        periods.append({"label": label, "gf": gf, "ga": ga, "gd": gf - ga,
                        "gd_str": f"{gf-ga:+d}"})
    return periods


def _fmt_svp(val) -> str:
    if val is None:
        return "&#x2014;"
    f = float(val)
    return f".{round(f * 1000):03d}"


def _game_display(g: dict, team_a: str, team_b: str, logos: dict) -> dict:
    d = g["date"]
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    team_a_won = (g["home_code"] == team_a and g["home_score"] > g["away_score"]) or \
                 (g["away_code"] == team_a and g["away_score"] > g["home_score"])
    return {
        "date_short":  d.strftime("%b %d").upper().lstrip("0"),
        "year":        str(d.year),
        "home_code":   g["home_code"],
        "away_code":   g["away_code"],
        "home_logo":   logos[g["home_code"]],
        "away_logo":   logos[g["away_code"]],
        "home_score":  g["home_score"],
        "away_score":  g["away_score"],
        "result_type": g["result_type"] or "REG",
        "team_a_won":  team_a_won,
        "a_label":     team_a,
        "b_label":     team_b,
    }


def _wins(games: list[dict], team: str) -> int:
    return sum(1 for g in games
               if (g["home_code"] == team and g["home_score"] > g["away_score"])
               or (g["away_code"] == team and g["away_score"] > g["home_score"]))


# ── Render helpers ─────────────────────────────────────────────────────────────

def _render_matchup(team_a: str, team_b: str, team_a_full: str, team_b_full: str,
                    logo_a: str, logo_b: str, slug_prefix: str, out_dir: Path,
                    games: list[dict], skaters: list[dict],
                    goalie_ctx_a: dict, cover_fn):

    wins_a = _wins(games, team_a)
    wins_b = len(games) - wins_a
    gf, ga = _gf_ga(games, team_a)
    periods = _period_data(games, team_a)
    logos = {team_a: logo_a, team_b: logo_b}

    a_scorers = [{"name": f"{s['first_name']} {s['last_name']}", "gp": s["gp"],
                  "g": int(s["g"]), "a": int(s["a"]), "pts": int(s["pts"])}
                 for s in skaters if s["team_code"] == team_a][:5]
    b_scorers = [{"name": f"{s['first_name']} {s['last_name']}", "gp": s["gp"],
                  "g": int(s["g"]), "a": int(s["a"]), "pts": int(s["pts"])}
                 for s in skaters if s["team_code"] == team_b][:3]

    game_displays = [_game_display(g, team_a, team_b, logos) for g in games]

    print(f"  Rendering {slug_prefix} — cover")
    cover_fn(out_dir)

    print(f"  Rendering {slug_prefix} — season series")
    render_series({
        "badge_label": f"{team_a} vs {team_b} · Season Series",
        "sub_label":   f"{team_a_full} vs {team_b_full}",
        "period_team": team_a,
        "logo_a":      logo_a,
        "logo_b":      logo_b,
        "team_a":      team_a,
        "team_b":      team_b,
        "wins_a":      wins_a,
        "wins_b":      wins_b,
        "gf":          gf,
        "ga":          ga,
        "gd":          f"{gf - ga:+d}",
        "periods":     periods,
    }, slug=f"{slug_prefix}_02_series", out_dir=out_dir)

    print(f"  Rendering {slug_prefix} — game log")
    render_games({
        "badge_label": f"Game Log · {team_a} vs {team_b}",
        "sub_label":   f"Every {team_a}–{team_b} Matchup",
        "games":       game_displays,
    }, slug=f"{slug_prefix}_03_games", out_dir=out_dir)

    print(f"  Rendering {slug_prefix} — scorers")
    render_scorers({
        "badge_label":  f"{team_a} vs {team_b} · Scorers",
        "sub_label":    f"Top Scorers · {team_a} vs {team_b}",
        "logo_a":       logo_a,
        "logo_b":       logo_b,
        "team_a":       team_a,
        "team_b":       team_b,
        "team_a_full":  team_a_full.upper(),
        "team_b_full":  team_b_full.upper(),
        "a_scorers":    a_scorers,
        "b_scorers":    b_scorers,
    }, slug=f"{slug_prefix}_04_scorers", out_dir=out_dir)

    print(f"  Rendering {slug_prefix} — goaltending")
    render_goalie(goalie_ctx_a, slug=f"{slug_prefix}_05_goalie", out_dir=out_dir)


# ── Historical data ────────────────────────────────────────────────────────────

def _historical_ctx(logos: dict) -> dict:
    """
    Correct PWHL playoff results where the 1st seed lost to their chosen opponent.
    2023-24: Toronto (#1) chose Minnesota → Minnesota won.
    2024-25: Montréal (#1) chose Ottawa  → Ottawa won.
    """
    seasons = [
        {
            "season_label": "PWHL Season 1 · 2023–24",
            "title":        "Toronto Picks Minnesota",
            "seed_code":    "TOR",
            "seed_logo":    logos["TOR"],
            "upset_code":   "MIN",
            "upset_logo":   logos["MIN"],
            "result":       "MIN WIN",
            "series_label": "Best-of-3 Semifinal",
            "seed_won":     False,
            "note":         "Toronto held the 1st seed and chose <strong>Minnesota</strong>. "
                            "The Frost eliminated the Six in the semifinal.",
        },
        {
            "season_label": "PWHL Season 2 · 2024–25",
            "title":        "Montréal Picks Ottawa",
            "seed_code":    "MTL",
            "seed_logo":    logos["MTL"],
            "upset_code":   "OTT",
            "upset_logo":   logos["OTT"],
            "result":       "OTT WIN",
            "series_label": "Best-of-5 Semifinal",
            "seed_won":     False,
            "note":         "Montr&#xe9;al held the 1st seed and chose <strong>Ottawa</strong>. "
                            "The Charge upset the defending champions to reach the Final.",
        },
    ]
    return {"seasons": seasons}


# ── Main ───────────────────────────────────────────────────────────────────────

def run(out_dir: Path | None = None):
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR

    mtl_logo = _logo_uri("MTL")
    min_logo = _logo_uri("MIN")
    ott_logo = _logo_uri("OTT")
    bos_logo = _logo_uri("BOS")
    tor_logo = _logo_uri("TOR")

    def _player_photo(name: str) -> str | None:
        slug = name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
        for ext in ("webp", "jpg", "jpeg", "png"):
            p = PLAYERS_DIR / f"{slug}.{ext}"
            if p.exists():
                return _file_to_data_uri(p)
        return None

    poulin_photo   = _player_photo("marie philip poulin")
    heise_photo    = _player_photo("taylor heise")
    desbiens_photo = _player_photo("ann renee desbiens")
    philips_photo  = _player_photo("gwyneth philips")

    with Session(engine) as session:
        # MTL vs MIN
        games_mm   = _h2h_games(session, "MTL", "MIN")
        skaters_mm = _h2h_skaters(session, "MTL", "MIN")
        des_min    = _goalie_vs(session, "desbiens", "MTL", "MIN")
        des_ott    = _goalie_vs(session, "desbiens", "MTL", "OTT")

        # OTT vs BOS
        games_ob   = _h2h_games(session, "OTT", "BOS")
        skaters_ob = _h2h_skaters(session, "OTT", "BOS")
        phi_bos    = _goalie_vs(session, "philips", "OTT", "BOS")
        phi_season = _goalie_season(session, "philips", "OTT")

    # ── MTL goalie context ────────────────────────────────────────────────────
    des_wins = sum(1 for g in games_mm
                   if (g["home_code"] == "MTL" and g["home_score"] > g["away_score"])
                   or (g["away_code"] == "MTL" and g["away_score"] > g["home_score"]))

    goalie_ctx_mm = {
        "badge_label":  "Goaltending · MTL",
        "title_line1":  "THE NET",
        "title_line2":  "IS LOCKED",
        "goalie_name":  "Ann-Renée Desbiens",
        "hero_label":   "Save Percentage vs MIN",
        "hero_sv":      _fmt_svp(des_min.get("sv_pct")),
        "hero_sub":     f"4 Starts · {int(des_min.get('ga') or 0)} Goals Allowed · 4–0 Record",
        "goalie_wins":  des_wins,
        "goalie_sa":    int(des_min.get("sa") or 0),
        "goalie_sv_num": int(des_min.get("sv") or 0),
        "goalie_ga":    int(des_min.get("ga") or 0),
        "compare_label": "SV% by Opponent · 2025–26",
        "comp_a_logo":  min_logo,
        "comp_a_code":  "MIN",
        "comp_a_label": "vs MIN",
        "comp_a_sv":    _fmt_svp(des_min.get("sv_pct")),
        "comp_a_detail": f"{int(des_min.get('ga') or 0)} GA · {int(des_min.get('gp') or 0)} GP",
        "comp_b_logo":  ott_logo,
        "comp_b_code":  "OTT",
        "comp_b_label": "vs OTT",
        "comp_b_sv":    _fmt_svp(des_ott.get("sv_pct")),
        "comp_b_detail": f"{int(des_ott.get('ga') or 0)} GA · {int(des_ott.get('gp') or 0)} GP",
        "goalie_photo":  desbiens_photo,
    }

    # ── OTT goalie context ────────────────────────────────────────────────────
    phi_wins = sum(1 for g in games_ob
                   if (g["home_code"] == "OTT" and g["home_score"] > g["away_score"])
                   or (g["away_code"] == "OTT" and g["away_score"] > g["home_score"]))
    phi_losses = len(games_ob) - phi_wins
    phi_gp_vs_bos = int(phi_bos.get("gp") or 0)

    goalie_ctx_ob = {
        "badge_label":  "Goaltending · OTT",
        "title_line1":  "WALL OF",
        "title_line2":  "SENATORS",
        "goalie_name":  "Gwyneth Philips",
        "hero_label":   "Save Percentage vs BOS",
        "hero_sv":      _fmt_svp(phi_bos.get("sv_pct")),
        "hero_sub":     f"{phi_gp_vs_bos} Starts vs BOS · {int(phi_bos.get('ga') or 0)} Goals Allowed",
        "goalie_wins":  phi_wins,
        "goalie_sa":    int(phi_bos.get("sa") or 0),
        "goalie_sv_num": int(phi_bos.get("sv") or 0),
        "goalie_ga":    int(phi_bos.get("ga") or 0),
        "compare_label": "Philips SV% · 2025–26",
        "comp_a_logo":  bos_logo,
        "comp_a_code":  "BOS",
        "comp_a_label": "vs BOS",
        "comp_a_sv":    _fmt_svp(phi_bos.get("sv_pct")),
        "comp_a_detail": f"{int(phi_bos.get('ga') or 0)} GA · {int(phi_bos.get('gp') or 0)} GP",
        "comp_b_logo":  ott_logo,
        "comp_b_code":  "OTT",
        "comp_b_label": "Full Season",
        "comp_b_sv":    _fmt_svp(phi_season.get("sv_pct")),
        "comp_b_detail": f"{int(phi_season.get('ga') or 0)} GA · {int(phi_season.get('gp') or 0)} GP",
        "goalie_photo":  philips_photo,
    }

    # ── MTL vs MIN carousel (4 slides) ───────────────────────────────────────
    print("\n=== MTL vs MIN (4 slides) ===")
    wins_mm  = _wins(games_mm, "MTL")
    gf_mm, ga_mm = _gf_ga(games_mm, "MTL")
    logos_mm = {"MTL": mtl_logo, "MIN": min_logo}
    game_displays_mm = [_game_display(g, "MTL", "MIN", logos_mm) for g in games_mm]
    skaters_mm_a = [{"name": f"{s['first_name']} {s['last_name']}", "gp": s["gp"],
                     "g": int(s["g"]), "a": int(s["a"]), "pts": int(s["pts"])}
                    for s in skaters_mm if s["team_code"] == "MTL"][:5]
    skaters_mm_b = [{"name": f"{s['first_name']} {s['last_name']}", "gp": s["gp"],
                     "g": int(s["g"]), "a": int(s["a"]), "pts": int(s["pts"])}
                    for s in skaters_mm if s["team_code"] == "MIN"][:3]

    print("  Slide 1/4 — cover")
    render_cover({"mtl_logo": mtl_logo, "min_logo": min_logo,
                  "poulin_photo": poulin_photo, "heise_photo": heise_photo}, out_dir)

    print("  Slide 2/4 — game log")
    render_games({"badge_label": "Game Log · MTL vs MIN",
                  "sub_label":   "Every MTL–MIN Matchup",
                  "games":       game_displays_mm},
                 slug="playoff_h2h_02_games", out_dir=out_dir)

    print("  Slide 3/4 — key performers")
    render_scorers({"badge_label":  "MTL vs MIN · Scorers",
                    "sub_label":    "Top Scorers · MTL vs MIN",
                    "logo_a":       mtl_logo, "logo_b": min_logo,
                    "team_a":       "MTL",    "team_b": "MIN",
                    "team_a_full":  "MONTRÉAL", "team_b_full": "MINNESOTA",
                    "a_scorers":    skaters_mm_a, "b_scorers": skaters_mm_b},
                   slug="playoff_h2h_03_scorers", out_dir=out_dir)

    print("  Slide 4/4 — combined stats")
    render_mm_stats({
        "mtl_logo":      mtl_logo,
        "min_logo":      min_logo,
        "ott_logo":      ott_logo,
        "wins_a":        wins_mm,
        "wins_b":        len(games_mm) - wins_mm,
        "gf":            gf_mm,
        "ga":            ga_mm,
        "gd":            f"{gf_mm - ga_mm:+d}",
        "svp_vs_min":    _fmt_svp(des_min.get("sv_pct")),
        "svp_vs_ott":    _fmt_svp(des_ott.get("sv_pct")),
        "goalie_wins":   wins_mm,
        "goalie_starts": int(des_min.get("gp") or 0),
        "goalie_sa":     int(des_min.get("sa") or 0),
        "goalie_sv":     int(des_min.get("sv") or 0),
        "goalie_ga":     int(des_min.get("ga") or 0),
        "ga_vs_min":     int(des_min.get("ga") or 0),
        "gp_vs_min":     int(des_min.get("gp") or 0),
        "ga_vs_ott":     int(des_ott.get("ga") or 0),
        "gp_vs_ott":     int(des_ott.get("gp") or 0),
        "desbiens_photo": desbiens_photo,
    }, out_dir=out_dir)

    # ── OTT vs BOS carousel ───────────────────────────────────────────────────
    print("\n=== OTT vs BOS (5 slides) ===")
    _render_matchup(
        team_a="OTT", team_b="BOS",
        team_a_full="Ottawa", team_b_full="Boston",
        logo_a=ott_logo, logo_b=bos_logo,
        slug_prefix="playoff_ob",
        out_dir=out_dir,
        games=games_ob, skaters=skaters_ob,
        goalie_ctx_a=goalie_ctx_ob,
        cover_fn=lambda od: render_cover_ott({"ott_logo": ott_logo, "bos_logo": bos_logo}, od),
    )

    # ── Historical slide ──────────────────────────────────────────────────────
    print("\n=== Historical (1 slide) ===")
    logos = {"MTL": mtl_logo, "MIN": min_logo, "OTT": ott_logo, "BOS": bos_logo, "TOR": tor_logo}
    hist_ctx = _historical_ctx(logos)
    render_historical(hist_ctx, out_dir)

    print(f"\nDone. All slides written to {out_dir}")


if __name__ == "__main__":
    run()
