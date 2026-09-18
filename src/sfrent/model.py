"""Hedonic rent model: log(rent_adj) ~ neighborhood + beds + baths + log sqft + age + size.

Ordinary least squares on the modelable listing frame. Each neighborhood gets its own
intercept (full dummy set, no global intercept); the other effects are relative to a baseline
unit (1 bed, 1 bath, 700 sqft, built before 1920, in a 5-19 unit building). The published
``model.json`` carries coefficients, bucket edges, and residual quantiles so the web app can
reproduce predictions client-side: ``rent = exp(neighborhood + sum(effects))``.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from sfrent.config import PUBLIC_DIR

log = logging.getLogger(__name__)

MODEL_PATH = PUBLIC_DIR / "model.json"
BASELINE_SQFT = 700.0
YEAR_EDGES = (1920, 1946, 1980, 2010)
YEAR_LABELS = ("pre_1920", "1920_1945", "1946_1979", "1980_2009", "2010_plus")
UNIT_EDGES = (2, 5, 20, 50)
UNIT_LABELS = ("1", "2_4", "5_19", "20_49", "50_plus")
BASELINE = {"bedrooms": 1, "bathrooms": 1.0, "year_built": "pre_1920", "building_units": "5_19"}
MIN_NEIGHBORHOOD_N = 30
HOLDOUT_FRACTION = 0.2


def bucket(value: float | None, edges: tuple[int, ...], labels: tuple[str, ...]) -> str:
    if value is None:
        return "unknown"
    for edge, label in zip(edges, labels, strict=False):
        if value < edge:
            return label
    return labels[-1]


def _bath_label(value: float | None) -> str:
    if value is None:
        return "1"
    value = min(value, 3.0)
    return str(int(value)) if value == int(value) else str(value)


def design_matrix(frame: pl.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Columns: one per neighborhood, then effect dummies and log-sqft terms."""
    rows = frame.select(
        "analysis_neighborhood", "bedrooms", "bathrooms", "sqft", "year_built", "building_units"
    ).to_dicts()
    neighborhoods = sorted({r["analysis_neighborhood"] for r in rows})
    columns = [f"nhood:{n}" for n in neighborhoods]
    columns += [f"bedrooms:{b}" for b in (0, 2, 3, 4, 5)]
    columns += [f"bathrooms:{b}" for b in ("0", "1.5", "2", "2.5", "3")]
    columns += ["log_sqft", "sqft_missing"]
    columns += [f"year_built:{label}" for label in (*YEAR_LABELS[1:], "unknown")]
    columns += [f"building_units:{label}" for label in ("1", "2_4", "20_49", "50_plus", "unknown")]
    index = {name: i for i, name in enumerate(columns)}

    matrix = np.zeros((len(rows), len(columns)))
    for i, r in enumerate(rows):
        matrix[i, index[f"nhood:{r['analysis_neighborhood']}"]] = 1.0
        for key in (
            f"bedrooms:{min(r['bedrooms'], 5)}",
            f"bathrooms:{_bath_label(r['bathrooms'])}",
            f"year_built:{bucket(r['year_built'], YEAR_EDGES, YEAR_LABELS)}",
            f"building_units:{bucket(r['building_units'], UNIT_EDGES, UNIT_LABELS)}",
        ):
            if key in index:  # baseline categories have no column
                matrix[i, index[key]] = 1.0
        if r["sqft"]:
            matrix[i, index["log_sqft"]] = math.log(r["sqft"] / BASELINE_SQFT)
        else:
            matrix[i, index["sqft_missing"]] = 1.0
    return matrix, columns


def _prepare(listings: pl.DataFrame) -> pl.DataFrame:
    rent = "rent_adj" if "rent_adj" in listings.columns else "rent"
    frame = listings.filter(pl.col("is_modelable") & (pl.col(rent) > 0)).with_columns(
        pl.col(rent).log().alias("_y")
    )
    counts = frame.group_by("analysis_neighborhood").len()
    keep = counts.filter(pl.col("len") >= MIN_NEIGHBORHOOD_N)["analysis_neighborhood"].to_list()
    return frame.filter(pl.col("analysis_neighborhood").is_in(keep))


def _fit(matrix: np.ndarray, y: np.ndarray) -> np.ndarray:
    coef, *_ = np.linalg.lstsq(matrix, y, rcond=None)
    return coef


def fit(listings: pl.DataFrame, seed: int = 7) -> dict[str, Any]:
    frame = _prepare(listings)
    matrix, columns = design_matrix(frame)
    y = frame["_y"].to_numpy()

    rng = np.random.default_rng(seed)
    holdout = rng.random(len(y)) < HOLDOUT_FRACTION
    coef_train = _fit(matrix[~holdout], y[~holdout])
    pred = np.exp(matrix[holdout] @ coef_train)
    actual = np.exp(y[holdout])
    holdout_mae = float(np.mean(np.abs(pred - actual)))
    holdout_mape = float(np.mean(np.abs(pred - actual) / actual))

    coef = _fit(matrix, y)
    fitted = matrix @ coef
    residuals = y - fitted
    r2 = float(1 - np.sum(residuals**2) / np.sum((y - y.mean()) ** 2))
    by_name = dict(zip(columns, coef.tolist(), strict=True))

    grouped: dict[str, dict[str, float]] = {}
    for name, value in by_name.items():
        group, _, level = name.partition(":")
        if level:
            grouped.setdefault(group, {})[level] = round(value, 5)
    neighborhood_n = dict(frame.group_by("analysis_neighborhood").len().iter_rows())

    return {
        "target": "log_rent_adj",
        "n": int(frame.height),
        "fit": {
            "r2": round(r2, 4),
            "holdout_mae": round(holdout_mae, 1),
            "holdout_mape": round(holdout_mape, 4),
            "residual_std": round(float(residuals.std()), 4),
        },
        "baseline": {**BASELINE, "sqft": BASELINE_SQFT},
        "buckets": {
            "year_built": {"edges": list(YEAR_EDGES), "labels": list(YEAR_LABELS)},
            "building_units": {"edges": list(UNIT_EDGES), "labels": list(UNIT_LABELS)},
        },
        "neighborhoods": grouped.pop("nhood"),
        "neighborhood_n": neighborhood_n,
        "coefficients": {
            **grouped,
            "log_sqft": round(by_name["log_sqft"], 5),
            "sqft_missing": round(by_name["sqft_missing"], 5),
        },
        "residual_quantiles": {
            f"p{q}": round(float(np.quantile(residuals, q / 100)), 5) for q in (10, 25, 75, 90)
        },
    }


def predict(model: dict[str, Any], **unit: Any) -> float:
    """Reference implementation of the client-side formula (used by tests)."""
    c = model["coefficients"]
    total = model["neighborhoods"][unit["analysis_neighborhood"]]
    total += c["bedrooms"].get(str(min(unit.get("bedrooms", 1), 5)), 0.0)
    total += c["bathrooms"].get(_bath_label(unit.get("bathrooms")), 0.0)
    sqft = unit.get("sqft")
    total += c["log_sqft"] * math.log(sqft / BASELINE_SQFT) if sqft else c["sqft_missing"]
    total += c["year_built"].get(bucket(unit.get("year_built"), YEAR_EDGES, YEAR_LABELS), 0.0)
    total += c["building_units"].get(
        bucket(unit.get("building_units"), UNIT_EDGES, UNIT_LABELS), 0.0
    )
    return math.exp(total)


def fit_and_publish(listings: pl.DataFrame, path: Path = MODEL_PATH) -> dict[str, Any]:
    model = fit(listings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model))
    fit_stats = model["fit"]
    log.info(
        "model: n=%d r2=%.3f holdout MAE $%.0f -> %s",
        model["n"],
        fit_stats["r2"],
        fit_stats["holdout_mae"],
        path,
    )
    return model
