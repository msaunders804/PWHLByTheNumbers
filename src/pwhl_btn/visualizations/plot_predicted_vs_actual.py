"""
plot_predicted_vs_actual.py — Model calibration: predicted vs actual final points.

Calibration scatter. For each team the model projects a final-points distribution
from the 67% snapshot; this plots the projected mean (x) against the actual final
points (y), one dot per team, for Season 8 (8 teams).
Horizontal bars show each team's 10–90% projection interval, so the fraction of
dots whose interval crosses the 45° line measures how well-calibrated the model's
uncertainty is (a true 10–90% interval should contain the outcome ~80% of the time).

Outputs:
    output/predicted_vs_actual.png
    output/predicted_vs_actual.svg

Run from repo root:
    PYTHONPATH=src python src/pwhl_btn/visualizations/plot_predicted_vs_actual.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

from pwhl_btn.analytics.monte_carlo import run_validation

PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────

SNAPSHOT_PCT = 0.67
SEASONS = [
    # (season_id, legend label, color)
    (8, "Season 8 (8 teams)", "#8c52ff"),   # purple
]

# BTN brand palette
BG   = "#ffffff"
FG   = "#000000"
GRID = "#dddddd"
DIAG = "#aaaaaa"

# ── Fetch data ─────────────────────────────────────────────────────────────────

series = []   # list of (label, color, teams_dict)
for season_id, label, color in SEASONS:
    print(f"  Running {label} validation at {SNAPSHOT_PCT:.0%} snapshot...")
    result = run_validation(season_id=season_id, game_pct=SNAPSHOT_PCT, verbose=False)
    if not result or not result.get("teams"):
        print(f"    skipped (no data for season_id={season_id})")
        continue
    series.append((label, color, result["teams"]))
    print(f"    rho={result['spearman']:.3f}  p={result['p_value']:.3f}")

if not series:
    raise SystemExit("  No data returned — are season_id=5 and season_id=8 in the DB?")

# ── Figure ────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(6.2, 6.2))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

# Determine shared square axis range from all values
all_vals = []
for _, _, teams in series:
    for d in teams.values():
        all_vals += [d["pred_pts"], d["actual_pts"],
                     d["pred_pts_low"], d["pred_pts_high"]]
lo = min(all_vals) - 3
hi = max(all_vals) + 3

# 45° line = perfect calibration
ax.plot([lo, hi], [lo, hi], color=DIAG, linewidth=1.3, linestyle="--",
        zorder=1, label="Perfect prediction")

covered = 0
total   = 0
for label, color, teams in series:
    for code, d in teams.items():
        p, a  = d["pred_pts"], d["actual_pts"]
        lo_i  = d["pred_pts_low"]
        hi_i  = d["pred_pts_high"]
        total += 1
        if lo_i <= a <= hi_i:
            covered += 1

        # Horizontal 10–90% projection interval
        ax.errorbar(p, a, xerr=[[p - lo_i], [hi_i - p]],
                    fmt="none", ecolor=color, elinewidth=1.3,
                    capsize=3, alpha=0.55, zorder=2)
        ax.scatter(p, a, s=90, color=color, zorder=3,
                   edgecolors=FG, linewidths=0.5)
        ax.annotate(code, xy=(p, a), xytext=(7, 4),
                    textcoords="offset points", color=FG,
                    fontsize=8, fontweight="500")

# ── Axes ───────────────────────────────────────────────────────────────────────

ax.set_xlim(lo, hi)
ax.set_ylim(lo, hi)
ax.set_aspect("equal", adjustable="box")
ax.tick_params(colors=FG, which="both", length=0, labelsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor(GRID)
ax.xaxis.grid(True, color=GRID, linewidth=0.4, linestyle=":", zorder=0)
ax.yaxis.grid(True, color=GRID, linewidth=0.4, linestyle=":", zorder=0)
ax.set_axisbelow(True)

ax.set_xlabel("Predicted final points  (67% snapshot)", color=FG, fontsize=11, labelpad=7)
ax.set_ylabel("Actual final points", color=FG, fontsize=11, labelpad=7)

# ── Legend ─────────────────────────────────────────────────────────────────────

legend_handles = [
    mlines.Line2D([], [], color=DIAG, linewidth=1.3, linestyle="--",
                  label="Perfect prediction"),
]
for label, color, _ in series:
    legend_handles.append(
        mlines.Line2D([], [], color=color, marker="o", linestyle="None",
                      markersize=8, markeredgecolor=FG, markeredgewidth=0.5,
                      label=label))
legend_handles.append(
    mlines.Line2D([], [], color="#888888", marker="|", linestyle="None",
                  markersize=10, label="10–90% projection interval"))
ax.legend(handles=legend_handles, loc="upper left", fontsize=8.5,
          facecolor="#f5f5f5", edgecolor=GRID, labelcolor=FG, framealpha=0.9)

# ── Title & watermark ──────────────────────────────────────────────────────────

ax.set_title(
    "Season 8 Calibration: Predicted vs Actual Final Points",
    color=FG, fontsize=14, fontweight="600", pad=24, loc="center",
)
ax.text(0.5, 1.03,
        f"67% snapshot · {covered}/{total} actual finishes fell inside the 10–90% projection",
        transform=ax.transAxes, ha="center", va="bottom",
        color="#888888", fontsize=9.5)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#444444", fontsize=7.5)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
png_path = OUTPUT_DIR / "predicted_vs_actual.png"
svg_path = OUTPUT_DIR / "predicted_vs_actual.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
print(f"  Interval coverage: {covered}/{total}")
