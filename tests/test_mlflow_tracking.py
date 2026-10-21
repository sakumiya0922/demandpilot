"""Contract tests for optional MLflow experiment tracking."""

import sys
from contextlib import contextmanager
from types import SimpleNamespace

from demandpilot.modeling.mlflow_tracking import log_training_experiment


class RecordingMLflow:
    def __init__(self):
        self.runs = []
        self.current = None
        self.uri = None
        self.experiment = None

    def set_tracking_uri(self, uri):
        self.uri = uri

    def set_experiment(self, name):
        self.experiment = name

    @contextmanager
    def start_run(self, run_name):
        run = {"name": run_name, "params": {}, "metrics": {}, "tags": {}, "artifacts": []}
        self.runs.append(run)
        self.current = run
        try:
            yield
        finally:
            self.current = None

    def log_params(self, params):
        self.current["params"].update(params)

    def log_metrics(self, scores):
        self.current["metrics"].update(scores)

    def set_tags(self, tags):
        self.current["tags"].update(tags)

    def log_artifacts(self, local_dir, artifact_path):
        self.current["artifacts"].append((local_dir, artifact_path))


def _inputs():
    candidate = {"parameters": {"num_leaves": 15, "min_child_samples": 30},
                 "best_iteration": 139, "validation": {"mae": 138.91, "wape": 0.4014}}
    result = {"lightgbm": {"mae": 274.01, "wape": 0.5741},
              "baseline": {"mae": 206.67, "wape": 0.433}}
    evaluation = {
        "candidates": [candidate], "selection_metric": "validation_mae",
        "results": {"validation": {"overall": result}, "test": {"overall": result}},
    }
    conditions = {"horizon_days": 7, "product_codes": ["a", "b"],
                  "selected_parameters": {"num_leaves": 15, "n_estimators": 139}}
    return evaluation, conditions


def test_tracking_disabled_without_uri(monkeypatch, tmp_path):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    evaluation, conditions = _inputs()
    log_training_experiment(evaluation, conditions, tmp_path)


def test_separate_validation_candidates_and_final_test_metrics(monkeypatch, tmp_path):
    fake = RecordingMLflow()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "DemandPilot-test")
    monkeypatch.setitem(sys.modules, "mlflow", fake)
    evaluation, conditions = _inputs()
    log_training_experiment(evaluation, conditions, tmp_path)

    assert fake.uri == "http://mlflow:5000"
    assert fake.experiment == "DemandPilot-test"
    assert [run["name"] for run in fake.runs] == [
        "candidate-1", "selected-model-and-final-refit"
    ]
    candidate, selected = fake.runs
    assert candidate["metrics"]["validation_mae"] == 138.91
    assert not any(key.startswith("test_") for key in candidate["metrics"])
    assert selected["metrics"]["test_lightgbm_mae"] == 274.01
    assert selected["metrics"]["test_baseline_wape"] == 0.433
    assert selected["tags"]["test_used_for_selection"] == "false"
    assert selected["artifacts"] == [(str(tmp_path), "training_outputs")]
