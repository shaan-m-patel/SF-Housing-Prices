import math

import numpy as np
import polars as pl

from sfrent import model


def _synthetic(n=4000, seed=1):
    """Rents generated from known effects so the fit can be checked against the truth."""
    rng = np.random.default_rng(seed)
    nhood = rng.choice(["Mission", "Marina"], n)
    beds = rng.choice([0, 1, 2, 3], n)
    sqft = rng.uniform(350, 1400, n)
    year = rng.choice([1910, 1930, 1965, 1995, 2018], n)
    units = rng.choice([1, 3, 10, 30, 120], n)
    log_rent = (
        np.where(nhood == "Mission", math.log(3400), math.log(4200))
        + np.select([beds == 0, beds == 2, beds == 3], [-0.15, 0.20, 0.35], 0.0)
        + 0.30 * np.log(sqft / 700)
        + np.where(year >= 2010, 0.12, 0.0)
        + rng.normal(0, 0.05, n)
    )
    return pl.DataFrame(
        {
            "analysis_neighborhood": nhood,
            "bedrooms": beds,
            "bathrooms": np.ones(n),
            "sqft": sqft,
            "year_built": year,
            "building_units": units,
            "rent_adj": np.exp(log_rent),
            "is_modelable": np.ones(n, dtype=bool),
        }
    )


def test_bucket_edges():
    assert model.bucket(1905, model.YEAR_EDGES, model.YEAR_LABELS) == "pre_1920"
    assert model.bucket(1946, model.YEAR_EDGES, model.YEAR_LABELS) == "1946_1979"
    assert model.bucket(2030, model.YEAR_EDGES, model.YEAR_LABELS) == "2010_plus"
    assert model.bucket(None, model.YEAR_EDGES, model.YEAR_LABELS) == "unknown"
    assert model.bucket(4, model.UNIT_EDGES, model.UNIT_LABELS) == "2_4"
    assert model.bucket(50, model.UNIT_EDGES, model.UNIT_LABELS) == "50_plus"


def test_fit_recovers_known_effects_and_predicts():
    fitted = model.fit(_synthetic())
    coef = fitted["coefficients"]
    assert fitted["fit"]["r2"] > 0.9
    assert abs(coef["bedrooms"]["2"] - 0.20) < 0.02
    assert abs(coef["log_sqft"] - 0.30) < 0.03
    assert abs(coef["year_built"]["2010_plus"] - 0.12) < 0.03
    assert abs(math.exp(fitted["neighborhoods"]["Mission"]) - 3400) < 120

    rent = model.predict(
        fitted, analysis_neighborhood="Marina", bedrooms=2, bathrooms=1, sqft=700, year_built=1910
    )
    assert abs(rent - 4200 * math.exp(0.20)) / rent < 0.03
    assert fitted["residual_quantiles"]["p25"] < 0 < fitted["residual_quantiles"]["p75"]


def test_small_neighborhoods_are_dropped():
    frame = _synthetic(n=400).with_columns(
        pl.when(pl.arange(0, 400) < 10)
        .then(pl.lit("Tiny"))
        .otherwise(pl.col("analysis_neighborhood"))
        .alias("analysis_neighborhood")
    )
    fitted = model.fit(frame)
    assert "Tiny" not in fitted["neighborhoods"] and fitted["n"] == 390
