import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";

/** Shapes of the artifacts written by `sfrent build` into public/data. */

export type BedroomStats = {
  analysis_neighborhood: string;
  bedrooms: number;
  n: number;
  rent_median: number;
  rent_p25: number;
  rent_p75: number;
  sqft_median: number | null;
};

export type HexCell = {
  /** [lat, lng] center */
  c: [number, number];
  /** boundary ring as [lng, lat] pairs */
  b: [number, number][];
  /** bedrooms -> [n, median rent] */
  s: Record<string, [number, number]>;
};

export type HexData = { resolution: number; cells: Record<string, HexCell> };

export type Bucket = { edges: number[]; labels: string[] };

export type Model = {
  target: string;
  n: number;
  fit: { r2: number; holdout_mae: number; holdout_mape: number; residual_std: number };
  baseline: { bedrooms: number; bathrooms: number; sqft: number; year_built: string; building_units: string };
  buckets: { year_built: Bucket; building_units: Bucket };
  neighborhoods: Record<string, number>;
  neighborhood_n: Record<string, number>;
  coefficients: {
    bedrooms: Record<string, number>;
    bathrooms: Record<string, number>;
    year_built: Record<string, number>;
    building_units: Record<string, number>;
    log_sqft: number;
    sqft_missing: number;
  };
  residual_quantiles: { p10: number; p25: number; p75: number; p90: number };
};

export type ZoriData = {
  latest_month: string;
  /** region ("city" or zip) -> [month "YYYY-MM", rent index] */
  regions: Record<string, [string, number][]>;
};

export type CitywideStats = { n: number; rent_median: number; rent_p25: number; rent_p75: number };

export type Summary = {
  /** bedrooms -> citywide stats over all modelable tenancies */
  citywide: Record<string, CitywideStats>;
  built_at: string;
  reference_month: string | null;
  listings: number;
  modelable: number;
  by_source: Record<string, number>;
  amenity_listings: number;
  neighborhoods: number;
  hexes: number;
  date_range: [string, string];
  model: { n: number; r2: number; holdout_mae: number; holdout_mape: number };
};

export type NeighborhoodProps = { name: string; label: [number, number] };
export type NeighborhoodCollection = FeatureCollection<Polygon | MultiPolygon, NeighborhoodProps>;

export type AppData = {
  stats: BedroomStats[];
  hexes: HexData;
  model: Model;
  zori: ZoriData;
  summary: Summary;
  neighborhoods: NeighborhoodCollection;
};

export const BEDROOM_OPTIONS = [
  { value: 0, label: "Studio" },
  { value: 1, label: "1 bd" },
  { value: 2, label: "2 bd" },
  { value: 3, label: "3 bd" },
  { value: 4, label: "4+ bd" },
] as const;

export const BATHROOM_OPTIONS = [
  { value: 1, label: "1" },
  { value: 1.5, label: "1.5" },
  { value: 2, label: "2" },
  { value: 2.5, label: "2.5" },
  { value: 3, label: "3+" },
] as const;

export const YEAR_BUILT_OPTIONS = [
  { value: "pre_1920", label: "Before 1920", representative: 1910 },
  { value: "1920_1945", label: "1920 – 1945", representative: 1930 },
  { value: "1946_1979", label: "1946 – 1979", representative: 1965 },
  { value: "1980_2009", label: "1980 – 2009", representative: 1995 },
  { value: "2010_plus", label: "2010 or newer", representative: 2018 },
  { value: "unknown", label: "Not sure", representative: null },
] as const;

export const BUILDING_OPTIONS = [
  { value: "1", label: "Single-family / in-law", representative: 1 },
  { value: "2_4", label: "2 – 4 units", representative: 3 },
  { value: "5_19", label: "5 – 19 units", representative: 10 },
  { value: "20_49", label: "20 – 49 units", representative: 30 },
  { value: "50_plus", label: "50+ units", representative: 120 },
  { value: "unknown", label: "Not sure", representative: null },
] as const;

export function bedroomLabel(bedrooms: number): string {
  if (bedrooms === 0) return "Studio";
  return `${bedrooms >= 4 ? "4+" : bedrooms} bd`;
}

/** Stats keyed by neighborhood for one bedroom count (4+ collapses to 4). */
export function statsFor(stats: BedroomStats[], bedrooms: number): Map<string, BedroomStats> {
  const out = new Map<string, BedroomStats>();
  for (const row of stats) {
    if (row.bedrooms === Math.min(bedrooms, 4)) out.set(row.analysis_neighborhood, row);
  }
  return out;
}
