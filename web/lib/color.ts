import type { ExpressionSpecification } from "maplibre-gl";

/** Cheap -> expensive. Tuned to read on a dark basemap and stay distinct from the amber accent. */
export const RENT_COLORS = ["#1e3a8a", "#2563eb", "#22d3ee", "#a3e635", "#fbbf24", "#f97316", "#ef4444"];

export type Domain = [number, number];

/** Robust color domain: 5th to 95th percentile so a few outliers don't wash out the map. */
export function colorDomain(values: number[]): Domain {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (sorted.length < 2) return [0, 1];
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];
  const lo = q(0.05);
  const hi = q(0.95);
  return hi > lo ? [lo, hi] : [lo, lo + 1];
}

function stops(domain: Domain): [number, string][] {
  const [lo, hi] = domain;
  return RENT_COLORS.map((c, i) => [lo + ((hi - lo) * i) / (RENT_COLORS.length - 1), c]);
}

export function fillColorExpression(property: string, domain: Domain): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", property], domain[0]],
    ...stops(domain).flat(),
  ] as ExpressionSpecification;
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rentColor(value: number, domain: Domain): string {
  const s = stops(domain);
  if (value <= s[0][0]) return s[0][1];
  if (value >= s[s.length - 1][0]) return s[s.length - 1][1];
  for (let i = 1; i < s.length; i++) {
    if (value <= s[i][0]) {
      const t = (value - s[i - 1][0]) / (s[i][0] - s[i - 1][0]);
      const a = hexToRgb(s[i - 1][1]);
      const b = hexToRgb(s[i][1]);
      const mix = a.map((ch, k) => Math.round(ch + (b[k] - ch) * t));
      return `rgb(${mix.join(",")})`;
    }
  }
  return s[s.length - 1][1];
}

export const RENT_GRADIENT_CSS = `linear-gradient(90deg, ${RENT_COLORS.join(", ")})`;
