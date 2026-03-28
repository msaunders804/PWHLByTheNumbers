"""
plot_predicted_vs_actual.py — Predicted vs Actual Season 7 Standings.

Scatter plots (one per snapshot) showing how the model's predicted final rank
compares to the actual final rank for each PWHL team.

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
import numpy as np

PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

from pwhl_btn.analytics.monte_carlo import run_validation

# ── Config ────────────────────────────────────────────────────────────────────

S7_SEASON_ID = 5   # season_id 5 = PWHL Season 7
SNAPSHOTS    = [
    (0.67, "67% of Season"),
]

# BTN brand colors
BG       = "#ffffff"
FG       = "#000000"
GRID     = "#dddddd"
ACCENT   = "#8c52ff"
DOT_GOOD = "#8c52ff"   # on or near diagonal
DOT_BAD  = "#ff6b6b"   # far from diagonal
DIAG     = "#aaaaaa"

# ── Fetch data ─────────────────────────────────────────────────────────────────

print("  Running Season 7 validation at each snapshot...")
snapshot_results = []

for pct, label in SNAPSHOTS:
    print(f"    {label} ({pct:.0%})...")
    result = run_validation(season_id=S7_SEASON_ID, game_pct=pct, verbose=False)
    if result and result.get("teams"):
        snapshot_results.append((label, pct, result))
        print(f"      rho={result['spearman']:.3f}  p={result['p_value']:.3f}")
    else:
        print(f"      skipped (no data)")

if not snapshot_results:
    print("  No data returned — is season_id=5 (Season 7) in the DB?")
    raise SystemExit(1)

# ── Figure ────────────────────────────────────────────────────────────────────

n_plots = len(snapshot_results)
fig, axes = plt.subplots(1, n_plots, figsize=(4.5 * n_plots, 5.2))
fig.patch.set_facecolor(BG)

if n_plots == 1:
    axes = [axes]

N_TEAMS = 8   # PWHL always 8 teams

for ax, (label, pct, result) in zip(axes, snapshot_results):
    ax.set_facecolor(BG)

    teams = result["teams"]
    rho   = result["spearman"]
    pval  = result["p_value"]

    pred_ranks   = [d["pred_rank"]   for d in teams.values()]
    actual_ranks = [d["actual_rank"] for d in teams.values()]
    codes        = list(teams.keys())

    # 45° diagonal (perfect prediction)
    ax.plot([0.5, N_TEAMS + 0.5], [0.5, N_TEAMS + 0.5],
            color=DIAG, linewidth=1.2, linestyle="--", zorder=1,
            label="Perfect prediction")

    # Color each dot by distance from diagonal
    for code, d in teams.items():
        pr = d["pred_rank"]
        ar = d["actual_rank"]
        dist = abs(pr - ar)
        color = DOT_GOOD if dist <= 1 else DOT_BAD

        ax.scatter(pr, ar, s=110, color=color, zorder=3,
                   edgecolors=FG, linewidths=0.5)
        # Label offset: push right/up to avoid overlap
        ax.annotate(
            code,
            xy=(pr, ar),
            xytext=(7, 4),
            textcoords="offset points",
            color=FG,
            fontsize=8.5,
            fontweight="500",
        )

    # Axes
    ticks = list(range(1, N_TEAMS + 1))
    ax.set_xlim(0.3, N_TEAMS + 0.7)
    ax.set_ylim(0.3, N_TEAMS + 0.7)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.tick_params(colors=FG, which="both", length=0, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.4, linestyle=":", zorder=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.4, linestyle=":", zorder=0)
    ax.set_axisbelow(True)

    ax.set_xlabel("Predicted rank", color=FG, fontsize=10, labelpad=6)
    if ax is axes[0]:
        ax.set_ylabel("Actual final rank", color=FG, fontsize=10, labelpad=6)
    else:
        ax.set_yticklabels([])

    sig_str = f"p={pval:.3f}" if pval >= 0.05 else f"p={pval:.3f} ✓"
    ax.set_title(
        f"{label}\nρ = {rho:.3f}  ({sig_str})",
        color=FG, fontsize=11, fontweight="500", pad=4,
    )

# ── Shared legend ─────────────────────────────────────────────────────────────

legend_handles = [
    mlines.Line2D([], [], color=DIAG,     linewidth=1.2, linestyle="--",
                  label="Perfect prediction"),
    mlines.Line2D([], [], color=DOT_GOOD, marker="o",   linestyle="None",
                  markersize=8, markeredgecolor=FG, markeredgewidth=0.5,
                  label="Off by ≤ 1 rank"),
    mlines.Line2D([], [], color=DOT_BAD,  marker="o",   linestyle="None",
                  markersize=8, markeredgecolor=FG, markeredgewidth=0.5,
                  label="Off by 2+ ranks"),
]
axes[-1].legend(
    handles=legend_handles, loc="upper left",
    fontsize=8.5, facecolor="#f5f5f5", edgecolor=GRID,
    labelcolor=FG, framealpha=0.9,
)

# ── Titles & watermark ────────────────────────────────────────────────────────

fig.suptitle(
    "Predicted vs Actual 24-25 Season Standings",
    color=FG, fontsize=18, fontweight="500", y=1.00,
)
fig.text(
    0.5, -0.04,
    "Perfect ranking match at 80% and 90% snapshots.",
    ha="center", color="#888888", fontsize=9, style="italic",
)
fig.text(
    0.99, -0.04, "ByTheNumbers · PWHL Analytics",
    ha="right", color="#444444", fontsize=7.5,
)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.6)
png_path = OUTPUT_DIR / "predicted_vs_actual.png"
svg_path = OUTPUT_DIR / "predicted_vs_actual.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
