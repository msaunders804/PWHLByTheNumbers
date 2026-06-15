"""
run_hook_ott.py — Renders the OTT vs BOS hook slide.
Usage: python -m pwhl_btn.jobs.run_hook_ott
"""
from pathlib import Path
from pwhl_btn.db.db_queries import _logo_uri
from pwhl_btn.render.prediction_render import render_pred_hook_ott

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"


def run():
    data = {
        "ott_logo": _logo_uri("OTT"),
        "bos_logo": _logo_uri("BOS"),
    }
    print("Rendering OTT vs BOS hook slide...")
    render_pred_hook_ott(data, OUTPUT_DIR)
    print(f"Done. Output → {OUTPUT_DIR / 'pred_hook_ott.png'}")


if __name__ == "__main__":
    run()
