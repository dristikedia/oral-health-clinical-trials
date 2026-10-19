import pandas as pd
import pytest

from conftest import load_script

charts = load_script("04_make_charts.py")


def test_horizontal_bar_chart_saves_file(tmp_path):
    path = tmp_path / "chart.png"
    charts.horizontal_bar_chart(["A", "B"], [3, 1], ["3", "1"], "Title", "Trials", path)
    assert path.exists() and path.stat().st_size > 1000


def test_results_chart_skips_small_groups(tmp_path):
    df = pd.DataFrame({
        "sponsor_type": ["Industry", "Individual"],
        "completed_trials": [100, 2],
        "with_results": [30, 0],
        "percent_with_results": [30.0, 0.0],
    })
    path = tmp_path / "results.png"
    charts.chart_results_posting(df, path)
    assert path.exists()


def test_main_exits_when_tables_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(charts, "TABLES_DIR", tmp_path)
    with pytest.raises(SystemExit):
        charts.main()
    assert "run  python src/03_analyze_trials.py  first" in capsys.readouterr().out
