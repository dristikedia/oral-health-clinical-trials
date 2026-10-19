"""Download oral health trials from the ClinicalTrials.gov API (version 2).

Run from the project folder:
    python src/01_download_trials.py
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
API_URL = "https://clinicaltrials.gov/api/v2/studies"
SEARCH_TERMS = ["periodontitis", "dental caries", "oral cancer", "tooth loss", "gingivitis"]
FIELDS = [
    "NCTId", "BriefTitle", "Condition", "StudyType", "Phase", "OverallStatus",
    "StartDate", "CompletionDate", "LeadSponsorName", "LeadSponsorClass",
    "HasResults", "EnrollmentCount",
]
PAGE_SIZE = 1000
MAX_PAGES = 50


def build_condition_query(term):
    """Search the condition field for the term and its close variants only.

    EXPANSION[Term] keeps spelling variants and synonyms (for example "caries, dental")
    but stops the API from widening "oral cancer" to every cancer study.
    """
    return f'EXPANSION[Term]"{term}"'


def get_json(url, params, attempts=3, wait_seconds=5, timeout=60):
    """GET a URL and return the JSON body. Retries on network errors and busy servers."""
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 400:
                # A BAD REQUEST WILL NOT FIX ITSELF, SO STOP RIGHT AWAY
                raise RuntimeError(f"The API rejected the request (HTTP 400): {response.text[:300]}")
            last_error = f"HTTP status {response.status_code}"
        except requests.RequestException as error:
            last_error = str(error)

        print(f"  Attempt {attempt} of {attempts} failed: {last_error}")
        if attempt < attempts:
            time.sleep(wait_seconds)

    raise RuntimeError(f"Could not reach {url} after {attempts} attempts. Last error: {last_error}")


def fetch_studies_for_term(term, wait_seconds=5):
    """Download every study for one search term, following the page tokens."""
    params = {
        "query.cond": build_condition_query(term),
        "fields": ",".join(FIELDS),
        "pageSize": PAGE_SIZE,
    }
    studies = []
    for page in range(1, MAX_PAGES + 1):
        body = get_json(API_URL, params, wait_seconds=wait_seconds)
        page_studies = body.get("studies", [])
        studies.extend(page_studies)
        print(f"  {term}: page {page}, {len(page_studies)} studies")

        next_token = body.get("nextPageToken")
        if not next_token:
            return studies
        params["pageToken"] = next_token

    raise RuntimeError(f"Stopped after {MAX_PAGES} pages for '{term}'. Raise MAX_PAGES if this is expected.")


def term_to_filename(term):
    """'dental caries' becomes 'trials_dental_caries.json'."""
    return "trials_" + term.lower().replace(" ", "_") + ".json"


def save_studies(term, studies, raw_dir):
    """Save the studies for one term as a JSON file, with a note of when and how."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "term": term,
        "query": build_condition_query(term),
        "downloaded_on": date.today().isoformat(),
        "study_count": len(studies),
        "studies": studies,
    }
    path = raw_dir / term_to_filename(term)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def count_with_default_expansion(term, raw_dir, wait_seconds=5):
    """Record how many studies the same term finds WITHOUT EXPANSION[Term].

    This documents why the project narrows the search: the default search widens
    some terms (such as "oral cancer") to many unrelated studies.
    """
    params = {"query.cond": term, "countTotal": "true", "pageSize": 1, "fields": "NCTId"}
    body = get_json(API_URL, params, wait_seconds=wait_seconds)
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "term": term,
        "query": term,
        "downloaded_on": date.today().isoformat(),
        "total_count_default_expansion": body.get("totalCount", 0),
    }
    path = raw_dir / ("check_default_expansion_" + term.lower().replace(" ", "_") + ".json")
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload["total_count_default_expansion"]


def main():
    total = 0
    for term in SEARCH_TERMS:
        print(f"Searching ClinicalTrials.gov for: {term}")
        try:
            studies = fetch_studies_for_term(term)
        except RuntimeError as error:
            print(f"ERROR: {error}")
            print("Fix: check your internet connection and try again in a few minutes.")
            sys.exit(1)

        if not studies:
            print(f"  WARNING: no studies found for '{term}'.")
        path = save_studies(term, studies, RAW_DIR)
        total += len(studies)
        print(f"  Saved {len(studies)} studies to {path}")

    if total == 0:
        print("ERROR: the API returned no studies for any term. Nothing to analyze.")
        sys.exit(1)

    # FOR THE README: HOW MANY STUDIES "oral cancer" FINDS WITH THE API'S DEFAULT EXPANSION
    try:
        wide = count_with_default_expansion("oral cancer", RAW_DIR)
        print(f"Check: 'oral cancer' with default expansion finds {wide} studies.")
    except RuntimeError as error:
        print(f"WARNING: could not run the expansion check: {error}")
    print(f"Done. {total} study records saved (one trial can match more than one term).")


if __name__ == "__main__":
    main()
