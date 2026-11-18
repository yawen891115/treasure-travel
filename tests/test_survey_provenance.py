import importlib.util
from pathlib import Path

import pandas as pd


def load_script(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_csv_is_not_real_survey(tmp_path, monkeypatch):
    mod = load_script('survey_to_requests.py')
    original = Path(__file__).resolve().parents[1] / 'survey' / 'sample_responses.csv'
    (tmp_path / 'survey').mkdir()
    target = tmp_path / 'survey' / 'sample_responses.csv'
    target.write_bytes(original.read_bytes())

    class Index:
        def find_by_name(self, name):
            return {'name': name, 'lat': 1.0, 'lng': 2.0}

    monkeypatch.setattr(mod, 'PlaceIndex', Index)
    monkeypatch.chdir(tmp_path)
    mod.main(target)
    text = (tmp_path / 'survey' / 'requests_from_survey.jsonl').read_text()
    assert '"source": "synthetic_example"' in text
    assert '"source": "survey"' not in text


def test_missing_origin_is_not_silently_replaced(tmp_path, monkeypatch):
    mod = load_script('survey_to_requests.py')
    original = Path(__file__).resolve().parents[1] / 'survey' / 'sample_responses.csv'
    (tmp_path / 'survey').mkdir()
    target = tmp_path / 'survey' / 'sample_responses.csv'
    pd.read_csv(original).iloc[:1].to_csv(target, index=False)

    class Index:
        def find_by_name(self, name):
            return None

    monkeypatch.setattr(mod, 'PlaceIndex', Index)
    monkeypatch.chdir(tmp_path)
    mod.main(target)
    assert not (tmp_path / 'survey' / 'requests_from_survey.jsonl').read_text().strip()
