import { readFile } from "node:fs/promises";
import path from "node:path";
import type { AppData } from "@/lib/data";

const DATA_DIR = path.join(process.cwd(), "public", "data");

async function readJson<T>(name: string): Promise<T> {
  return JSON.parse(await readFile(path.join(DATA_DIR, name), "utf8")) as T;
}

/** Runs at build time only (static export); the artifacts are committed by `sfrent build`. */
export async function loadAppData(): Promise<AppData> {
  const [stats, hexes, model, zori, summary, neighborhoods] = await Promise.all([
    readJson<AppData["stats"]>("neighborhood_bedroom_stats.json"),
    readJson<AppData["hexes"]>("hexes.json"),
    readJson<AppData["model"]>("model.json"),
    readJson<AppData["zori"]>("zori.json"),
    readJson<AppData["summary"]>("summary.json"),
    readJson<AppData["neighborhoods"]>("analysis_neighborhoods.geojson"),
  ]);
  return { stats, hexes, model, zori, summary, neighborhoods };
}
