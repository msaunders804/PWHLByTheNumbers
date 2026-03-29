"""
cli.py — Interactive REPL for the BTN natural language query engine.

Usage:
    python -m pwhl_btn.nlp.cli

Type a plain-English question about PWHL stats and press Enter.
Type 'quit' or 'exit' (or Ctrl-C / Ctrl-D) to exit.
"""
from __future__ import annotations

from pwhl_btn.nlp.query_engine import run_query

_BANNER = """\
╔══════════════════════════════════════════════════════╗
║     PWHL By The Numbers — Natural Language Query     ║
║     Type a question, or 'quit' to exit.              ║
╚══════════════════════════════════════════════════════╝
"""

_MAX_TABLE_ROWS = 25   # truncate display beyond this many rows


def main() -> None:
    print(_BANNER)
    while True:
        try:
            question = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        print()
        try:
            result = run_query(question)
        except EnvironmentError as exc:
            print(f"Configuration error: {exc}\n")
            continue
        except Exception as exc:
            print(f"Unexpected error: {exc}\n")
            continue

        # Summary
        print(result["summary"])
        print()

        # Data table
        if result["rows"]:
            _print_table(result["columns"], result["rows"])
            print()


def _print_table(columns: list[str], rows: list[dict]) -> None:
    display_rows = rows[:_MAX_TABLE_ROWS]
    truncated    = len(rows) > _MAX_TABLE_ROWS

    # Column widths: max of header length vs any cell value length
    widths: dict[str, int] = {col: len(col) for col in columns}
    for row in display_rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))

    sep    = "+-" + "-+-".join("-" * widths[col] for col in columns) + "-+"
    header = "| " + " | ".join(col.ljust(widths[col]) for col in columns) + " |"

    print(sep)
    print(header)
    print(sep)
    for row in display_rows:
        line = "| " + " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns) + " |"
        print(line)
    print(sep)

    total = len(rows)
    if truncated:
        print(f"  … {total - _MAX_TABLE_ROWS} more row(s) not shown (full results saved to output/nlp_results/)")
    else:
        print(f"  {total} row(s)")


if __name__ == "__main__":
    main()
