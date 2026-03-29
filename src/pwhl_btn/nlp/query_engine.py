"""
query_engine.py — Natural language → SQL → English query interface.

Sends a user question to Claude to generate SQL, executes it against the
Railway MySQL database, then asks Claude to summarise the results in plain
English.  On a SQL error the query is retried once with the error context
included in the prompt.

Usage (programmatic):
    from pwhl_btn.nlp.query_engine import run_query
    result = run_query("Who leads the league in goals this season?")
    print(result["summary"])

Returns:
    {
        "question": str,
        "sql":      str,
        "columns":  list[str],
        "rows":     list[dict],
        "summary":  str,
    }
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic
from sqlalchemy import text

from pwhl_btn.db.db_queries import engine

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output" / "nlp_results"
MODEL      = "claude-sonnet-4-6"

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a precise SQL generator for the PWHL (Professional Women's Hockey \
League) analytics MySQL database.

## Schema

games
  game_id INT PK, season_id INT, date DATE,
  home_team_id INT, away_team_id INT,
  home_score INT, away_score INT,
  result_type VARCHAR,   -- 'REG' | 'OT' | 'SO'
  game_status VARCHAR    -- 'final' for completed games

player_game_stats
  game_id INT, player_id INT, team_id INT,
  goals INT, assists INT, points INT,
  shots INT, plus_minus INT, pim INT, toi_seconds INT

goalie_game_stats
  game_id INT, team_id INT,
  saves INT, shots_against INT, goals_against INT, toi INT

teams
  team_id INT PK, team_code VARCHAR, team_name VARCHAR, season_id INT
  -- team_code values: BOS MIN MTL TOR OTT NY VAN SEA

players
  player_id INT PK, first_name VARCHAR, last_name VARCHAR, position VARCHAR

## Rules
1. Default to season_id = 8 unless the user specifies otherwise.
2. Points system: regulation win = 3 pts, OT/SO win = 2 pts, OT/SO loss = 1 pt,
   regulation loss = 0 pts.
3. For team queries involving win/loss records or matchups, always account for
   BOTH home_team_id and away_team_id sides.
4. For player name searches use LIKE '%name%' (case-insensitive).
5. Add LIMIT 50 if the query could return many rows and no LIMIT is specified.
6. Return ONLY the raw SQL query — no markdown fences, no explanation,
   no trailing semicolon.
7. Only generate SELECT statements.
"""


# ── Public API ─────────────────────────────────────────────────────────────────

def run_query(question: str) -> dict:
    """
    Translate a natural-language question into SQL, execute it, and return
    a plain-English summary along with the raw data.

    Always returns a dict with keys: question, sql, columns, rows, summary.
    On unrecoverable failure, rows will be empty and summary will contain the
    error explanation.
    """
    client = _get_client()

    # Step 1 — generate SQL
    sql = _generate_sql(client, question)

    # Step 2 — execute (one retry on failure)
    rows, columns, err = _execute(sql)
    if err:
        print(f"  [SQL error] {err}\n  Retrying with error context…")
        sql = _generate_sql(client, question, prior_sql=sql, error=err)
        rows, columns, err = _execute(sql)
        if err:
            result = {
                "question": question,
                "sql":      sql,
                "columns":  [],
                "rows":     [],
                "summary":  (
                    f"Sorry, I wasn't able to generate a valid query for that question. "
                    f"Error: {err}"
                ),
            }
            _save(result)
            return result

    # Step 3 — summarise
    summary = _summarise(client, question, sql, rows, columns)

    result = {
        "question": question,
        "sql":      sql,
        "columns":  columns,
        "rows":     rows,
        "summary":  summary,
    }
    _save(result)
    return result


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it before running."
        )
    return anthropic.Anthropic(api_key=key)


def _sql_user_message(
    question: str,
    prior_sql: str | None = None,
    error: str | None = None,
) -> str:
    if prior_sql and error:
        return (
            f"Question: {question}\n\n"
            f"Your previous SQL attempt failed:\n{prior_sql}\n\n"
            f"Error: {error}\n\n"
            "Please generate a corrected SQL query."
        )
    return f"Question: {question}"


def _generate_sql(
    client: anthropic.Anthropic,
    question: str,
    prior_sql: str | None = None,
    error: str | None = None,
) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _sql_user_message(question, prior_sql, error)}],
    )
    return response.content[0].text.strip()


def _execute(sql: str) -> tuple[list[dict], list[str], str | None]:
    """Run sql against the DB. Returns (rows, columns, error_or_None)."""
    try:
        with engine.connect() as conn:
            result  = conn.execute(text(sql))
            columns = list(result.keys())
            rows    = [
                {col: _to_json_safe(val) for col, val in zip(columns, row)}
                for row in result.fetchall()
            ]
            return rows, columns, None
    except Exception as exc:
        return [], [], str(exc)


def _to_json_safe(val):
    """Convert DB types that aren't JSON-serializable to plain Python types."""
    import datetime, decimal
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, decimal.Decimal):
        return float(val)
    return val


def _summarise(
    client: anthropic.Anthropic,
    question: str,
    sql: str,
    rows: list[dict],
    columns: list[str],
) -> str:
    rows_preview = rows[:50]
    rows_text    = json.dumps(rows_preview, default=str, indent=2) if rows_preview else "(no rows returned)"
    truncated    = f"\n(showing first 50 of {len(rows)} rows)" if len(rows) > 50 else ""

    content = (
        f"Question: {question}\n\n"
        f"SQL executed:\n{sql}\n\n"
        f"Results ({len(rows)} row(s)){truncated}:\n{rows_text}\n\n"
        "Please provide a clear, concise English answer to the question based on "
        "the results above. State any assumptions you made. If the results are "
        "empty, explain what that likely means in context."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text.strip()


def _save(result: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"nlp_{ts}.json"
    path.write_text(json.dumps(result, default=str, indent=2), encoding="utf-8")
