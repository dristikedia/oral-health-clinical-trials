import pandas as pd
import pytest

from conftest import load_script

clean = load_script("02_clean_trials.py")


def test_flatten_study_handles_missing_sections():
    row = clean.flatten_study({"protocolSection": {"identificationModule": {"nctId": "NCT1"}}})
    assert row["nct_id"] == "NCT1"
    assert row["conditions"] == ""
    assert row["phases"] == ""
    assert row["has_results"] is False


@pytest.mark.parametrize("phases, study_type, expected", [
    ("PHASE3", "INTERVENTIONAL", "Phase 3"),
    ("PHASE2+PHASE3", "INTERVENTIONAL", "Phase 2/3"),
    ("NA", "INTERVENTIONAL", "Not applicable"),
    ("", "OBSERVATIONAL", "Observational (no phase)"),
    ("", "INTERVENTIONAL", "Not reported"),
    ("PHASE5", "INTERVENTIONAL", "Other: PHASE5"),
])
def test_phase_label(phases, study_type, expected):
    assert clean.phase_label(phases, study_type) == expected


@pytest.mark.parametrize("text, expected", [
    ("2019-03", 2019), ("2021-06-01", 2021), (None, None), ("", None), ("unknown", None),
])
def test_year_from_date(text, expected):
    assert clean.year_from_date(text) == expected


def test_build_clean_table_removes_duplicates_and_keeps_both_terms(fixtures_dir):
    df = clean.build_clean_table(clean.read_raw_files(fixtures_dir))
    assert len(df) == 4
    assert df["nct_id"].is_unique
    shared = df.set_index("nct_id").loc["NCT00000002"]
    assert shared["matched_terms"] == "gingivitis; periodontitis"


def test_build_clean_table_labels(fixtures_dir):
    df = clean.build_clean_table(clean.read_raw_files(fixtures_dir)).set_index("nct_id")
    assert df.at["NCT00000001", "sponsor_type"] == "Industry"
    assert df.at["NCT00000001", "start_year"] == 2019
    assert df.at["NCT00000004", "phase_label"] == "Phase 2/3"
    assert pd.isna(df.at["NCT00000003", "start_year"])


def test_build_clean_table_with_no_studies():
    df = clean.build_clean_table([("gingivitis", "2026-10-17", [])])
    assert df.empty
    assert "matched_terms" in df.columns and "start_year" in df.columns


def test_main_exits_when_raw_files_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(clean, "RAW_DIR", tmp_path)
    with pytest.raises(SystemExit):
        clean.main()
    assert "run  python src/01_download_trials.py  first" in capsys.readouterr().out


def test_main_exits_when_files_have_no_studies(tmp_path, monkeypatch, capsys):
    (tmp_path / "trials_x.json").write_text('{"term": "x", "downloaded_on": "2026-10-17", "studies": []}')
    monkeypatch.setattr(clean, "RAW_DIR", tmp_path)
    with pytest.raises(SystemExit):
        clean.main()
    assert "contain no studies" in capsys.readouterr().out
