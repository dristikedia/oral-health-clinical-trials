"""Draw five charts from the tables made by 03_analyze_trials.py.

Run from the project folder:
    python src/04_make_charts.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # DRAW TO FILES, NO WINDOW NEEDED
import matplotlib.pyplot as plt
import pandas as pd

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
TABLES_DIR = PROJECT_DIR / "results" / "tables"
CHARTS_DIR = PROJECT_DIR / "results" / "charts"
BLUE = "#2a78d6"
LIGHT_BLUE = "#a9c8ee"
GREY = "#8a8985"
TEXT = "#52514e"
NEEDED_TABLES = ["trials_per_year", "by_phase", "by_status", "by_sponsor", "results_by_sponsor"]


def style_axes(ax, grid_axis="y"):
    """Light, quiet axes so the data stands out."""
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=TEXT)
    ax.grid(axis=grid_axis, color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)


def horizontal_bar_chart(labels, values, value_labels, title, xlabel, path):
    """A horizontal bar chart with the first item at the top and a label on each bar."""
    fig, ax = plt.subplots(figsize=(8.5, 0.45 * len(labels) + 1.6))
    positions = list(range(len(labels)))[::-1]  # FIRST ROW AT THE TOP
    bars = ax.barh(positions, values, color=BLUE, height=0.65)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.bar_label(bars, labels=value_labels, padding=3, color=TEXT, fontsize=9)
    style_axes(ax, grid_axis="x")
    ax.set_xlim(0, max(values) * 1.18 if len(values) else 1)
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_trials_per_year(df, path):
    """Bars of trials per start year; the current (partial) year is lighter."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    complete = df[df["is_partial_year"] == 0]
    partial = df[df["is_partial_year"] == 1]
    ax.bar(complete["start_year"], complete["trials"], color=BLUE, width=0.75)
    ax.bar(partial["start_year"], partial["trials"], color=LIGHT_BLUE, width=0.75,
           label="Current year (partial)")
    style_axes(ax)
    ax.set_xticks(list(df["start_year"])[::2])
    ax.set_ylabel("Trials")
    ax.set_title("Oral health trials by start year", loc="left", fontsize=13)
    if not partial.empty:
        ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_results_posting(df, path):
    """Share of completed trials with posted results, for groups with at least 20 trials."""
    df = df[df["completed_trials"] >= 20].sort_values("percent_with_results", ascending=False)
    labels = [f"{g}\n(n = {n})" for g, n in zip(df["sponsor_type"], df["completed_trials"])]
    value_labels = [f"{p}%" for p in df["percent_with_results"]]
    horizontal_bar_chart(
        labels, df["percent_with_results"].tolist(), value_labels,
        "Completed trials with results posted, by lead sponsor",
        "Percent of completed trials (groups with 20+ completed trials)", path,
    )


def main():
    missing = [name for name in NEEDED_TABLES if not (TABLES_DIR / f"{name}.csv").exists()]
    if missing:
        print(f"ERROR: missing result tables: {', '.join(missing)}")
        print("Fix: run  python src/03_analyze_trials.py  first.")
        sys.exit(1)

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    tables = {name: pd.read_csv(TABLES_DIR / f"{name}.csv") for name in NEEDED_TABLES}

    # 1 TRIALS PER YEAR
    chart_trials_per_year(tables["trials_per_year"], CHARTS_DIR / "01_trials_per_year.png")

    # 2 PHASE (INTERVENTIONAL ONLY)
    phase = tables["by_phase"]
    horizontal_bar_chart(
        phase["phase"].tolist(), phase["trials"].tolist(),
        [f"{t} ({p}%)" for t, p in zip(phase["trials"], phase["percent"])],
        "Interventional trials by phase", "Trials", CHARTS_DIR / "02_trials_by_phase.png",
    )

    # 3 STATUS
    status = tables["by_status"]
    horizontal_bar_chart(
        status["status"].tolist(), status["trials"].tolist(),
        [f"{t} ({p}%)" for t, p in zip(status["trials"], status["percent"])],
        "Trials by recruitment status", "Trials", CHARTS_DIR / "03_trials_by_status.png",
    )

    # 4 SPONSOR TYPE
    sponsor = tables["by_sponsor"]
    horizontal_bar_chart(
        sponsor["sponsor_type"].tolist(), sponsor["trials"].tolist(),
        [f"{t} ({p}%)" for t, p in zip(sponsor["trials"], sponsor["percent"])],
        "Trials by lead sponsor type", "Trials", CHARTS_DIR / "04_trials_by_sponsor.png",
    )

    # 5 RESULTS POSTED
    chart_results_posting(tables["results_by_sponsor"], CHARTS_DIR / "05_results_posted_by_sponsor.png")

    for path in sorted(CHARTS_DIR.glob("*.png")):
        print(f"Saved {path.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    main()
