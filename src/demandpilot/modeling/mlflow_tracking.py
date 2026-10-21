"""Log validation candidates and the selected model run to MLflow.

MLflow is opt-in outside Docker Compose: with no MLFLOW_TRACKING_URI, the
existing local training flow and its artifacts remain unchanged.
"""

import os
from pathlib import Path


def _log_scores(mlflow, prefix: str, scores: dict) -> None:
    values = {
        f"{prefix}_{metric}": float(scores[metric])
        for metric in ("mae", "wape")
        if scores.get(metric) is not None
    }
    if values:
        mlflow.log_metrics(values)


def log_training_experiment(evaluation: dict, conditions: dict, output_dir: Path) -> None:
    """Track validation-only search separately from sealed test evaluation.

    The final run logs the saved evaluation model's split metrics and the
    separately refitted final model as distinct named file artifacts.
    """
    uri = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
    if not uri:
        return

    import mlflow

    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_NAME", "DemandPilot"))
    horizon = conditions["horizon_days"]
    product_count = len(conditions["product_codes"])

    # Candidate runs contain validation metrics only: never use the sealed
    # test set for candidate selection.
    for index, candidate in enumerate(evaluation["candidates"], start=1):
        with mlflow.start_run(run_name=f"candidate-{index}"):
            mlflow.log_params({
                "run_type": "candidate",
                "model": "LightGBM",
                "horizon_days": horizon,
                "product_count": product_count,
                **candidate["parameters"],
                "best_iteration": candidate["best_iteration"],
            })
            _log_scores(mlflow, "validation", candidate["validation"])

    selected = conditions["selected_parameters"]
    with mlflow.start_run(run_name="selected-model-and-final-refit"):
        mlflow.log_params({
            "run_type": "selected",
            "model": "LightGBM",
            "horizon_days": horizon,
            "product_count": product_count,
            "selection_metric": evaluation["selection_metric"],
            **selected,
        })
        mlflow.set_tags({
            "evaluation_model": "evaluation_model.txt",
            "final_inference_model": "final_model.txt",
            "test_used_for_selection": "false",
            "future_actuals_available": "false",
        })
        for split in ("validation", "test"):
            overall = evaluation["results"][split]["overall"]
            for model_name in ("lightgbm", "baseline"):
                _log_scores(mlflow, f"{split}_{model_name}", overall[model_name])
        mlflow.log_artifacts(str(output_dir), artifact_path="training_outputs")
