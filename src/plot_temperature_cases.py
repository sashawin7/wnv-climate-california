"""Scatter of weekly WNV cases against same-week temperature, with LOWESS smooths.

One point per county-week with at least one case, 2020 onward, for each of
tmax, tmin and tavg. Cases are on a log axis with slight vertical jitter, since
most county-weeks have 1-3 cases and would otherwise sit on top of each other.

Run from the project root:  python -m src.plot_temperature_cases
Output: outputs/figures/temperature_vs_cases_2020_2026.png
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess

from src.config import PROCESSED, ROOT

DATA = PROCESSED / "ca_wnv_weather_weekly.csv"
OUT = ROOT / "outputs" / "figures" / "temperature_vs_cases_2020_2026.png"
FIRST_YEAR = 2020

# Categorical slots 1-3 of the reference palette (validated for all-pairs use).
SERIES = [
    ("tmin", "Daily low (tmin)", "#2a78d6"),
    ("tavg", "Daily mean (tavg)", "#1baf7a"),
    ("tmax", "Daily high (tmax)", "#eb6834"),
]
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def main() -> None:
    d = pd.read_csv(DATA)
    d = d[(d["mmwr_year"] >= FIRST_YEAR) & (d["wnv_cases"] > 0)]
    first, last = d["mmwr_year"].min(), d["mmwr_year"].max()

    rng = np.random.default_rng(0)
    jitter = np.exp(rng.uniform(-0.08, 0.08, len(d)))  # +/- 8%, symmetric on a log axis

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for col, label, color in SERIES:
        ax.scatter(d[col], d["wnv_cases"] * jitter, s=14, color=color, alpha=0.35,
                   linewidths=0, label=label)
    for col, label, color in SERIES:
        fit = lowess(d["wnv_cases"], d[col], frac=0.4)
        ax.plot(fit[:, 0], fit[:, 1], color=SURFACE, linewidth=4.5)  # surface ring
        ax.plot(fit[:, 0], fit[:, 1], color=color, linewidth=2.2)
        ax.annotate(col, (fit[-1, 0], fit[-1, 1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK_2, fontweight="bold")

    ax.set_yscale("log")
    ax.set_yticks([1, 2, 5, 10, 20, 40])
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("Weekly mean temperature (°C), same week as reported cases", color=INK_2)
    ax.set_ylabel("WNV cases in the county-week (log scale)", color=INK_2)
    ax.set_title(
        f"WNV cases vs. temperature, county-weeks with ≥1 case, {first}–{last}",
        loc="left", color=INK, fontsize=12, fontweight="bold", pad=24,
    )
    ax.text(0, 1.01, f"{len(d):,} county-weeks, {d['wnv_cases'].sum():,} cases. "
            "Lines are LOWESS smooths (frac 0.4) of cases on temperature.",
            transform=ax.transAxes, fontsize=8.5, color=INK_2, va="bottom")
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    leg = ax.legend(loc="upper left", frameon=False, fontsize=9, markerscale=1.6)
    for h in leg.legend_handles:
        h.set_alpha(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, facecolor=SURFACE)
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
