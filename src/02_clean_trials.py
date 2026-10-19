"""Turn the raw JSON downloads into one clean table with one row per trial.

Run from the project folder:
    python src/02_clean_trials.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
CLEAN_PATH = PROJECT_DIR / "data" / "processed" / "trials_clean.csv"

PHASE_LABELS = {
    "EARLY_PHASE1": "Early phase 1",
    "PHASE1": "Phase 1",
    "PHASE1+PHASE2": "Phase 1/2",
    "PHASE2": "Phase 2",
    "PHASE2+PHASE3": "Phase 2/3",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "Not applicable",
}

SPONSOR_LABELS = {
    "INDUSTRY": "Industry",
    "OTHER": "University, hospital, or other",
    "NIH": "US NIH",
    "FED": "Government",
    "OTHER_GOV": "Government",
    "NETWORK": "Research network",
    "INDIV": "Individual",
    "UNKNOWN": "Unknown",
}


def flatten_study(study):
    """Pull the fields we need out of one nested study record."""
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    design = protocol.get("designModule", {})
    conditions = protocol.get("conditionsModule", {}).get("conditions", [])

    return {
        "nct_id": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "conditions": "; ".join(conditions),
        "study_type": design.get("studyType"),
        "phases": "+".join(design.get("phases", [])),
        "overall_status": status.get("overallStatus"),
        "start_date": status.get("startDateStruct", {}).get("date"),
        "completion_date": status.get("completionDateStruct", {}).get("date"),
        "sponsor_name": sponsor.get("name"),
        "sponsor_class": sponsor.get("class"),
        "has_results": study.get("hasResults", False),
        "enrollment": design.get("enrollmentInfo", {}).get("count"),
    }


def phase_label(phases, study_type):
    """Give each trial a readable phase label."""
    if phases in PHASE_LABELS:
        return PHASE_LABELS[phases]
    if phases == "" and study_type == "OBSERVATIONAL":
        return "Observational (no phase)"
    if phases == "":
        return "Not reported"
    return "Other: " + phases


def year_from_date(text):
    """'2024-04' or '2024-04-20' becomes 2024. Missing or odd values become None."""
    if not isinstance(text, str) or len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


def read_raw_files(raw_dir):
    """Read every trials_*.json file. Returns a list of (term, download date, studies)."""
    files = sorted(Path(raw_dir).glob("trials_*.json"))
    loaded = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        loaded.append((payload["term"], payload.get("downloaded_on"), payload.get("studies", [])))
    return loaded


def build_clean_table(loaded):
    """Make one row per trial. A trial found by two search terms is kept once,
    with both terms listed in matched_terms."""
    rows = []
    for term, downloaded_on, studies in loaded:
        for study in studies:
            row = flatten_study(study)
            row["downloaded_on"] = downloaded_on
            row["matched_term"] = term
            rows.append(row)

    columns = list(flatten_study({}).keys()) + ["downloaded_on", "matched_term"]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        # NO STUDIES: RETURN AN EMPTY TABLE THAT STILL HAS ALL THE FINAL COLUMNS
        extra_columns = ["downloaded_on", "matched_terms", "phase_label", "sponsor_type", "start_year"]
        final_columns = list(flatten_study({}).keys()) + extra_columns
        return pd.DataFrame(columns=final_columns)

    # DROP RECORDS WITHOUT AN ID, THEN COMBINE THE MATCHED TERMS FOR EACH TRIAL
    df = df[df["nct_id"].notna()]
    terms = df.groupby("nct_id")["matched_term"].apply(lambda values: "; ".join(sorted(set(values))))
    df = df.drop_duplicates(subset="nct_id").drop(columns=["matched_term"])
    df["matched_terms"] = df["nct_id"].map(terms)

    # ADD READABLE LABELS AND THE START YEAR
    df["phase_label"] = [phase_label(p, t) for p, t in zip(df["phases"], df["study_type"])]
    df["sponsor_type"] = df["sponsor_class"].map(SPONSOR_LABELS).fillna("Unknown")
    df["start_year"] = df["start_date"].apply(year_from_date).astype("Int64")
    df["has_results"] = df["has_results"].astype(bool)
    return df.sort_values("nct_id").reset_index(drop=True)


def main():
    loaded = read_raw_files(RAW_DIR)
    if not loaded:
        print(f"ERROR: no trials_*.json files found in {RAW_DIR}")
        print("Fix: run  python src/01_download_trials.py  first.")
        sys.exit(1)

    df = build_clean_table(loaded)
    if df.empty:
        print("ERROR: the downloaded files contain no studies. Nothing to clean.")
        sys.exit(1)

    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_PATH, index=False)
    raw_rows = sum(len(studies) for _, _, studies in loaded)
    print(f"Read {raw_rows} study records, kept {len(df)} unique trials.")
    print(f"Clean table written to {CLEAN_PATH.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    main()
