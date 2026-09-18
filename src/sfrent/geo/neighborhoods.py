"""SF Analysis Neighborhood polygons and point-in-polygon assignment.

Source: DataSF ``sevw-6tgi`` (2020 census tracts tagged with their Analysis Neighborhood).
Tracts are dissolved per neighborhood into ``data/reference/analysis_neighborhoods.geojson``.
Names match the Rent Board's ``analysis_neighborhood`` field exactly.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

from sfrent.config import REFERENCE_DIR
from sfrent.sources import datasf

log = logging.getLogger(__name__)

DATASET_ID = "sevw-6tgi"
NAME_FIELD = "neighborhoods_analysis_boundaries"
REFERENCE_PATH = REFERENCE_DIR / "analysis_neighborhoods.geojson"


def pull(path: Path = REFERENCE_PATH) -> Path:
    """Download tract polygons and dissolve them into one feature per neighborhood."""
    tracts = datasf.fetch_geojson(DATASET_ID)["features"]
    by_name: dict[str, list[Any]] = {}
    for feature in tracts:
        name = feature["properties"].get(NAME_FIELD)
        if name and feature.get("geometry"):
            by_name.setdefault(name, []).append(shape(feature["geometry"]))
    features = [
        {
            "type": "Feature",
            "properties": {"name": name},
            "geometry": shapely.union_all(geoms).__geo_interface__,
        }
        for name, geoms in sorted(by_name.items())
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    log.info("neighborhoods: %d polygons from %d tracts -> %s", len(features), len(tracts), path)
    return path


class NeighborhoodIndex:
    """Spatial index over neighborhood polygons for bulk point-in-polygon lookups."""

    def __init__(self, features: Sequence[dict[str, Any]]) -> None:
        self.names = [feature["properties"]["name"] for feature in features]
        self.geometries = [shape(feature["geometry"]) for feature in features]
        self._tree = STRtree(self.geometries)

    @classmethod
    def load(cls, path: Path = REFERENCE_PATH) -> NeighborhoodIndex:
        if not path.exists():
            pull(path)
        return cls(json.loads(path.read_text())["features"])

    def assign(
        self, lats: Sequence[float | None], lngs: Sequence[float | None]
    ) -> list[str | None]:
        """Neighborhood name per (lat, lng); ``None`` for missing coordinates or points outside."""
        result: list[str | None] = [None] * len(lats)
        valid = [i for i, (lat, lng) in enumerate(zip(lats, lngs, strict=True)) if lat and lng]
        if not valid:
            return result
        points = shapely.points([lngs[i] for i in valid], [lats[i] for i in valid])
        point_idx, geom_idx = self._tree.query(points, predicate="within")
        for p, g in zip(point_idx.tolist(), geom_idx.tolist(), strict=True):
            result[valid[p]] = self.names[g]
        return result
