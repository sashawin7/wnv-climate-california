"""Scatter of weekly WNV cases against same-week humidity in one county, with LOWESS smooths.

One point per week with at least one case, over the whole analysis period, in three
panels: rmin, rmax (relative humidity, %) and sph (specific humidity, g/kg). The
panels share the case axis but not the humidity axis, since the units differ.
Cases are on a log axis with slight vertical jitter, as in plot_temperature_cases.

Run from the project root:  python -m src.plot_humidity_cases ["County Name"]
Output: outputs/figures/humidity_vs_cases_<county>.png
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess

from src.config import CA_COUNTIES, PROCESSED, ROOT

DATA = PROCESSED / "ca_wnv_weather_weekly.csv"
DEFAULT_COUNTY = "Los Angeles"  # the county with the most weeks with cases

PANELS = [
    ("rmin", "Daily minimum relative humidity (%)", 1),
    ("rmax", "Daily maximum relative humidity (%)", 1),
    ("sph", "Specific humidity (g/kg)", 1000),  # stored as kg/kg
]
POINT = "#2a78d6"  # categorical slot 1 of the reference palette
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def main() -> None:
    county = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_COUNTY
    if county not in CA_COUNTIES:
        raise SystemExit(f"Unknown county {county!r}; use a name like 'Los Angeles'")
    out = ROOT / "outputs" / "figures" / f"humidity_vs_cases_{county.lower().replace(' ', '_')}.png"

    d = pd.read_csv(DATA)
    d = d[(d["county"] == county) & (d["wnv_cases"] > 0)]
    first, last = d["mmwr_year"].min(), d["mmwr_year"].max()

    rng = np.random.default_rng(0)
    jitter = np.exp(rng.uniform(-0.08, 0.08, len(d)))  # +/- 8%, symmetric on a log axis
    cases_max = d["wnv_cases"].max()
    yticks = [t for t in [1, 2, 5, 10, 20, 40, 80] if t <= cases_max * 1.2]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), dpi=150, sharey=True, facecolor=SURFACE)
    for ax, (col, label, scale) in zip(axes, PANELS):
        sub = d[d[col].notna()]
        x = sub[col] * scale
        ax.set_facecolor(SURFACE)
        ax.scatter(x, sub["wnv_cases"] * jitter[d[col].notna().values], s=16, color=POINT,
                   alpha=0.4, linewidths=0)
        fit = lowess(sub["wnv_cases"], x, frac=0.5)
        ax.plot(fit[:, 0], fit[:, 1], color=SURFACE, linewidth=4.5)  # surface ring
        ax.plot(fit[:, 0], fit[:, 1], color=POINT, linewidth=2.2)

        ax.set_yscale("log")
        ax.set_yticks(yticks)
        ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel(label, color=INK_2, fontsize=9)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
        for side in ["left", "bottom"]:
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK_2, labelsize=9)
    axes[0].set_ylabel("WNV cases in the week (log scale)", color=INK_2)

    fig.suptitle(f"{county} County: WNV cases vs. same-week humidity, weeks with ≥1 case, "
                 f"{first}–{last}", x=0.01, ha="left", color=INK, fontsize=12,
                 fontweight="bold")
    fig.text(0.01, 0.905, f"{len(d):,} weeks, {d['wnv_cases'].sum():,} cases. "
             "Lines are LOWESS smooths (frac 0.5) of cases on humidity.",
             fontsize=8.5, color=INK_2, ha="left")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(out, facecolor=SURFACE)
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
