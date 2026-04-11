"""
backfill_period_scores.py — Patch period score columns for all completed games missing them.

Fetches only gs["goalsByPeriod"] — no player/goalie data touched.

Usage:
    python -m pwhl_btn.jobs.backfill_period_scores           # patch all NULL rows
    python -m pwhl_btn.jobs.backfill_period_scores --dry-run  # preview without writing
"""

import argparse
import time

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.jobs.backfill import SEASON_ID, RATE_LIMIT, fetch_game, _period_scores

engine  = get_engine(pool_pre_ping=True)
Session = sessionmaker(bind=engine)


def get_games_missing_period_scores(session) -> list[int]:
    rows = session.execute(text("""
        SELECT game_id FROM games
        WHERE season_id   = :sid
          AND game_status = 'final'
          AND home_score_p1 IS NULL
        ORDER BY game_id
    """), {"sid": SEASON_ID}).fetchall()
    return [r.game_id for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = Session()
    game_ids = get_games_missing_period_scores(session)

    if not game_ids:
        print("No games with missing period scores — nothing to do.")
        session.close()
        return

    print(f"Found {len(game_ids)} game(s) with NULL period scores. Patching...")

    ok = fail = 0
    for i, gid in enumerate(game_ids, start=1):
        print(f"  [{i:3d}/{len(game_ids)}] Game {gid}...", end=" ", flush=True)
        try:
            gs     = fetch_game(gid)
            scores = _period_scores(gs)

            if args.dry_run:
                h = f"P1={scores['home_score_p1']} P2={scores['home_score_p2']} P3={scores['home_score_p3']}"
                a = f"P1={scores['away_score_p1']} P2={scores['away_score_p2']} P3={scores['away_score_p3']}"
                print(f"[DRY]  home: {h}  away: {a}")
                ok += 1
                continue

            session.execute(text("""
                UPDATE games SET
                    home_score_p1 = :hp1,
                    home_score_p2 = :hp2,
                    home_score_p3 = :hp3,
                    away_score_p1 = :ap1,
                    away_score_p2 = :ap2,
                    away_score_p3 = :ap3
                WHERE game_id = :gid
            """), {
                "hp1": scores["home_score_p1"], "hp2": scores["home_score_p2"],
                "hp3": scores["home_score_p3"], "ap1": scores["away_score_p1"],
                "ap2": scores["away_score_p2"], "ap3": scores["away_score_p3"],
                "gid": gid,
            })
            session.commit()
            h = f"{scores['home_score_p1']}-{scores['home_score_p2']}-{scores['home_score_p3']}"
            a = f"{scores['away_score_p1']}-{scores['away_score_p2']}-{scores['away_score_p3']}"
            print(f"OK  (home {h} | away {a})")
            ok += 1

        except Exception as e:
            session.rollback()
            print(f"FAILED ({e})")
            fail += 1

        time.sleep(RATE_LIMIT)

    session.close()
    print(f"\nDone: {ok} patched, {fail} failed.")


if __name__ == "__main__":
    main()
