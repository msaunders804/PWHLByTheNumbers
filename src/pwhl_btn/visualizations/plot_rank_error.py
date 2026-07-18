"""
plot_rank_error.py — Model accuracy across season snapshots, S7 vs S8.

Grouped bar chart showing mean absolute rank error (MAE) at 33%, 67%, and 90%
for Season 7 (6 teams) and Season 8 (8 teams), with Spearman ρ annotated on
each bar. Lower bars = better prediction; non-significant bars (p ≥ 0.05) are
drawn at reduced opacity.

Outputs:
    output/rank_error.png
    output/rank_error.svg

Run from repo root:
    PYTHONPATH=src python src/pwhl_btn/visualizations/plot_rank_error.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

from pwhl_btn.analytics.monte_carlo import run_validation

# ── Config ─────────────────────────────────────────────────────────────────────

SEASONS = [
    # (season_id, legend label, bar color)
    (5, "Season 7 (6 teams)", "#8c52ff"),   # purple
    (8, "Season 8 (8 teams)", "#ff8c42"),   # orange
]
SNAPSHOTS = [
    (0.33, "33%"),
    (0.67, "67%"),
    (0.90, "90%"),
]

# White-background brand palette
BG          = "#ffffff"
FG          = "#000000"
GRID        = "#dddddd"
ANNOT_COLOR = "#000000"

# ── Fetch data ─────────────────────────────────────────────────────────────────

# series[season_id] = list of per-snapshot dicts aligned to SNAPSHOTS order
series = {}
for season_id, label, color in SEASONS:
    print(f"  Running {label} validation at each snapshot...")
    recs = []
    for pct, snap_label in SNAPSHOTS:
        result = run_validation(season_id=season_id, game_pct=pct, verbose=False)
        if not result or not result.get("teams"):
            print(f"    {snap_label} — skipped (no data)")
            recs.append(None)
            continue
        teams = result["teams"]
        mae   = float(np.mean([abs(d["pred_rank"] - d["actual_rank"])
                                for d in teams.values()]))
        recs.append({
            "mae":  mae,
            "rho":  result["spearman"],
            "pval": result["p_value"],
            "sig":  result["p_value"] < 0.05,
        })
        print(f"    {snap_label} — MAE={mae:.2f}  rho={result['spearman']:.3f}  p={result['p_value']:.3f}")
    series[season_id] = recs

all_maes = [r["mae"] for recs in series.values() for r in recs if r]
if not all_maes:
    print("  No data returned — are season_id=5 and season_id=8 in the DB?")
    raise SystemExit(1)

# ── Figure ─────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(7, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

snap_labels = [s[1] for s in SNAPSHOTS]
x           = np.arange(len(SNAPSHOTS))
n_series    = len(SEASONS)
group_w     = 0.72
bar_w       = group_w / n_series

for s_idx, (season_id, label, color) in enumerate(SEASONS):
    offset = (s_idx - (n_series - 1) / 2) * bar_w
    for j, rec in enumerate(series[season_id]):
        if rec is None:
            continue
        alpha = 1.0 if rec["sig"] else 0.4
        ax.bar(x[j] + offset, rec["mae"], width=bar_w * 0.92,
               color=color, edgecolor=color, linewidth=1.0,
               alpha=alpha, zorder=2)
        sig_marker = " *" if rec["sig"] else ""
        ax.text(x[j] + offset, rec["mae"] + 0.04,
                f"{rec['rho']:.2f}{sig_marker}",
                ha="center", va="bottom", color=FG, fontsize=8.5,
                fontweight="600", rotation=0)

# Reference line at MAE = 1.0 (off by one rank on average)
ax.axhline(1.0, color=GRID, linewidth=1.0, linestyle="--", zorder=1)
ax.text(len(SNAPSHOTS) - 0.5, 1.03, "±1 rank", color="#aaaaaa",
        fontsize=8, ha="right", va="bottom", style="italic")

# ── Axes ───────────────────────────────────────────────────────────────────────

ax.set_xticks(x)
ax.set_xticklabels(snap_labels, color=FG, fontsize=12)
ax.set_xlim(-0.5, len(SNAPSHOTS) - 0.5)
ax.set_ylim(0, max(all_maes) * 1.55)

ax.set_ylabel("Mean Absolute Rank Error", color=FG, fontsize=11, labelpad=8)
ax.set_xlabel("Season Snapshot", color=FG, fontsize=11, labelpad=8)

ax.tick_params(axis="y", colors=FG, labelsize=9, length=0)
ax.tick_params(axis="x", length=0)
ax.yaxis.grid(True, color=GRID, linewidth=0.5, linestyle="--", zorder=0)
ax.set_axisbelow(True)

for spine in ax.spines.values():
    spine.set_visible(False)

# ── Legend ─────────────────────────────────────────────────────────────────────

from matplotlib.patches import Patch
legend_handles = [Patch(facecolor=color, label=label)
                  for _, label, color in SEASONS]
legend_handles.append(Patch(facecolor="#999999", alpha=0.4, label="faded = p ≥ 0.05"))
ax.legend(handles=legend_handles, loc="upper right",
          fontsize=8.5, facecolor="#f5f5f5", edgecolor=GRID,
          labelcolor=FG, framealpha=0.9)

# ── Title & watermark ──────────────────────────────────────────────────────────

ax.set_title(
    "Monte Carlo Model Accuracy by Season Snapshot\nSeason 7 vs Season 8  (ρ annotated, * = p < 0.05)",
    color=FG, fontsize=13, fontweight="500", pad=10,
)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#aaaaaa", fontsize=7.5)

# ── Save ───────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
png_path = OUTPUT_DIR / "rank_error.png"
svg_path = OUTPUT_DIR / "rank_error.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
