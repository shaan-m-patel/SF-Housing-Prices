import type { Feature, FeatureCollection, Polygon } from "geojson";
import type { HexCell, HexData } from "@/lib/data";

export type LatLng = { lat: number; lng: number };

const EARTH_RADIUS_KM = 6371.0088;

export function haversineKm(a: LatLng, b: LatLng): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/** Common SF work hubs; mirrors sfrent.geo.commute.HUBS. */
export const HUBS: { name: string; lat: number; lng: number }[] = [
  { name: "Financial District", lat: 37.7946, lng: -122.4007 },
  { name: "SoMa / Salesforce Tower", lat: 37.7897, lng: -122.3972 },
  { name: "Mission Bay / UCSF", lat: 37.7676, lng: -122.3912 },
  { name: "Civic Center", lat: 37.7793, lng: -122.4193 },
  { name: "UCSF Parnassus", lat: 37.7631, lng: -122.4586 },
  { name: "Caltrain 4th & King", lat: 37.7765, lng: -122.3947 },
];

export const DISTANCE_BANDS_KM: [number, number][] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 5],
  [5, 8],
  [8, 15],
];

export function bandLabel([lo, hi]: [number, number]): string {
  return `${lo}–${hi} km`;
}

/** Circle polygon (as GeoJSON) around a point, used for the commute radius ring. */
export function circlePolygon(center: LatLng, radiusKm: number, steps = 72): Feature<Polygon> {
  const ring: [number, number][] = [];
  const latRad = (center.lat * Math.PI) / 180;
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * 2 * Math.PI;
    const dLat = (radiusKm / EARTH_RADIUS_KM) * Math.cos(theta);
    const dLng = ((radiusKm / EARTH_RADIUS_KM) * Math.sin(theta)) / Math.cos(latRad);
    ring.push([center.lng + (dLng * 180) / Math.PI, center.lat + (dLat * 180) / Math.PI]);
  }
  return { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } };
}

export type HexProps = {
  id: string;
  n: number;
  median: number | null;
  distanceKm: number | null;
  within: boolean;
};

export function hexStats(cell: HexCell, bedrooms: number): [number, number] | undefined {
  return cell.s[String(Math.min(bedrooms, 4))] ?? (bedrooms >= 4 ? cell.s["5"] : undefined);
}

/** Hex polygons with the selected bedroom stats and distance to the work pin attached. */
export function hexFeatures(
  hexes: HexData,
  bedrooms: number,
  work: LatLng | null,
  radiusKm: number,
): FeatureCollection<Polygon, HexProps> {
  const features: Feature<Polygon, HexProps>[] = [];
  for (const [id, cell] of Object.entries(hexes.cells)) {
    const stats = hexStats(cell, bedrooms);
    if (!stats) continue;
    const distanceKm = work ? haversineKm(work, { lat: cell.c[0], lng: cell.c[1] }) : null;
    features.push({
      type: "Feature",
      properties: {
        id,
        n: stats[0],
        median: stats[1],
        distanceKm,
        within: distanceKm === null ? true : distanceKm <= radiusKm,
      },
      geometry: { type: "Polygon", coordinates: [[...cell.b, cell.b[0]]] },
    });
  }
  return { type: "FeatureCollection", features };
}

/** Listing-weighted median of hex medians (a robust "typical rent" for a group of cells). */
export function weightedMedian(items: { median: number; n: number }[]): number | null {
  if (!items.length) return null;
  const sorted = [...items].sort((a, b) => a.median - b.median);
  const total = sorted.reduce((s, x) => s + x.n, 0);
  let acc = 0;
  for (const item of sorted) {
    acc += item.n;
    if (acc >= total / 2) return item.median;
  }
  return sorted[sorted.length - 1].median;
}
