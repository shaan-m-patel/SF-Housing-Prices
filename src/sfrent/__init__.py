"""sfrent: San Francisco apartment rent data pipeline.

Collectors pull raw records into ``data/raw/<source>/``, the normalize layer maps every
source onto one ``Listing`` schema, and ``pipeline.build`` writes analysis-ready Parquet.
See ``docs/DATA_PLAN.md`` for the data plan this package implements.
"""

__version__ = "0.1.0"
