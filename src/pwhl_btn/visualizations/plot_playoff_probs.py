"""
plot_playoff_probs.py — Season 8 playoff qualification probability chart.

Horizontal bar chart showing each team's Monte Carlo-derived probability of
finishing in the top 4 (playoff spot), based on current standings.

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

from pwhl_btn.analytics.monte_carlo import run_simulation

# ── Brand colors ──────────────────────────────────────────────────────────────

BG           = "#000000"
FG           = "#ffffff"
GRID         = "#2a2a2a"
BAR_IN       = "#8c52ff"   # top 4 — in playoff position
BAR_OUT      = "#3a3a3a"   # 5th–8th — out
BAR_EDGE_IN  = "#b38aff"
BAR_EDGE_OUT = "#5a5a5a"
LINE_COLOR   = "#ff6b6b"   # 50% coin-flip line

# ── Run simulation ─────────────────────────────────────────────────────────────

print("  Running Monte Carlo simulation...")
results = run_simulation()

# Sort teams by playoff probability descending
teams = sorted(results.values(), key=lambda t: t["playoff_pct"], reverse=True)
n = len(teams)

labels   = [t["team_code"]    for t in teams]
probs    = [t["playoff_pct"]  for t in teams]
cur_pts  = [t["current_pts"]  for t in teams]
gp_rem   = [t["games_remaining"] for t in teams]
proj_pts = [t["proj_pts_mean"] for t in teams]

PLAYOFF_SPOTS = 4

# ── Figure ────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

y_pos = list(range(n))

for i, (team, prob) in enumerate(zip(teams, probs)):
    in_playoffs = i < PLAYOFF_SPOTS
    color       = BAR_IN  if in_playoffs else BAR_OUT
    edge        = BAR_EDGE_IN if in_playoffs else BAR_EDGE_OUT

    ax.barh(i, prob, height=0.62, color=color,
            edgecolor=edge, linewidth=0.8, zorder=2)

    # Probability label inside/outside bar
    label_x = prob - 1.5 if prob >= 12 else prob + 1.0
    ha      = "right"    if prob >= 12 else "left"
    ax.text(label_x, i, f"{prob:.1f}%",
            va="center", ha=ha, color=FG,
            fontsize=10.5, fontweight="600", zorder=3)

    # Right-side annotation: pts + games remaining
    ax.text(102, i,
            f"{team['current_pts']} pts  |  {team['games_remaining']} GP left",
            va="center", ha="left", color="#888888", fontsize=8.5)

# Playoff cutoff line (horizontal, between 4th and 5th)
if n > PLAYOFF_SPOTS:
    cutoff_y = PLAYOFF_SPOTS - 0.5
    ax.axhline(cutoff_y, color=LINE_COLOR, linewidth=1.2,
               linestyle="--", zorder=4, alpha=0.8)
    ax.text(0.5, cutoff_y + 0.08, "Playoff cutoff (Top 4)",
            color=LINE_COLOR, fontsize=8, va="bottom", alpha=0.9)

# 50% reference line
ax.axvline(50, color="#555555", linewidth=0.8, linestyle=":", zorder=1)
ax.text(50.5, -0.7, "50%", color="#555555", fontsize=7.5, va="top")

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

ax.set_xlabel("Probability of finishing Top 4",
              color="#888888", fontsize=10, labelpad=8)
ax.set_title(
    "Season 8 Playoff Qualification Probabilities (67% Snapshot)",
    color=FG, fontsize=16, fontweight="500", pad=14, loc="center",
)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#444444", fontsize=7.5)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
plt.subplots_adjust(right=0.78)   # make room for right-side annotations

png_path = OUTPUT_DIR / "playoff_probs.png"
svg_path = OUTPUT_DIR / "playoff_probs.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg",  bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
