import type { Bucket, Model } from "@/lib/data";

/** Client-side mirror of `sfrent.model.predict`: rent = exp(neighborhood + Σ effects). */

export type Unit = {
  neighborhood: string;
  bedrooms: number;
  bathrooms: number;
  sqft: number | null;
  yearBuilt: string; // bucket label, e.g. "1946_1979" or "unknown"
  buildingUnits: string; // bucket label, e.g. "5_19" or "unknown"
};

export type Term = {
  key: string;
  label: string;
  detail: string;
  /** log-rent contribution; 0 for baseline categories */
  value: number;
};

export type Estimate = {
  rent: number;
  band: { p10: number; p25: number; p75: number; p90: number };
  base: number;
  terms: Term[];
};

export function bucketLabel(value: number | null, bucket: Bucket): string {
  if (value === null) return "unknown";
  for (let i = 0; i < bucket.edges.length; i++) {
    if (value < bucket.edges[i]) return bucket.labels[i];
  }
  return bucket.labels[bucket.labels.length - 1];
}

function bathKey(bathrooms: number): string {
  const b = Math.min(bathrooms, 3);
  return Number.isInteger(b) ? String(b) : b.toFixed(1);
}

export function estimate(model: Model, unit: Unit): Estimate {
  const c = model.coefficients;
  const base = model.neighborhoods[unit.neighborhood] ?? 0;
  const beds = Math.min(unit.bedrooms, 5);
  const terms: Term[] = [
    {
      key: "bedrooms",
      label: bedsLabel(beds),
      detail: `vs. ${model.baseline.bedrooms}-bedroom baseline`,
      value: c.bedrooms[String(beds)] ?? 0,
    },
    {
      key: "bathrooms",
      label: `${bathKey(unit.bathrooms)} bath`,
      detail: `vs. ${model.baseline.bathrooms} bath`,
      value: c.bathrooms[bathKey(unit.bathrooms)] ?? 0,
    },
    unit.sqft
      ? {
          key: "sqft",
          label: `${Math.round(unit.sqft).toLocaleString()} sq ft`,
          detail: `elasticity ${c.log_sqft.toFixed(2)} vs. ${model.baseline.sqft} sq ft`,
          value: c.log_sqft * Math.log(unit.sqft / model.baseline.sqft),
        }
      : { key: "sqft", label: "Size unknown", detail: "no square footage given", value: c.sqft_missing },
    {
      key: "year_built",
      label: humanBucket(unit.yearBuilt, "Built"),
      detail: "vs. buildings from before 1920",
      value: c.year_built[unit.yearBuilt] ?? 0,
    },
    {
      key: "building_units",
      label: humanBucket(unit.buildingUnits, "Building"),
      detail: "vs. 5 – 19 unit buildings",
      value: c.building_units[unit.buildingUnits] ?? 0,
    },
  ];
  const logRent = base + terms.reduce((sum, t) => sum + t.value, 0);
  const q = model.residual_quantiles;
  return {
    rent: Math.exp(logRent),
    band: {
      p10: Math.exp(logRent + q.p10),
      p25: Math.exp(logRent + q.p25),
      p75: Math.exp(logRent + q.p75),
      p90: Math.exp(logRent + q.p90),
    },
    base: Math.exp(base),
    terms,
  };
}

/** Multiplicative effect of a log-scale coefficient, e.g. 0.148 -> +16%. */
export function effectPct(value: number): number {
  return Math.expm1(value) * 100;
}

function bedsLabel(beds: number): string {
  if (beds === 0) return "Studio";
  return `${beds}${beds >= 5 ? "+" : ""} bedroom${beds > 1 ? "s" : ""}`;
}

function humanBucket(label: string, prefix: string): string {
  if (label === "unknown") return `${prefix}: not sure`;
  if (label === "pre_1920") return "Built before 1920";
  if (label.endsWith("_plus")) {
    const n = label.replace("_plus", "");
    return prefix === "Built" ? `Built ${n} or later` : `${n}+ unit building`;
  }
  const [lo, hi] = label.split("_");
  if (prefix === "Built") return `Built ${lo} – ${hi}`;
  return lo === "1" ? "Single-family or in-law" : `${lo} – ${hi} unit building`;
}
