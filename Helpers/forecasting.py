"""Leakage-safe chronological forecasting utilities."""

from dataclasses import dataclass
from pathlib import Path
import json

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


@dataclass(frozen=True)
class ForecastResult:
    target: str
    predictions: pd.DataFrame
    metrics: dict[str, float]
    model: object


def _features(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    result["hour"] = timestamps.hour
    result["day_of_week"] = timestamps.dayofweek
    result["lag_1"] = frame[target].shift(1)
    result["lag_24"] = frame[target].shift(24)
    return result


def forecast_target(
    frame: pd.DataFrame,
    target: str,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    random_state: int = 42,
) -> ForecastResult:
    """Train a modest model and evaluate it on the chronological test tail."""

    if target not in frame or "timestamp" not in frame:
        raise ValueError(f"frame must contain timestamp and {target}")
    ordered = frame.sort_values("timestamp").reset_index(drop=True).copy()
    features = _features(ordered, target)
    valid = features.notna().all(axis=1)
    n = len(ordered)
    train_end = int(n * train_fraction)
    validation_end = int(n * (train_fraction + validation_fraction))
    if train_end < 2 or validation_end <= train_end or validation_end >= n:
        raise ValueError("chronological dataset must contain enough rows for 70/15/15 splits")
    train_rows = valid & (ordered.index < train_end)
    validation_rows = valid & (ordered.index >= train_end) & (ordered.index < validation_end)
    test_rows = valid & (ordered.index >= validation_end)
    if train_rows.sum() < 2 or test_rows.sum() < 1:
        raise ValueError("insufficient valid lagged rows for training or testing")
    model = RandomForestRegressor(n_estimators=100, random_state=random_state, n_jobs=1)
    model.fit(features.loc[train_rows], ordered.loc[train_rows, target])
    validation_predictions = model.predict(features.loc[validation_rows]) if validation_rows.any() else []
    validation_actual = ordered.loc[validation_rows, target].to_numpy(dtype=float)

    # Only observations known before the test tail may enter test features.
    # Test-period actual values remain available solely for final scoring.
    recursive_values = ordered[target].copy()
    recursive_values.loc[test_indices := ordered.index[test_rows].tolist()] = float("nan")
    predictions = []
    for index in test_indices:
        row_timestamp = pd.Timestamp(ordered.loc[index, "timestamp"])
        lag_1_index = index - 1
        lag_24_index = index - 24
        lag_1 = float(recursive_values.loc[lag_1_index]) if lag_1_index in recursive_values.index else float("nan")
        lag_24 = float(recursive_values.loc[lag_24_index]) if lag_24_index in recursive_values.index else float("nan")
        feature_row = pd.DataFrame(
            [{
                "hour": row_timestamp.hour,
                "day_of_week": row_timestamp.dayofweek,
                "lag_1": lag_1,
                "lag_24": lag_24,
            }]
        )
        predicted = float(model.predict(feature_row)[0])
        predictions.append(predicted)
        recursive_values.loc[index] = predicted
    predictions = pd.Series(predictions, dtype=float).to_numpy()
    actual = ordered.loc[test_rows, target].to_numpy(dtype=float)
    result = pd.DataFrame(
        {
            "timestamp": ordered.loc[test_rows, "timestamp"].to_numpy(),
            "actual": actual,
            "predicted": predictions,
            "persistence": ordered[target].shift(24).loc[test_rows].fillna(
                ordered[target].shift(1).loc[test_rows]
            ).to_numpy(dtype=float),
        }
    )
    persistence = result["persistence"].fillna(result["actual"].mean())
    metrics = {
        "model_mae": float(mean_absolute_error(result.actual, result.predicted)),
        "model_rmse": float(mean_squared_error(result.actual, result.predicted) ** 0.5),
        "persistence_mae": float(mean_absolute_error(result.actual, persistence)),
        "persistence_rmse": float(mean_squared_error(result.actual, persistence) ** 0.5),
        "validation_model_mae": (
            float(mean_absolute_error(validation_actual, validation_predictions))
            if len(validation_actual)
            else None
        ),
        "validation_model_rmse": (
            float(mean_squared_error(validation_actual, validation_predictions) ** 0.5)
            if len(validation_actual)
            else None
        ),
        "train_fraction": float(train_fraction),
        "validation_fraction": float(validation_fraction),
        "test_fraction": float(1.0 - train_fraction - validation_fraction),
        "train_end": pd.Timestamp(
        ordered.loc[min(train_end - 1, n - 1), "timestamp"]
        ).isoformat(),
        "validation_end": pd.Timestamp(
        ordered.loc[validation_end - 1, "timestamp"]
        ).isoformat(),
        "test_start": pd.Timestamp(
        ordered.loc[test_indices[0], "timestamp"]
        ).isoformat(),
        "test_end": pd.Timestamp(
        ordered.loc[test_indices[-1], "timestamp"]
        ).isoformat(),
        "model": "RandomForestRegressor(n_estimators=100, random_state=42)",
    }
    return ForecastResult(target=target, predictions=result, metrics=metrics, model=model)


def save_forecast_artifacts(result: ForecastResult, output_dir: str | Path) -> None:
    """Save predictions and an actual-versus-predicted plot."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.predictions.to_csv(output / f"{result.target}_forecast.csv", index=False)
    (output / f"{result.target}_forecast_metrics.json").write_text(
        json.dumps(
            {
                "target": result.target,
                "metrics": result.metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    figure, axis = plt.subplots(figsize=(10, 4))
    result.predictions.plot(x="timestamp", y=["actual", "predicted"], ax=axis)
    axis.set_title(f"{result.target}: actual versus predicted")
    axis.set_ylabel(result.target)
    figure.tight_layout()
    figure.savefig(output / f"{result.target}_forecast.png", dpi=150)
    plt.close(figure)
