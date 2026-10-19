import pandas as pd
import pytest

from conftest import load_script

clean = load_script("02_clean_trials.py")
analyze = load_script("03_analyze_trials.py")


@pytest.fixture
def trials(fixtures_dir, tmp_path):
    """Clean the fixture files, save them, and read them back the way the script does."""
    path = tmp_path / "clean.csv"
    clean.build_clean_table(clean.read_raw_files(fixtures_dir)).to_csv(path, index=False)
    return analyze.load_clean_table(path)


def test_reference_year(trials):
    assert analyze.reference_year(trials) == 2026


def test_trials_per_year_fills_missing_years(trials):
    table = analyze.trials_per_year(trials, 2018, 2026)
    assert len(table) == 9
    counts = table.set_index("start_year")["trials"]
    assert counts[2018] == 0
    assert counts[2019] == 1
    assert counts[2026] == 1
    assert table["is_partial_year"].tolist()[-1] == 1


def test_phase_table_only_interventional(trials):
    table = analyze.phase_table(trials)
    assert table["trials"].sum() == 3
    assert "Observational (no phase)" not in table["phase"].tolist()
    assert table["phase"].tolist() == ["Phase 2/3", "Phase 3", "Not applicable"]


def test_status_labels(trials):
    table = analyze.status_table(trials).set_index("status")
    assert table.at["Completed", "trials"] == 3
    assert table.at["Recruiting", "percent"] == 25.0


def test_results_posting_by_sponsor(trials):
    table = analyze.results_posting(trials, "sponsor_type").set_index("sponsor_type")
    assert table.at["Industry", "percent_with_results"] == 100.0
    assert table.at["University, hospital, or other", "completed_trials"] == 2
    assert table.at["University, hospital, or other", "with_results"] == 0


def test_results_overall(trials):
    assert analyze.results_overall(trials) == (3, 1, 33.3)


def test_results_posting_with_no_completed_trials(trials):
    recruiting_only = trials[trials["overall_status"] == "RECRUITING"]
    table = analyze.results_posting(recruiting_only, "sponsor_type")
    assert table.empty
    assert analyze.results_overall(recruiting_only) == (0, 0, 0.0)


def test_trials_per_term_counts_shared_trials_twice(trials):
    table = analyze.trials_per_term(trials).set_index("search_term")
    assert table.at["gingivitis", "trials"] == 3
    assert table.at["periodontitis", "trials"] == 2


def test_markdown_table_keeps_whole_numbers():
    assert "| 3 | 33.3 |" in analyze.to_markdown_table(pd.DataFrame({"n": [3], "pct": [33.3]}))


def test_main_exits_when_clean_table_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(analyze, "CLEAN_PATH", tmp_path / "missing.csv")
    with pytest.raises(SystemExit):
        analyze.main()
    assert "clean table not found" in capsys.readouterr().out


def test_expansion_check_lines(trials, tmp_path):
    (tmp_path / "check_default_expansion_gingivitis.json").write_text(
        '{"term": "gingivitis", "total_count_default_expansion": 900}')
    lines = analyze.expansion_check_lines(tmp_path, trials)
    assert lines == ["Search check: 'gingivitis' with the API's default expansion finds 900 studies; "
                     "with EXPANSION[Term] it finds 3."]


def test_expansion_check_lines_without_file(trials, tmp_path):
    assert analyze.expansion_check_lines(tmp_path, trials) == []
