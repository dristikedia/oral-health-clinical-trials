"""Count trials by year, phase, status, and sponsor, and check how many completed
trials posted results. Saves tables and writes results/summary.md.

Run from the project folder:
    python src/03_analyze_trials.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
CLEAN_PATH = PROJECT_DIR / "data" / "processed" / "trials_clean.csv"
RAW_DIR = PROJECT_DIR / "data" / "raw"
TABLES_DIR = PROJECT_DIR / "results" / "tables"
SUMMARY_PATH = PROJECT_DIR / "results" / "summary.md"
FIRST_YEAR = 2000

STATUS_LABELS = {
    "COMPLETED": "Completed",
    "UNKNOWN": "Unknown (not updated in 2+ years)",
    "RECRUITING": "Recruiting",
    "NOT_YET_RECRUITING": "Not yet recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn",
    "SUSPENDED": "Suspended",
}
PHASE_ORDER = [
    "Early phase 1", "Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3",
    "Phase 3", "Phase 4", "Not applicable", "Not reported",
]


def load_clean_table(path):
    """Read the clean table made by 02_clean_trials.py."""
    df = pd.read_csv(path, dtype={"nct_id": str})
    df["start_year"] = df["start_year"].astype("Int64")
    df["has_results"] = df["has_results"].astype(bool)
    return df


def reference_year(df):
    """The year the data was downloaded. Later start years are planned, not real yet."""
    return int(str(df["downloaded_on"].dropna().max())[:4])


def count_with_percent(series, name):
    """Count each value and add a percent column."""
    table = series.value_counts().rename_axis(name).reset_index(name="trials")
    table["percent"] = (100 * table["trials"] / table["trials"].sum()).round(1)
    return table


def trials_per_year(df, first_year, last_year):
    """Trials by start year, with every year shown even if it has zero trials."""
    years = pd.DataFrame({"start_year": range(first_year, last_year + 1)})
    counts = df["start_year"].value_counts().rename_axis("start_year").reset_index(name="trials")
    counts["start_year"] = counts["start_year"].astype(int)
    table = years.merge(counts, on="start_year", how="left").fillna({"trials": 0})
    table["trials"] = table["trials"].astype(int)
    table["is_partial_year"] = (table["start_year"] == last_year).astype(int)
    return table


def phase_table(df):
    """Phase counts for interventional trials only. Observational studies have no phase."""
    interventional = df[df["study_type"] == "INTERVENTIONAL"]
    table = count_with_percent(interventional["phase_label"], "phase")
    order = {phase: i for i, phase in enumerate(PHASE_ORDER)}
    table["order"] = table["phase"].map(order).fillna(len(PHASE_ORDER))
    return table.sort_values("order").drop(columns="order").reset_index(drop=True)


def status_table(df):
    """Trials per recruitment status, with readable labels."""
    labels = df["overall_status"].map(STATUS_LABELS).fillna(df["overall_status"])
    return count_with_percent(labels, "status")


def sponsor_table(df):
    """Trials per lead sponsor type."""
    return count_with_percent(df["sponsor_type"], "sponsor_type")


def results_posting(df, group_column):
    """Among completed trials: how many posted results, overall share by group."""
    completed = df[df["overall_status"] == "COMPLETED"]
    if completed.empty:
        return pd.DataFrame(columns=[group_column, "completed_trials", "with_results", "percent_with_results"])
    table = completed.groupby(group_column).agg(
        completed_trials=("nct_id", "count"),
        with_results=("has_results", "sum"),
    ).reset_index()
    table["with_results"] = table["with_results"].astype(int)
    table["percent_with_results"] = (100 * table["with_results"] / table["completed_trials"]).round(1)
    return table.sort_values("completed_trials", ascending=False).reset_index(drop=True)


def results_overall(df):
    """Completed trials, how many posted results, and the percent."""
    completed = df[df["overall_status"] == "COMPLETED"]
    total = len(completed)
    with_results = int(completed["has_results"].sum())
    percent = round(100 * with_results / total, 1) if total else 0.0
    return total, with_results, percent


def trials_per_term(df):
    """How many trials matched each search term (a trial can match several)."""
    terms = df["matched_terms"].str.split("; ").explode()
    return count_with_percent(terms, "search_term").drop(columns="percent")


def expansion_check_lines(raw_dir, df):
    """Sentences comparing the narrowed search with the API's default expansion, if the check file exists."""
    lines = []
    for path in sorted(Path(raw_dir).glob("check_default_expansion_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        term = payload["term"]
        narrowed = int(df["matched_terms"].str.split("; ").explode().eq(term).sum())
        lines.append(
            f"Search check: '{term}' with the API's default expansion finds "
            f"{payload['total_count_default_expansion']:,} studies; with EXPANSION[Term] it finds {narrowed:,}."
        )
    return lines


def to_markdown_table(df):
    """Turn a DataFrame into a simple Markdown table (no extra packages needed)."""
    if df.empty:
        return "_No rows._"
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    divider = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = []
    # ASTYPE(OBJECT) KEEPS WHOLE NUMBERS LOOKING LIKE 8 INSTEAD OF 8.0
    for row in df.astype(object).values.tolist():
        cells = ["" if pd.isna(value) else str(value) for value in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, divider] + rows)


def key_findings(df, tables, overall):
    """Plain-language sentences built from the numbers."""
    lines = []
    year_table = tables["trials_per_year"]
    complete_years = year_table[year_table["is_partial_year"] == 0]
    peak = complete_years.loc[complete_years["trials"].idxmax()]
    lines.append(
        f"{len(df)} unique trials were found. The busiest complete start year was "
        f"{int(peak['start_year'])} with {int(peak['trials'])} trials."
    )

    phases = tables["by_phase"].set_index("phase")
    interventional = int(phases["trials"].sum())
    if "Not applicable" in phases.index:
        lines.append(
            f"Of {interventional} interventional trials, {phases.at['Not applicable', 'trials']} "
            f"({phases.at['Not applicable', 'percent']}%) have no drug phase (\"Not applicable\"), "
            f"which is typical of device, procedure, and behavioral studies."
        )

    total, with_results, percent = overall
    lines.append(f"{with_results} of {total} completed trials ({percent}%) have results posted on ClinicalTrials.gov.")

    sponsor = tables["results_by_sponsor"].set_index("sponsor_type")
    for group in ["Industry", "University, hospital, or other"]:
        if group in sponsor.index:
            lines.append(
                f"{group}: {sponsor.at[group, 'with_results']} of {sponsor.at[group, 'completed_trials']} "
                f"completed trials ({sponsor.at[group, 'percent_with_results']}%) posted results."
            )
    return lines


def main():
    if not CLEAN_PATH.exists():
        print(f"ERROR: clean table not found at {CLEAN_PATH}")
        print("Fix: run  python src/01_download_trials.py  then  python src/02_clean_trials.py")
        sys.exit(1)

    df = load_clean_table(CLEAN_PATH)
    if df.empty:
        print("ERROR: the clean table has no trials. Nothing to analyze.")
        sys.exit(1)

    # BUILD EVERY TABLE
    last_year = reference_year(df)
    tables = {
        "trials_per_year": trials_per_year(df, FIRST_YEAR, last_year),
        "by_phase": phase_table(df),
        "by_status": status_table(df),
        "by_sponsor": sponsor_table(df),
        "results_by_sponsor": results_posting(df, "sponsor_type"),
        "results_by_study_type": results_posting(df, "study_type"),
        "trials_per_term": trials_per_term(df),
    }
    overall = results_overall(df)

    # SAVE TABLES
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False)

    # WRITE THE SUMMARY
    missing_year = int(df["start_year"].isna().sum())
    before = int((df["start_year"] < FIRST_YEAR).sum())
    planned = int((df["start_year"] > last_year).sum())
    parts = [
        "# Results summary",
        "",
        f"Generated automatically by src/03_analyze_trials.py. Data downloaded on {df['downloaded_on'].max()}.",
        "",
        "## Key numbers",
        "",
    ]
    parts += [f"- {line}" for line in key_findings(df, tables, overall)]
    raw_records = int(tables["trials_per_term"]["trials"].sum())
    parts.append(f"- The five searches returned {raw_records:,} records before duplicates were removed.")
    parts += [f"- {line}" for line in expansion_check_lines(RAW_DIR, df)]
    parts += [
        "",
        f"Start year chart covers {FIRST_YEAR} to {last_year} ({last_year} is partial). "
        f"Not shown: {before} trials starting before {FIRST_YEAR}, {planned} with planned start dates after "
        f"{last_year}, and {missing_year} with no start date.",
        "",
    ]
    for name, table in tables.items():
        parts += [f"## {name}", "", to_markdown_table(table), ""]
    SUMMARY_PATH.write_text("\n".join(parts), encoding="utf-8")

    for name in tables:
        print(f"Saved results/tables/{name}.csv")
    print("Summary written to results/summary.md")


if __name__ == "__main__":
    main()
