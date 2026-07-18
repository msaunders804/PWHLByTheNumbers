"""
plot_playoff_probs.py — Season 8 playoff forecast at 67% vs actual outcome.

Horizontal bar chart of each team's Monte Carlo top-4 probability computed at
the 67% snapshot of Season 8, annotated with whether the team *actually*
finished in the top 4. Validates the mid-season forecast against reality.

Outputs:
    output/playoff_probs.png
    output/playoff_probs.svg

Run from repo root:
    PYTHONPATH=src python src/pwhl_btn/visualizations/plot_playoff_probs.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

from pwhl_btn.analytics.monte_carlo import run_validation

S8_SEASON_ID = 8
SNAPSHOT_PCT = 0.67
PLAYOFF_SPOTS = 4

# ── Brand colors ──────────────────────────────────────────────────────────────

BG           = "#ffffff"
FG           = "#000000"
GRID         = "#dddddd"
BAR_IN       = "#8c52ff"   # predicted top 4 — in playoff position
BAR_OUT      = "#d0d0d0"   # predicted 5th–8th — out
BAR_EDGE_IN  = "#8c52ff"
BAR_EDGE_OUT = "#aaaaaa"
LINE_COLOR   = "#ff6b6b"   # 50% coin-flip line

# ── Run 67% snapshot validation ────────────────────────────────────────────────

print(f"  Running Season {S8_SEASON_ID} validation at {SNAPSHOT_PCT:.0%} snapshot...")
result = run_validation(season_id=S8_SEASON_ID, game_pct=SNAPSHOT_PCT, verbose=False)
if not result or not result.get("teams"):
    raise SystemExit(f"  No data for season_id={S8_SEASON_ID} — is it populated in the DB?")

# result["teams"] is keyed by team_code → {pred_rank, actual_rank, playoff_pct, ...}
team_rows = [{"team_code": code, **vals} for code, vals in result["teams"].items()]

# Sort by predicted playoff probability descending
teams = sorted(team_rows, key=lambda t: t["playoff_pct"], reverse=True)
n = len(teams)

labels = [t["team_code"]   for t in teams]
probs  = [t["playoff_pct"] for t in teams]

# ── Figure ────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

y_pos = list(range(n))

for i, (team, prob) in enumerate(zip(teams, probs)):
    predicted_in = i < PLAYOFF_SPOTS   # top 4 by predicted prob

    color = BAR_IN  if predicted_in else BAR_OUT
    edge  = BAR_EDGE_IN if predicted_in else BAR_EDGE_OUT

    ax.barh(i, prob, height=0.62, color=color,
            edgecolor=edge, linewidth=0.8, zorder=2)

    # Probability label inside/outside bar
    label_x = prob - 1.5 if prob >= 12 else prob + 1.0
    ha      = "right"    if prob >= 12 else "left"
    ax.text(label_x, i, f"{prob:.1f}%",
            va="center", ha=ha, color=FG,
            fontsize=10.5, fontweight="600", zorder=3)

# Playoff cutoff line (horizontal, between 4th and 5th)
if n > PLAYOFF_SPOTS:
    cutoff_y = PLAYOFF_SPOTS - 0.5
    ax.axhline(cutoff_y, color=LINE_COLOR, linewidth=1.2,
               linestyle="--", zorder=4, alpha=0.8)
    ax.text(0.5, cutoff_y + 0.08, "Playoff cutoff (Top 4)",
            color=LINE_COLOR, fontsize=8, va="bottom", alpha=0.9)

# 50% reference line
ax.axvline(50, color="#aaaaaa", linewidth=0.8, linestyle=":", zorder=1)
ax.text(50.5, -0.7, "50%", color="#aaaaaa", fontsize=7.5, va="top")

# ── Axes ──────────────────────────────────────────────────────────────────────

ax.set_xlim(0, 100)
ax.set_ylim(-0.6, n - 0.4)
ax.set_yticks(y_pos)
ax.set_yticklabels(labels, color=FG, fontsize=11, fontweight="500")
ax.invert_yaxis()   # highest probability at top

ax.xaxis.set_major_formatter(mticker.PercentFormatter())
ax.tick_params(axis="x", colors="#888888", labelsize=9, length=0)
ax.tick_params(axis="y", length=0)

for spine in ax.spines.values():
    spine.set_visible(False)

ax.xaxis.grid(True, color=GRID, linewidth=0.5, linestyle="--", zorder=0)
ax.set_axisbelow(True)

# ── Labels & title ────────────────────────────────────────────────────────────

ax.set_xlabel("Predicted probability of finishing Top 4  (67% snapshot)",
              color="#888888", fontsize=10, labelpad=8)

# Count correct forecasts (predicted Top-4 vs actual Top-4)
hits = sum(1 for i, t in enumerate(teams)
           if (i < PLAYOFF_SPOTS) == (t["actual_rank"] <= PLAYOFF_SPOTS))

# Bold title (method) with a subtitle reporting accuracy vs final standings
ax.set_title(
    "Monte Carlo Playoff Prediction @ 67% of the Season",
    color=FG, fontsize=15, fontweight="600", pad=24, loc="center",
)
ax.text(0.5, 1.035,
        f"{hits}/{n} correct with Season Final Results",
        transform=ax.transAxes, ha="center", va="bottom",
        color="#888888", fontsize=10)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#444444", fontsize=7.5)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
plt.subplots_adjust(right=0.9)   # breathing room at the 100% edge

png_path = OUTPUT_DIR / "playoff_probs.png"
svg_path = OUTPUT_DIR / "playoff_probs.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg",  bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
