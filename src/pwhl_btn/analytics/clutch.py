"""
clutch.py — "Which Teams Actually Win When It Matters?"

Clutch-time metrics derived from period-by-period scoring:
  - 3rd period goal differential per team
  - Record when tied / leading / trailing entering the 3rd
  - OT/SO record per team

Usage:
    python -m pwhl_btn.analytics.clutch
"""

from sqlalchemy import text
from pwhl_btn.db.db_config import get_engine

SEASON_ID = 8


def get_clutch_stats(season_id: int = SEASON_ID) -> list[dict]:
    """
    Returns one dict per team with all clutch metrics.
    Requires home_score_p1/p2/p3 and away_score_p1/p2/p3 to be populated.
    """
    engine = get_engine(pool_pre_ping=True)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            WITH team_games AS (
                -- Expand each game into two rows: one per team
                SELECT
                    g.game_id,
                    g.result_type,
                    g.home_team_id                            AS team_id,
                    g.home_score_p1                           AS gf_p1,
                    g.home_score_p2                           AS gf_p2,
                    g.home_score_p3                           AS gf_p3,
                    g.away_score_p1                           AS ga_p1,
                    g.away_score_p2                           AS ga_p2,
                    g.away_score_p3                           AS ga_p3,
                    CASE WHEN g.home_score > g.away_score THEN 1 ELSE 0 END AS won
                FROM games g
                WHERE g.season_id   = :sid
                  AND g.game_status = 'final'
                  AND g.home_score_p1 IS NOT NULL

                UNION ALL

                SELECT
                    g.game_id,
                    g.result_type,
                    g.away_team_id                            AS team_id,
                    g.away_score_p1                           AS gf_p1,
                    g.away_score_p2                           AS gf_p2,
                    g.away_score_p3                           AS gf_p3,
                    g.home_score_p1                           AS ga_p1,
                    g.home_score_p2                           AS ga_p2,
                    g.home_score_p3                           AS ga_p3,
                    CASE WHEN g.away_score > g.home_score THEN 1 ELSE 0 END AS won
                FROM games g
                WHERE g.season_id   = :sid
                  AND g.game_status = 'final'
                  AND g.away_score_p1 IS NOT NULL
            ),
            team_games_enriched AS (
                SELECT *,
                    (gf_p1 + gf_p2) AS score_for_after2,
                    (ga_p1 + ga_p2) AS score_against_after2,
                    (gf_p3 - ga_p3) AS p3_diff
                FROM team_games
            )
            SELECT
                t.team_code,
                t.team_name,

                -- 3rd period goal differential
                SUM(tg.gf_p3)                                              AS p3_gf,
                SUM(tg.ga_p3)                                              AS p3_ga,
                SUM(tg.p3_diff)                                            AS p3_diff,

                -- Record when tied after 2
                SUM(CASE WHEN tg.score_for_after2 = tg.score_against_after2 THEN 1 ELSE 0 END) AS tied_after2_gp,
                SUM(CASE WHEN tg.score_for_after2 = tg.score_against_after2 AND tg.won = 1 THEN 1 ELSE 0 END) AS tied_after2_w,

                -- Record when leading after 2
                SUM(CASE WHEN tg.score_for_after2 > tg.score_against_after2 THEN 1 ELSE 0 END) AS leading_after2_gp,
                SUM(CASE WHEN tg.score_for_after2 > tg.score_against_after2 AND tg.won = 1 THEN 1 ELSE 0 END) AS leading_after2_w,

                -- Record when trailing after 2
                SUM(CASE WHEN tg.score_for_after2 < tg.score_against_after2 THEN 1 ELSE 0 END) AS trailing_after2_gp,
                SUM(CASE WHEN tg.score_for_after2 < tg.score_against_after2 AND tg.won = 1 THEN 1 ELSE 0 END) AS trailing_after2_w,

                -- OT record (excludes SO)
                SUM(CASE WHEN tg.result_type = 'OT' THEN 1 ELSE 0 END)    AS ot_gp,
                SUM(CASE WHEN tg.result_type = 'OT' AND tg.won = 1 THEN 1 ELSE 0 END) AS ot_w,

                -- SO record
                SUM(CASE WHEN tg.result_type = 'SO' THEN 1 ELSE 0 END)    AS so_gp,
                SUM(CASE WHEN tg.result_type = 'SO' AND tg.won = 1 THEN 1 ELSE 0 END) AS so_w

            FROM team_games_enriched tg
            JOIN teams t ON t.team_id = tg.team_id AND t.season_id = :sid
            GROUP BY t.team_code, t.team_name
            ORDER BY p3_diff DESC
        """), {"sid": season_id}).mappings().all()

    return [dict(r) for r in rows]


def print_clutch_report(season_id: int = SEASON_ID) -> None:
    rows = get_clutch_stats(season_id)

    if not rows:
        print("No data — run the migration and period score backfill first.")
        return

    print(f"\n  Clutch Performance Report — Season {season_id}")
    print("  " + "─" * 72)

    # 3rd period differential
    print(f"\n  {'TEAM':<6}  {'P3 GF':>6}  {'P3 GA':>6}  {'P3 +/-':>7}  "
          f"{'TIED@2':>8}  {'LEAD@2':>8}  {'TRAIL@2':>9}  {'OT':>6}  {'SO':>6}")
    print("  " + "─" * 72)

    for r in rows:
        def record(w, gp):
            if gp == 0:
                return "  —"
            return f"{w}-{gp - w}"

        p3   = f"{r['p3_diff']:+d}"
        tied = record(r['tied_after2_w'],    r['tied_after2_gp'])
        lead = record(r['leading_after2_w'], r['leading_after2_gp'])
        trl  = record(r['trailing_after2_w'],r['trailing_after2_gp'])
        ot   = record(r['ot_w'],             r['ot_gp'])
        so   = record(r['so_w'],             r['so_gp'])

        print(f"  {r['team_code']:<6}  {r['p3_gf']:>6}  {r['p3_ga']:>6}  {p3:>7}  "
              f"{tied:>8}  {lead:>8}  {trl:>9}  {ot:>6}  {so:>6}")

    print()


if __name__ == "__main__":
    print_clutch_report()
